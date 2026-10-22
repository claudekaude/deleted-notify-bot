"""Фоновые задачи: истечение подписок и очистка старых метаданных."""
from __future__ import annotations

import asyncio
import logging
import os

from aiogram import Bot

from config import Config
from db import Database
from handlers.business import send_renew_reminder

log = logging.getLogger(__name__)

INTERVAL_SECONDS = 600  # раз в 10 минут


async def maintenance_loop(bot: Bot, db: Database, config: Config) -> None:
    while True:
        try:
            # 1. Истёкшие подписки -> is_active=0 + напоминание с кнопкой «💳 Купить»
            for owner_id in await db.expire_subscriptions():
                log.info("Подписка пользователя %s истекла", owner_id)
                await send_renew_reminder(bot, db, config, owner_id)

            # 2. Очистка по сроку хранения — только если RETENTION_DAYS > 0.
            #    По умолчанию (0) данные и файлы не удаляются автоматически.
            for path in await db.purge_old_messages(config.retention_days):
                try:
                    os.remove(path)
                except OSError:
                    pass
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Ошибка в фоновой задаче обслуживания")
        await asyncio.sleep(INTERVAL_SECONDS)
