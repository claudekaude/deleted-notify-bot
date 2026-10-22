"""
Команды администратора. Доступ — только для ID из config.admin_ids
(главный ADMIN_ID + необязательные ADMIN_IDS). Проверка прав на стороне сервера.

Команды:
    /stats              — общая статистика
    /users [N]          — список последних N пользователей и их подписок
    /grant  <id> <дней|forever>  — выдать подписку
    /extend <id> <дней|forever>  — продлить подписку (синоним grant, но по смыслу — продление)
    /revoke <id>        — досрочно отозвать подписку
    /subinfo <id>       — подписка, подключение и счётчик записей пользователя
    /payments [id]      — последние платежи
    /refund <charge_id> — возврат звёзд
    /backup             — резервная копия базы
"""
from __future__ import annotations

import logging
import os
import tempfile
import zipfile
from datetime import datetime

from aiogram import Bot, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import BaseFilter, Command, CommandObject
from aiogram.types import FSInputFile, Message

from config import Config
from db import Database
from handlers.payments import refund_star_payment
from locales import normalize_lang, t
from utils import fmt_date, plan_name, safe_send

log = logging.getLogger(__name__)
router = Router(name="admin")

# Максимум дней при ручной выдаче (≈100 лет = практически «навсегда»)
MAX_GRANT_DAYS = 36500


class IsAdmin(BaseFilter):
    """Проверка прав администратора на сервере (не полагаемся на скрытие кнопок)."""

    async def __call__(self, message: Message, config: Config) -> bool:
        return message.from_user is not None and message.from_user.id in config.admin_ids


router.message.filter(IsAdmin())


def _parse_days(raw: str) -> int | None:
    """Разбирает число дней; 'forever'/'inf'/'0' -> None (бессрочно). Иначе ValueError."""
    raw = raw.strip().lower()
    if raw in ("forever", "inf", "вечно", "навсегда", "0"):
        return None
    days = int(raw)
    if days < 1 or days > MAX_GRANT_DAYS:
        raise ValueError
    return days


async def _apply_grant(message: Message, command: CommandObject, bot: Bot, db: Database,
                       config: Config, lang: str, usage_key: str) -> None:
    """Общая логика для /grant и /extend: продлевает подписку и уведомляет пользователя."""
    args = (command.args or "").split()
    try:
        user_id = int(args[0])
        days = _parse_days(args[1])
    except (IndexError, ValueError):
        await message.answer(t(lang, usage_key))
        return

    if await db.get_user(user_id) is None:
        await db.upsert_user(user_id, None, None)
    expires = await db.extend_subscription(user_id, "grant", days)
    until = fmt_date(expires, config.timezone) if expires else "♾"
    days_text = str(days) if days is not None else "∞"
    await message.answer(t(lang, "admin_grant_ok", user_id=user_id, days=days_text, until=until))
    log.info("Админ %s: подписка пользователю %s на %s дн.", message.from_user.id, user_id, days_text)

    user_lang = normalize_lang(await db.get_language(user_id))
    await safe_send(bot, user_id, t(user_lang, "admin_grant_notify", days=days_text, until=until))


@router.message(Command("stats"))
async def cmd_stats(message: Message, db: Database, lang: str) -> None:
    await message.answer(t(lang, "admin_stats", **await db.stats()))


@router.message(Command("grant"))
async def cmd_grant(message: Message, command: CommandObject, bot: Bot, db: Database,
                    config: Config, lang: str) -> None:
    await _apply_grant(message, command, bot, db, config, lang, "admin_grant_usage")


@router.message(Command("extend"))
async def cmd_extend(message: Message, command: CommandObject, bot: Bot, db: Database,
                     config: Config, lang: str) -> None:
    await _apply_grant(message, command, bot, db, config, lang, "admin_extend_usage")


@router.message(Command("revoke"))
async def cmd_revoke(message: Message, command: CommandObject, bot: Bot, db: Database, lang: str) -> None:
    try:
        user_id = int((command.args or "").strip())
    except ValueError:
        await message.answer(t(lang, "admin_revoke_usage"))
        return
    ok = await db.revoke_subscription(user_id)
    await message.answer(t(lang, "admin_revoke_ok" if ok else "admin_revoke_none", user_id=user_id))
    if ok:
        log.info("Админ %s отозвал подписку у %s", message.from_user.id, user_id)


@router.message(Command("subinfo"))
async def cmd_subinfo(message: Message, command: CommandObject, db: Database, config: Config, lang: str) -> None:
    try:
        user_id = int((command.args or "").strip())
    except ValueError:
        await message.answer(t(lang, "admin_subinfo_usage"))
        return
    sub = await db.get_subscription(user_id)
    summary = await db.user_summary(user_id)
    if sub is None:
        sub_line = t(lang, "status_sub_none")
    elif db.subscription_is_active(sub):
        until = "♾" if sub["expires_at"] is None else fmt_date(sub["expires_at"], config.timezone)
        sub_line = t(lang, "admin_subinfo_active", plan=plan_name(lang, sub["plan"]), until=until)
    else:
        until = fmt_date(sub["expires_at"], config.timezone)
        sub_line = t(lang, "admin_subinfo_inactive", until=until)
    await message.answer(t(lang, "admin_subinfo", user_id=user_id, sub=sub_line,
                           conn_active=summary["connections_active"], conn_total=summary["connections_total"],
                           messages=summary["messages_meta"]))


@router.message(Command("users"))
async def cmd_users(message: Message, command: CommandObject, db: Database, config: Config, lang: str) -> None:
    try:
        limit = min(int((command.args or "20").strip()), 50)
    except ValueError:
        limit = 20
    users = await db.list_users(limit=limit)
    if not users:
        await message.answer(t(lang, "admin_users_empty"))
        return
    lines = [t(lang, "admin_users_title", count=len(users))]
    for u in users:
        active = db.subscription_is_active(u) if u.get("plan") else False
        mark = "✅" if active else "▫️"
        name = ("@" + u["username"]) if u["username"] else (u["first_name"] or "—")
        if u.get("plan") and u["expires_at"]:
            until = fmt_date(u["expires_at"], config.timezone)
        elif u.get("plan"):
            until = "♾"
        else:
            until = "—"
        lines.append(f"{mark} <code>{u['user_id']}</code> · {name} · {until}")
    await message.answer("\n".join(lines))


@router.message(Command("backup"))
async def cmd_backup(message: Message, db: Database, config: Config, lang: str) -> None:
    """Резервная копия: снимок базы + все медиафайлы в одном zip."""
    stamp = datetime.now(config.timezone).strftime("%Y%m%d-%H%M%S")
    backups_dir = os.path.join(os.path.dirname(config.db_path) or ".", "backups")
    os.makedirs(backups_dir, exist_ok=True)
    zip_path = os.path.join(backups_dir, f"backup-{stamp}.zip")
    try:
        # 1) согласованный снимок базы во временный файл
        with tempfile.TemporaryDirectory() as tmp:
            db_snapshot = os.path.join(tmp, "bot.db")
            await db.backup_to(db_snapshot)
            # 2) упаковываем снимок базы + папку медиа
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
                z.write(db_snapshot, "bot.db")
                if os.path.isdir(config.media_dir):
                    for root, _dirs, files in os.walk(config.media_dir):
                        for fn in files:
                            full = os.path.join(root, fn)
                            arc = os.path.join("media", os.path.relpath(full, config.media_dir))
                            z.write(full, arc)
        size_kb = max(1, os.path.getsize(zip_path) // 1024)
        await message.answer(t(lang, "admin_backup_ok", path=zip_path, size=size_kb))
        # Telegram ограничивает размер файла от бота (~50 МБ) — большой архив только на диске
        if os.path.getsize(zip_path) < 45 * 1024 * 1024:
            try:
                await message.answer_document(FSInputFile(zip_path), caption=t(lang, "admin_backup_file"))
            except TelegramAPIError as exc:
                log.warning("Копия создана, но не отправлена файлом: %s", exc)
    except Exception as exc:
        log.exception("Не удалось создать резервную копию")
        await message.answer(t(lang, "admin_backup_error", error=str(exc)))


@router.message(Command("refund"))
async def cmd_refund(message: Message, command: CommandObject, bot: Bot, db: Database,
                     config: Config, lang: str) -> None:
    charge_id = (command.args or "").strip()
    if not charge_id:
        await message.answer(t(lang, "admin_refund_usage"))
        return
    try:
        payment = await refund_star_payment(bot, db, config, charge_id)
    except TelegramAPIError as exc:
        log.warning("Возврат %s отклонён: %s", charge_id, exc)
        await message.answer(t(lang, "admin_refund_error", error=str(exc)))
        return
    if payment is None:
        await message.answer(t(lang, "admin_refund_not_found"))
        return

    await message.answer(t(lang, "admin_refund_ok", charge_id=charge_id, amount=payment["amount"]))
    user_lang = normalize_lang(await db.get_language(payment["owner_user_id"]))
    await safe_send(bot, payment["owner_user_id"], t(user_lang, "payment_refunded", amount=payment["amount"]))


@router.message(Command("payments"))
async def cmd_payments(message: Message, command: CommandObject, db: Database,
                       config: Config, lang: str) -> None:
    user_id: int | None = None
    if command.args:
        try:
            user_id = int(command.args.strip())
        except ValueError:
            await message.answer(t(lang, "admin_refund_usage"))
            return
    payments = await db.list_payments(user_id)
    if not payments:
        await message.answer(t(lang, "admin_payments_empty"))
        return
    lines = [t(lang, "admin_payments_title")]
    for p in payments:
        lines.append(
            f"• {fmt_date(p['created_at'], config.timezone)} · <code>{p['owner_user_id']}</code> · "
            f"{p['plan']} · {p['amount']} ⭐ · {p['status']}\n  <code>{p['telegram_payment_charge_id']}</code>"
        )
    await message.answer("\n".join(lines))
