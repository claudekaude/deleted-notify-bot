"""Общие функции, которые используют разные хендлеры."""
from __future__ import annotations

import logging
from html import escape

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message, User

from config import Config
from db import Database
from keyboards import main_menu_kb
from locales import t
from utils import fmt_date, plan_name

log = logging.getLogger(__name__)

# Кэш username бота, чтобы не запрашивать get_me() на каждое сообщение
_bot_username: str | None = None


async def get_bot_username(bot: Bot) -> str:
    global _bot_username
    if _bot_username is None:
        me = await bot.get_me()
        _bot_username = me.username or "bot"
    return _bot_username


async def edit_or_send(callback: CallbackQuery, text: str, reply_markup: InlineKeyboardMarkup | None = None) -> None:
    """Редактирует сообщение с кнопками; если нельзя — отправляет новое."""
    msg = callback.message
    if isinstance(msg, Message):
        try:
            await msg.edit_text(text, reply_markup=reply_markup, disable_web_page_preview=True)
            return
        except TelegramBadRequest as exc:
            if "message is not modified" in str(exc):
                return
            log.debug("Не удалось отредактировать сообщение: %s", exc)
    if callback.from_user:
        await callback.bot.send_message(callback.from_user.id, text, reply_markup=reply_markup,
                                        disable_web_page_preview=True)


async def menu_markup(db: Database, user_id: int, lang: str) -> InlineKeyboardMarkup:
    return main_menu_kb(lang)


async def onboard(bot: Bot, db: Database, config: Config, user: User, lang: str) -> list[str]:
    """
    Приветствие нового пользователя: выдаёт пробный период (один раз)
    и возвращает тексты для отправки (приветствие с предупреждением о приватности).
    """
    texts = [
        t(lang, "welcome",
          name=escape(user.first_name or user.username or str(user.id)),
          bot_username=await get_bot_username(bot),
          privacy=t(lang, "privacy")),
    ]
    if await db.start_trial_if_needed(user.id, config.trial_days):
        texts.append(t(lang, "trial_started", days=config.trial_days))
    return texts


async def build_status(bot: Bot, db: Database, config: Config, user_id: int, lang: str) -> str:
    """Текст для кнопки «📊 Статус»: подписка, подключение, уведомления."""
    sub = await db.get_subscription(user_id)
    lines = [t(lang, "status_title"), ""]

    if db.subscription_is_active(sub):
        if sub["expires_at"] is None:
            lines.append(t(lang, "status_sub_lifetime"))
        else:
            lines.append(t(lang, "status_sub_active",
                           plan=plan_name(lang, sub["plan"]),
                           until=fmt_date(sub["expires_at"], config.timezone)))
    elif sub:
        lines.append(t(lang, "status_sub_expired", until=fmt_date(sub["expires_at"], config.timezone)))
    else:
        lines.append(t(lang, "status_sub_none"))

    connections = await db.get_owner_connections(user_id)
    if not connections:
        lines.append(t(lang, "status_conn_none", bot_username=await get_bot_username(bot)))
    elif any(c["is_enabled"] for c in connections):
        lines.append(t(lang, "status_conn_on"))
    else:
        lines.append(t(lang, "status_conn_off"))

    user = await db.get_user(user_id)
    enabled = bool(user["notifications_enabled"]) if user else True
    lines.append(t(lang, "status_notif_on" if enabled else "status_notif_off"))
    return "\n".join(lines)
