"""Сборка всех роутеров и глобальный обработчик ошибок."""
from __future__ import annotations

import logging

from aiogram import Router
from aiogram.types import ErrorEvent

from locales import t

from . import admin, business, history, menu, payments, start

log = logging.getLogger(__name__)


def setup_routers() -> Router:
    root = Router(name="root")
    # admin первым: его фильтр пропускает только ADMIN_ID, остальные идут дальше
    root.include_routers(
        admin.router,
        start.router,
        menu.router,
        history.router,
        payments.router,
        business.router,
    )

    @root.errors()
    async def on_error(event: ErrorEvent, **data) -> bool:
        """Логирует любое необработанное исключение и вежливо сообщает пользователю."""
        log.exception("Ошибка при обработке update %s", event.update.update_id, exc_info=event.exception)
        lang = data.get("lang")
        try:
            if event.update.callback_query:
                await event.update.callback_query.answer(t(lang, "error_generic"), show_alert=True)
            elif event.update.message and event.update.message.chat.type == "private":
                await event.update.message.answer(t(lang, "error_generic"))
        except Exception:
            log.debug("Не удалось сообщить пользователю об ошибке", exc_info=True)
        return True

    return root
