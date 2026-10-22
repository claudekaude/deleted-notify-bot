"""
Оплата подписки через Telegram Stars (валюта XTR).

Поток: «💳 Купить» -> выбор тарифа -> send_invoice(currency="XTR")
       -> pre_checkout_query (проверка) -> successful_payment (продление).
Возврат: refundStarPayment (команда админа /refund) и событие refunded_payment.
"""
from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery

from config import Config, Plan
from db import Database
from handlers.common import edit_or_send, menu_markup
from keyboards import BuyCb, MenuCb, plans_kb
from locales import t
from utils import fmt_date, plan_name

log = logging.getLogger(__name__)
router = Router(name="payments")

CURRENCY = "XTR"


def make_payload(plan: Plan, user_id: int) -> str:
    return f"sub:{plan.code}:{user_id}"


def parse_payload(payload: str) -> tuple[str, int] | None:
    """'sub:m1:123' -> ('m1', 123); None — если payload не наш."""
    try:
        prefix, plan_code, user_id = payload.split(":")
        if prefix != "sub":
            return None
        return plan_code, int(user_id)
    except ValueError:
        return None


# ---------------------------------------------------------------- выбор тарифа и счёт

@router.callback_query(MenuCb.filter(F.action == "buy"))
async def on_buy(callback: CallbackQuery, config: Config, lang: str) -> None:
    await callback.answer()
    await edit_or_send(callback, t(lang, "buy_title"), plans_kb(lang, config.plans))


@router.message(Command("buy"))
async def cmd_buy(message: Message, config: Config, lang: str) -> None:
    await message.answer(t(lang, "buy_title"), reply_markup=plans_kb(lang, config.plans))


@router.callback_query(BuyCb.filter())
async def on_plan_selected(callback: CallbackQuery, callback_data: BuyCb, bot: Bot,
                           config: Config, lang: str) -> None:
    plan = config.plans.get(callback_data.plan)
    if plan is None:
        await callback.answer(t(lang, "error_generic"), show_alert=True)
        return

    name = plan_name(lang, plan.code)
    try:
        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title=t(lang, "invoice_title", name=name),
            description=t(lang, "invoice_description", name=name),
            payload=make_payload(plan, callback.from_user.id),
            currency=CURRENCY,
            # Для звёзд — ровно одна позиция, provider_token не нужен
            prices=[LabeledPrice(label=t(lang, "invoice_label", name=name), amount=plan.stars)],
        )
        await callback.answer(t(lang, "invoice_sent"))
    except TelegramAPIError:
        log.exception("Не удалось выставить счёт пользователю %s", callback.from_user.id)
        await callback.answer(t(lang, "error_generic"), show_alert=True)


# ---------------------------------------------------------------- проверка перед оплатой

@router.pre_checkout_query()
async def on_pre_checkout(query: PreCheckoutQuery, config: Config, lang: str) -> None:
    """Telegram ждёт ответа до 10 секунд — проверяем быстро и отвечаем всегда."""
    try:
        parsed = parse_payload(query.invoice_payload)
        plan = config.plans.get(parsed[0]) if parsed else None
        ok = (
            parsed is not None
            and plan is not None
            and parsed[1] == query.from_user.id
            and query.currency == CURRENCY
            and query.total_amount == plan.stars
        )
    except Exception:
        log.exception("Ошибка проверки pre_checkout_query")
        ok = False

    if ok:
        await query.answer(ok=True)
    else:
        log.warning("Отклонён pre_checkout от %s: payload=%r amount=%s",
                    query.from_user.id, query.invoice_payload, query.total_amount)
        await query.answer(ok=False, error_message=t(lang, "precheckout_error"))


# ---------------------------------------------------------------- успешная оплата

@router.message(F.successful_payment)
async def on_successful_payment(message: Message, db: Database, config: Config, lang: str) -> None:
    payment = message.successful_payment
    user_id = message.from_user.id
    parsed = parse_payload(payment.invoice_payload)
    plan = config.plans.get(parsed[0]) if parsed else None
    if plan is None:
        log.error("Оплата с неизвестным payload %r от %s (charge %s)",
                  payment.invoice_payload, user_id, payment.telegram_payment_charge_id)
        await message.answer(t(lang, "error_generic"))
        return

    # Защита от повторной обработки одного и того же платежа
    is_new = await db.add_payment(user_id, plan.code, payment.total_amount,
                                  payment.currency, payment.telegram_payment_charge_id)
    if not is_new:
        log.info("Повторное событие оплаты %s — пропуск", payment.telegram_payment_charge_id)
        return

    expires = await db.extend_subscription(user_id, plan.code, plan.days)
    log.info("Оплата: user=%s plan=%s stars=%s charge=%s",
             user_id, plan.code, payment.total_amount, payment.telegram_payment_charge_id)

    if expires is None:
        text = t(lang, "payment_success_lifetime")
    else:
        text = t(lang, "payment_success", until=fmt_date(expires, config.timezone))
    await message.answer(text, reply_markup=await menu_markup(db, user_id, lang))


# ---------------------------------------------------------------- возвраты

async def apply_refund(db: Database, config: Config, charge_id: str) -> dict | None:
    """Помечает платёж возвращённым и откатывает оплаченный период. Возвращает платёж."""
    payment = await db.get_payment(charge_id)
    if payment is None or not await db.mark_payment_refunded(charge_id):
        return None
    plan = config.plans.get(payment["plan"])
    await db.reduce_subscription(payment["owner_user_id"], plan.days if plan else None)
    return payment


async def refund_star_payment(bot: Bot, db: Database, config: Config, charge_id: str) -> dict | None:
    """
    Возврат звёзд через refundStarPayment.
    Бросает TelegramAPIError, если Telegram отклонил возврат.
    """
    payment = await db.get_payment(charge_id)
    if payment is None or payment["status"] != "paid":
        return None
    await bot.refund_star_payment(user_id=payment["owner_user_id"], telegram_payment_charge_id=charge_id)
    return await apply_refund(db, config, charge_id)


@router.message(F.refunded_payment)
async def on_refunded_payment(message: Message, db: Database, config: Config, lang: str) -> None:
    """Telegram сообщает о возврате (например, сделанном не через /refund) — синхронизируем БД."""
    refunded = message.refunded_payment
    payment = await apply_refund(db, config, refunded.telegram_payment_charge_id)
    if payment:
        await message.answer(t(lang, "payment_refunded", amount=refunded.total_amount))


@router.message(Command("paysupport"))
async def cmd_paysupport(message: Message, lang: str) -> None:
    """Обязательная по правилам Telegram команда поддержки по платежам."""
    await message.answer(t(lang, "paysupport", user_id=message.from_user.id))
