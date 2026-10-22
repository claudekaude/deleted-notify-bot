"""
Middleware: регистрирует пользователя и подставляет в хендлеры его язык.

Подключается только к message / callback_query / pre_checkout_query —
то есть к событиям, где event.from_user — это сам пользователь бота.
К бизнес-событиям НЕ подключается: там from_user — собеседник владельца,
и заводить его в users не нужно.
"""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.enums import ChatType
from aiogram.types import CallbackQuery, Message, PreCheckoutQuery, TelegramObject

from db import Database
from locales import normalize_lang

log = logging.getLogger(__name__)


class UserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        db: Database = data["db"]
        user = getattr(event, "from_user", None)

        # Работаем только в личке с ботом (группы/каналы игнорируем)
        if isinstance(event, Message) and event.chat.type != ChatType.PRIVATE:
            return None

        if user is not None and isinstance(event, (Message, CallbackQuery, PreCheckoutQuery)):
            try:
                await db.upsert_user(user.id, user.username, user.first_name)
                row = await db.get_user(user.id)
            except Exception:
                log.exception("Не удалось сохранить пользователя %s", user.id)
                row = None
            # lang_chosen — язык, выбранный в боте (None, если ещё не выбран);
            # lang — язык для текстов прямо сейчас (выбранный или из настроек Telegram)
            chosen = row["language"] if row else None
            data["user_row"] = row
            data["lang_chosen"] = chosen
            data["lang"] = normalize_lang(chosen or user.language_code)

        return await handler(event, data)
