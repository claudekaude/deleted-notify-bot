"""
Бизнес-события Telegram: business_connection, business_message, deleted_business_messages.

Telegram в deleted_business_messages присылает только номера сообщений, поэтому
всё, что нужно показать при удалении, сохраняется в момент получения:
- метаданные: message_id, chat_id, автор, дата, тип содержимого;
- текст или подпись (если STORE_MESSAGE_TEXT=1) — только для сообщений собеседника;
- file_id медиа — ссылка Telegram на файл (не сам файл), по ней медиа можно
  повторно отправить владельцу, пока Telegram хранит файл на серверах.
Одноразовые (view-once) медиа Telegram ботам не передаёт в принципе — их здесь нет.
"""
from __future__ import annotations

import logging
import os
import time

from aiogram import Bot, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BusinessConnection, BusinessMessagesDeleted, Message
from aiogram.utils.text_decorations import html_decoration

from config import Config
from db import Database
from handlers.common import get_bot_username, menu_markup
from keyboards import buy_kb
from locales import normalize_lang, t
from utils import (clip_html, download_media, fmt_person_short, fmt_ts, full_name,
                   safe_send, send_saved_media)

log = logging.getLogger(__name__)
router = Router(name="business")

# Сколько удалённых сообщений расписывать подробно в одном уведомлении
MAX_DETAILED_ENTRIES = 20
# Сколько сохранённых медиа максимум переслать при пакетном удалении
MAX_MEDIA_RESEND = 5
# Ограничение длины текста в уведомлении (лимит сообщения Telegram — 4096 символов)
MAX_TEXT_SINGLE = 3500
MAX_TEXT_MULTI = 400
MAX_CAPTION = 900  # лимит подписи к медиа — 1024, оставляем запас

# Типы, для которых в заголовке уведомления используем значок камеры вместо корзины
VISUAL_TYPES = {"photo", "video", "animation", "video_note"}


def _html_content(message: Message, owner_id: int, config: Config) -> str | None:
    """
    HTML-содержимое сообщения собеседника с сохранённым форматированием (жирный,
    курсив и т.п.). Свои сообщения владельца не храним. Результат безопасен для HTML.
    """
    if not config.store_message_text:
        return None
    if message.from_user and message.from_user.id == owner_id:
        return None
    if message.text is not None:
        return html_decoration.unparse(message.text, message.entities or [])
    if message.caption is not None:
        return html_decoration.unparse(message.caption, message.caption_entities or [])
    return None


def _extract_file_id(message: Message) -> str | None:
    """file_id основного медиа сообщения (не сам файл). None — если медиа нет."""
    if message.photo:
        return message.photo[-1].file_id          # самое крупное превью
    for attr in ("video", "animation", "document", "audio", "voice", "video_note", "sticker"):
        obj = getattr(message, attr, None)
        if obj is not None:
            return obj.file_id
    return None


def _quote(lang: str, html_text: str | None, limit: int) -> str:
    """Текст (с сохранённым форматированием) в цитате под спойлером. '' если пусто."""
    content = clip_html(html_text, limit)
    return t(lang, "content_quote", text=content) if content else ""


async def _watermark(bot: Bot, lang: str) -> str:
    """Подпись-водяной знак с тегом бота под каждым уведомлением."""
    return t(lang, "watermark", bot=await get_bot_username(bot))


def _can_reply(connection: BusinessConnection) -> bool:
    """В Bot API 9.0+ права лежат в rights, раньше было поле can_reply."""
    if connection.rights is not None:
        return bool(connection.rights.can_reply)
    return bool(connection.can_reply)


async def _owner_lang(db: Database, owner_id: int) -> str:
    return normalize_lang(await db.get_language(owner_id))


async def _resolve_connection(bot: Bot, db: Database, connection_id: str | None) -> dict | None:
    """
    Находит подключение (и владельца) по business_connection_id.
    Если в БД его нет (например, база создана заново) — запрашивает у Telegram.
    """
    if not connection_id:
        return None
    conn = await db.get_connection(connection_id)
    if conn is not None:
        return conn
    try:
        bc = await bot.get_business_connection(connection_id)
    except TelegramAPIError as exc:
        log.warning("Не удалось получить бизнес-подключение %s: %s", connection_id, exc)
        return None
    await db.upsert_user(bc.user.id, bc.user.username, bc.user.first_name)
    await db.upsert_connection(bc.id, bc.user.id, bc.user_chat_id, bc.is_enabled, _can_reply(bc))
    return await db.get_connection(connection_id)


async def _tracking_allowed(db: Database, owner_id: int) -> bool:
    """Отслеживать можно, если уведомления включены и подписка активна."""
    user = await db.get_user(owner_id)
    if user is None or not user["notifications_enabled"]:
        return False
    return await db.has_active_subscription(owner_id)


async def send_renew_reminder(bot: Bot, db: Database, config: Config, owner_id: int) -> None:
    """Напоминание о продлении, не чаще раза в REMINDER_INTERVAL_HOURS."""
    if not await db.should_remind(owner_id, config.reminder_interval_hours):
        return
    lang = await _owner_lang(db, owner_id)
    if await safe_send(bot, owner_id, t(lang, "sub_expired_reminder"), reply_markup=buy_kb(lang)):
        await db.mark_reminded(owner_id)


# ---------------------------------------------------------------- 1. ПОДКЛЮЧЕНИЕ

@router.business_connection()
async def on_business_connection(connection: BusinessConnection, bot: Bot, db: Database, config: Config) -> None:
    owner = connection.user
    try:
        await db.upsert_user(owner.id, owner.username, owner.first_name)
        await db.upsert_connection(connection.id, owner.id, connection.user_chat_id,
                                   connection.is_enabled, _can_reply(connection))
    except Exception:
        log.exception("Ошибка сохранения бизнес-подключения %s", connection.id)
        return

    lang = normalize_lang(await db.get_language(owner.id) or owner.language_code)
    log.info("Бизнес-подключение %s владельца %s: enabled=%s", connection.id, owner.id, connection.is_enabled)

    if connection.is_enabled:
        texts = [t(lang, "connected"), t(lang, "privacy")]
        if await db.start_trial_if_needed(owner.id, config.trial_days):
            texts.append(t(lang, "trial_started", days=config.trial_days))
        await safe_send(bot, connection.user_chat_id, "\n\n".join(texts),
                        reply_markup=await menu_markup(db, owner.id, lang))
    else:
        # Бот отключён. Данные НЕ удаляем: язык, настройки, история и медиа сохраняются,
        # при повторном подключении прежнее состояние восстанавливается.
        await safe_send(bot, connection.user_chat_id, t(lang, "disconnected"))


# ---------------------------------------------------------------- 2. МЕТАДАННЫЕ

@router.business_message()
async def on_business_message(message: Message, bot: Bot, db: Database, config: Config) -> None:
    conn = await _resolve_connection(bot, db, message.business_connection_id)
    if conn is None or not conn["is_enabled"]:
        return
    owner_id = conn["owner_user_id"]

    # Минимизация данных: без активной подписки/при паузе ничего не сохраняем
    if not await _tracking_allowed(db, owner_id):
        return

    author = message.from_user
    is_own = bool(author and author.id == owner_id)
    content_type = getattr(message.content_type, "value", message.content_type)
    # file_id и медиа храним только для сообщений собеседника, не для своих сообщений владельца
    file_id = None if is_own else _extract_file_id(message)

    # Сразу скачиваем оригинал медиа на диск (не дожидаясь удаления)
    media_path = media_size = None
    if file_id and config.store_media:
        dest_dir = os.path.join(config.media_dir, str(owner_id))
        name_hint = f"{message.chat.id}_{message.message_id}"
        media_path, media_size = await download_media(bot, file_id, content_type, dest_dir, name_hint)
        if media_path is None:
            # Диагностика идёт в логи владельца, пользователю ничего не показываем
            log.warning("Медиа %s/%s не сохранено на диск (останется ссылка file_id)",
                        message.chat.id, message.message_id)

    try:
        await db.save_message_meta(
            owner_user_id=owner_id,
            connection_id=conn["business_connection_id"],
            chat_id=message.chat.id,
            message_id=message.message_id,
            from_user_id=author.id if author else None,
            from_username=author.username if author else None,
            from_name=full_name(author.first_name, author.last_name) if author else None,
            sent_at=int(message.date.timestamp()),
            content_type=content_type,
            text=_html_content(message, owner_id, config),
            file_id=file_id,
            media_path=media_path,
            media_size=media_size,
        )
    except Exception:
        log.exception("Не удалось сохранить метаданные сообщения %s/%s", message.chat.id, message.message_id)


@router.edited_business_message()
async def on_edited_business_message(message: Message, bot: Bot, db: Database, config: Config) -> None:
    """
    Правка сообщения: сохраняем новую версию, всю историю изменений и присылаем
    владельцу компактное уведомление «Было / Стало».
    """
    conn = await _resolve_connection(bot, db, message.business_connection_id)
    if conn is None or not conn["is_enabled"]:
        return
    owner_id = conn["owner_user_id"]
    if not await _tracking_allowed(db, owner_id):
        return

    new_text = _html_content(message, owner_id, config)
    if new_text is None:
        return  # сообщение владельца или хранение текста выключено — не трогаем

    chat_id = message.chat.id
    row = await db.get_message(owner_id, chat_id, message.message_id)
    old_text = row["text"] if row else None
    # Защита от дублей: то же содержимое -> повторное событие, ничего не делаем
    if old_text == new_text:
        return

    edited_at = int(time.time())
    try:
        await db.add_edit(owner_id, chat_id, message.message_id, old_text, new_text, edited_at)
        await db.update_message_text(owner_id, chat_id, message.message_id, new_text)
    except Exception:
        log.exception("Не удалось сохранить правку сообщения %s/%s", chat_id, message.message_id)
        return

    user = await db.get_user(owner_id)
    if user is None or not user["notifications_enabled"]:
        return
    lang = normalize_lang(user["language"])

    author = fmt_person_short(
        message.from_user.id if message.from_user else (row and row["from_user_id"]),
        message.from_user.username if message.from_user else (row and row["from_username"]),
        full_name(message.from_user.first_name, message.from_user.last_name) if message.from_user
        else (row and row["from_name"]),
    )
    old_block = _quote(lang, old_text, MAX_TEXT_SINGLE) or t(lang, "edit_old_unavailable")
    new_block = _quote(lang, new_text, MAX_TEXT_SINGLE)
    body = (
        t(lang, "edit_head", author=author) + "\n"
        + t(lang, "edit_time", edited=fmt_ts(edited_at, config.timezone)) + "\n\n"
        + t(lang, "edit_old_label") + "\n" + old_block + "\n"
        + t(lang, "edit_new_label") + "\n" + new_block
        + await _watermark(bot, lang)
    )
    await safe_send(bot, owner_id, body)


# ---------------------------------------------------------------- 3. УДАЛЕНИЕ

@router.deleted_business_messages()
async def on_deleted_messages(event: BusinessMessagesDeleted, bot: Bot, db: Database, config: Config) -> None:
    conn = await _resolve_connection(bot, db, event.business_connection_id)
    if conn is None:
        log.warning("Удаление в неизвестном подключении %s — пропуск", event.business_connection_id)
        return
    owner_id = conn["owner_user_id"]
    chat_id = event.chat.id
    message_ids = list(event.message_ids)
    deleted_at = int(time.time())  # Telegram не передаёт время удаления — берём момент получения

    meta = await db.get_messages_meta(owner_id, chat_id, message_ids)
    # Помечаем удалёнными все известные записи (строки остаются для раздела «История»)
    known_ids = [mid for mid, row in meta.items() if not row["is_deleted"]]
    if known_ids:
        await db.mark_messages_deleted(owner_id, chat_id, known_ids, deleted_at)

    user = await db.get_user(owner_id)
    if user is None or not user["notifications_enabled"]:
        return  # уведомления на паузе — запись помечена, но не присылаем

    # Проверка подписки ПЕРЕД отправкой уведомления
    if not await db.has_active_subscription(owner_id):
        await send_renew_reminder(bot, db, config, owner_id)
        return

    lang = normalize_lang(user["language"])
    tz = config.timezone
    deleted_text = fmt_ts(deleted_at, tz)

    rows: list[dict] = []
    unknown = 0
    for mid in message_ids:
        row = meta.get(mid)
        if row is None:
            unknown += 1                       # не сохраняли это сообщение
        elif row["is_deleted"]:
            continue                           # дубликат события — уже обработано
        elif row["from_user_id"] == owner_id:
            continue                           # свои сообщения владельца не репортим
        else:
            rows.append(row)

    total = len(rows) + unknown
    if total == 0:
        return  # удалены только свои сообщения владельца или дубликат события

    text_rows = [r for r in rows if not r.get("file_id")]
    media_rows = [r for r in rows if r.get("file_id")]
    single = total == 1
    text_limit = MAX_TEXT_SINGLE if single else MAX_TEXT_MULTI

    wm = await _watermark(bot, lang)

    def _head(row: dict) -> str:
        """Шапка уведомления: автор + действие (📷 для медиа, 🗑 для текста) и время."""
        author = fmt_person_short(row["from_user_id"], row["from_username"], row["from_name"])
        key = "del_head_media" if row.get("content_type") in VISUAL_TYPES else "del_head"
        return (t(lang, key, author=author) + "\n"
                + t(lang, "del_time", sent=fmt_ts(row["sent_at"], tz), deleted=deleted_text))

    # Текстовые удаления: шапка, под ней содержимое под спойлером, внизу тег бота
    for row in text_rows[:MAX_DETAILED_ENTRIES]:
        block = _quote(lang, row.get("text"), text_limit)
        await safe_send(bot, owner_id, _head(row) + (f"\n\n{block}" if block else "") + wm)

    # Медиа: сам файл — главный элемент, под спойлером; подпись = шапка + содержимое + тег
    for row in media_rows[:MAX_MEDIA_RESEND]:
        block = _quote(lang, row.get("text"), MAX_CAPTION)
        caption = _head(row) + (f"\n\n{block}" if block else "") + wm
        ok = await send_saved_media(bot, owner_id, row["content_type"], row["file_id"],
                                    caption=caption, local_path=row.get("media_path"))
        if not ok:
            await safe_send(bot, owner_id, _head(row) + (f"\n\n{block}" if block else "")
                            + "\n" + t(lang, "deleted_media_unavailable", count=1) + wm)

    # Остаток: неизвестные (без деталей) и то, что не поместилось в подробный показ
    shown = min(len(text_rows), MAX_DETAILED_ENTRIES) + min(len(media_rows), MAX_MEDIA_RESEND)
    remainder = total - shown
    if remainder > 0:
        if shown == 0:
            await safe_send(bot, owner_id, t(lang, "deleted_unknown_compact",
                                             count=remainder, deleted=deleted_text) + wm)
        else:
            await safe_send(bot, owner_id, t(lang, "deleted_more_compact", count=remainder) + wm)

    # «Надгробия» для неизвестных удалённых id, чтобы дубликат события не повторил уведомление
    if unknown:
        unknown_ids = [mid for mid in message_ids if mid not in meta]
        await db.insert_deleted_tombstones(owner_id, event.business_connection_id, chat_id,
                                           unknown_ids, deleted_at)
