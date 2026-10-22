"""Вспомогательные функции: форматирование и безопасная отправка сообщений."""
from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import datetime, timezone
from html import escape, unescape
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
)
from aiogram.types import Chat, FSInputFile

from locales import t

log = logging.getLogger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")
# Расширение файла по типу содержимого (запасной вариант, если нет в file_path)
_EXT_BY_TYPE = {
    "photo": ".jpg", "video": ".mp4", "animation": ".mp4", "video_note": ".mp4",
    "voice": ".ogg", "audio": ".mp3", "document": "", "sticker": ".webp",
}


def clip_html(html: str | None, limit: int) -> str | None:
    """
    Безопасно обрезает HTML-содержимое до limit символов.
    Если укладывается — возвращает как есть (с сохранённым форматированием);
    иначе срезает теги и режет по тексту, чтобы не поломать разметку.
    """
    if html is None:
        return None
    if len(html) <= limit:
        return html
    plain = unescape(_TAG_RE.sub("", html))
    return escape(plain[:limit]) + "…"


def fmt_ts(ts: int | None, tz: ZoneInfo) -> str:
    """Unix-время -> «21.10.2026 14:05:33 (MSK)»."""
    if ts is None:
        return "—"
    dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(tz)
    return dt.strftime("%d.%m.%Y %H:%M:%S %Z")


def fmt_date(ts: int | None, tz: ZoneInfo) -> str:
    if ts is None:
        return "—"
    return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(tz).strftime("%d.%m.%Y %H:%M")


def fmt_person(user_id: int | None, username: str | None, name: str | None) -> str:
    """«Имя @username · ID 123» с экранированием HTML."""
    parts: list[str] = []
    if name:
        parts.append(escape(name))
    if username:
        parts.append(f"@{escape(username)}")
    if not parts:
        parts.append("—")
    id_part = f" · ID <code>{user_id}</code>" if user_id is not None else ""
    return " ".join(parts) + id_part


def fmt_person_short(user_id: int | None, username: str | None, name: str | None) -> str:
    """Компактный автор для уведомления: «@username» / «Имя» / «id123»."""
    if username:
        return f"@{escape(username)}"
    if name:
        return escape(name)
    return f"id{user_id}" if user_id is not None else "—"


def fmt_chat(chat: Chat) -> str:
    """Название чата (для личного чата — имя собеседника) + ID."""
    title = chat.title or chat.full_name or ""
    username = f" @{escape(chat.username)}" if chat.username else ""
    return f"{escape(title)}{username} · ID <code>{chat.id}</code>".strip()


def full_name(first: str | None, last: str | None) -> str | None:
    name = " ".join(p for p in (first, last) if p)
    return name or None


def plan_name(lang: str | None, plan_code: str | None) -> str:
    return t(lang, f"plan_{plan_code}") if plan_code else "—"


async def safe_send(bot: Bot, chat_id: int, text: str, **kwargs) -> bool:
    """
    Отправляет сообщение, не роняя обработчик:
    - пользователь заблокировал бота -> False;
    - flood control -> ждём и пробуем ещё раз;
    - прочие ошибки -> логируем и False.
    """
    for attempt in range(3):
        try:
            await bot.send_message(chat_id, text, **kwargs)
            return True
        except TelegramRetryAfter as exc:
            log.warning("Flood control для %s: ждём %s с", chat_id, exc.retry_after)
            await asyncio.sleep(exc.retry_after + 1)
        except TelegramForbiddenError:
            log.info("Пользователь %s заблокировал бота или не начинал диалог", chat_id)
            return False
        except TelegramBadRequest as exc:
            log.warning("Не удалось отправить сообщение %s: %s", chat_id, exc)
            return False
        except TelegramNetworkError as exc:
            log.warning("Сетевая ошибка при отправке %s (попытка %s): %s", chat_id, attempt + 1, exc)
            await asyncio.sleep(2 ** attempt)
    return False


# Как отправлять сохранённое медиа по типу: (метод бота, поддерживает ли спойлер, поддерживает ли подпись)
_MEDIA_SEND = {
    "photo": ("send_photo", True, True),
    "video": ("send_video", True, True),
    "animation": ("send_animation", True, True),
    "document": ("send_document", False, True),
    "audio": ("send_audio", False, True),
    "voice": ("send_voice", False, True),
    "video_note": ("send_video_note", False, False),
    "sticker": ("send_sticker", False, False),
}
# Имя аргумента с файлом у каждого метода отправки
_MEDIA_ARG = {
    "send_photo": "photo", "send_video": "video", "send_animation": "animation",
    "send_document": "document", "send_audio": "audio", "send_voice": "voice",
    "send_video_note": "video_note", "send_sticker": "sticker",
}


def _media_integrity_ok(local_path: str | None, expected_size: int | None = None) -> bool:
    """Проверка целостности: файл существует и непустой (и совпадает размер, если известен)."""
    if not local_path or not os.path.exists(local_path):
        return False
    try:
        size = os.path.getsize(local_path)
    except OSError:
        return False
    if size == 0:
        return False
    if expected_size and size != expected_size:
        log.warning("Размер медиа %s не совпадает: %s != %s", local_path, size, expected_size)
        return False
    return True


async def download_media(bot: Bot, file_id: str, content_type: str | None, dest_dir: str,
                         name_hint: str) -> tuple[str | None, int | None]:
    """
    Скачивает оригинал медиа на диск сразу при получении.
    Возвращает (путь, размер) или (None, None) при ошибке/непройденной проверке целостности.
    """
    path = None
    try:
        file = await bot.get_file(file_id)
        ext = os.path.splitext(file.file_path or "")[1] or _EXT_BY_TYPE.get(content_type or "", "")
        os.makedirs(dest_dir, exist_ok=True)
        path = os.path.join(dest_dir, f"{name_hint}{ext}")
        await bot.download_file(file.file_path, destination=path)
        # Проверяем успешность загрузки, прежде чем считать файл сохранённым
        if not _media_integrity_ok(path, file.file_size):
            raise OSError("проверка целостности не пройдена")
    except Exception as exc:  # сеть/API/диск — ничего не роняем, останется file_id
        log.warning("Скачивание медиа %s не удалось: %s", file_id[:12], exc)
        if path:
            try:
                os.remove(path)
            except OSError:
                pass
        return None, None
    return path, os.path.getsize(path)


async def send_saved_media(bot: Bot, chat_id: int, content_type: str | None, file_id: str | None,
                           caption: str | None = None, local_path: str | None = None,
                           disable_notification: bool = False) -> bool:
    """
    Пересылает сохранённое медиа под спойлером. Сначала пытается отправить локальную
    копию (local_path), при её отсутствии/повреждении — по file_id. False, если тип
    не поддержан или Telegram уже не отдаёт файл.
    """
    if content_type not in _MEDIA_SEND:
        return False
    method_name, can_spoiler, can_caption = _MEDIA_SEND[content_type]
    method = getattr(bot, method_name)
    kwargs: dict = {"disable_notification": disable_notification}
    if can_spoiler:
        kwargs["has_spoiler"] = True
    if can_caption and caption:
        kwargs["caption"] = caption[:1024]
    # Источник: локальный файл (приоритет) либо file_id
    if _media_integrity_ok(local_path):
        source = FSInputFile(local_path)
    elif file_id:
        source = file_id
    else:
        return False
    try:
        await method(chat_id, **{_MEDIA_ARG[method_name]: source}, **kwargs)
        return True
    except TelegramForbiddenError:
        return False
    except TelegramAPIError as exc:
        log.info("Медиа %s не переслано: %s", content_type, exc)
        return False


def split_text(blocks: list[str], separator: str = "\n\n", limit: int = 4000) -> list[str]:
    """Склеивает блоки в сообщения не длиннее лимита Telegram (4096)."""
    chunks: list[str] = []
    current = ""
    for block in blocks:
        candidate = f"{current}{separator}{block}" if current else block
        if len(candidate) > limit and current:
            chunks.append(current)
            current = block
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks
