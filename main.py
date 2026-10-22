"""
Точка входа. Запуск: python main.py

Бот работает через long polling и явно запрашивает бизнес-обновления
(business_connection, business_message, deleted_business_messages).
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramNetworkError, TelegramUnauthorizedError
from aiogram.types import BotCommand
from aiohttp_socks import ProxyConnectionError, ProxyError, ProxyTimeoutError

from config import ConfigError, load_config
from db import Database
from handlers import setup_routers
from middlewares import UserMiddleware
from tasks import maintenance_loop

# Типы обновлений, которые бот получает. Бизнес-события по умолчанию НЕ приходят,
# поэтому перечисляем их явно.
ALLOWED_UPDATES = [
    "message",                    # команды, successful_payment, refunded_payment
    "callback_query",             # inline-кнопки
    "pre_checkout_query",         # подтверждение оплаты звёздами
    "business_connection",        # подключение/отключение бота к аккаунту
    "business_message",           # новые сообщения в бизнес-чатах (метаданные + текст)
    "edited_business_message",    # правки сообщений — чтобы хранить актуальный текст
    "deleted_business_messages",  # удаление сообщений в бизнес-чатах
]


async def set_commands(bot: Bot) -> None:
    await bot.set_my_commands([
        BotCommand(command="start", description="Запуск / Start"),
        BotCommand(command="menu", description="Меню / Menu"),
        BotCommand(command="status", description="Статус / Status"),
        BotCommand(command="history", description="История / History"),
        BotCommand(command="buy", description="Купить подписку / Buy"),
        BotCommand(command="connect", description="Подключить / Connect"),
        BotCommand(command="settings", description="Настройки / Settings"),
        BotCommand(command="help", description="Помощь / Help"),
        BotCommand(command="paysupport", description="Поддержка по оплате / Payment support"),
    ])


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        stream=sys.stdout,
    )
    log = logging.getLogger("main")

    config = load_config()
    db = Database(config.db_path)
    await db.connect()

    # Если задан PROXY_URL — все запросы к Telegram идут через прокси
    session = AiohttpSession(proxy=config.proxy_url) if config.proxy_url else None
    bot = Bot(token=config.bot_token, session=session,
              default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True))
    # MemoryStorage хранит шаги поиска в «Истории» (сбрасывается при перезапуске)
    dp = Dispatcher(storage=MemoryStorage())
    # Зависимости, доступные в хендлерах по имени аргумента: db, config
    dp["db"] = db
    dp["config"] = config

    user_mw = UserMiddleware()
    dp.message.outer_middleware(user_mw)
    dp.callback_query.outer_middleware(user_mw)
    dp.pre_checkout_query.outer_middleware(user_mw)

    dp.include_router(setup_routers())

    maintenance: asyncio.Task | None = None
    try:
        me = await bot.get_me()
        log.info("Бот @%s (id=%s) запускается", me.username, me.id)
        if not me.can_connect_to_business:
            log.warning("Business Mode выключен! Включите его в @BotFather: "
                        "Bot Settings -> Business Mode -> Turn on")
        await set_commands(bot)
        maintenance = asyncio.create_task(maintenance_loop(bot, db, config))
        await dp.start_polling(bot, allowed_updates=ALLOWED_UPDATES)
    finally:
        if maintenance:
            maintenance.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await maintenance
        await db.close()
        await bot.session.close()
        log.info("Бот остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
    except ConfigError as exc:
        # Ошибки конфигурации выводим без трейсбэка
        print(f"Ошибка запуска: {exc}", file=sys.stderr)
        sys.exit(1)
    except TelegramNetworkError as exc:
        print("Ошибка запуска: нет связи с api.telegram.org.\n"
              "Скорее всего, доступ заблокирован провайдером. Включите VPN или укажите PROXY_URL в .env.\n"
              f"Детали: {exc}", file=sys.stderr)
        sys.exit(1)
    except (ProxyError, ProxyConnectionError, ProxyTimeoutError, OSError) as exc:
        # Ошибки подключения к прокси из PROXY_URL
        print("Ошибка запуска: не удалось подключиться к прокси из PROXY_URL.\n"
              "Проверьте адрес, порт, логин и пароль прокси.\n"
              f"Детали: {exc}", file=sys.stderr)
        sys.exit(1)
    except TelegramUnauthorizedError:
        print("Ошибка запуска: неверный BOT_TOKEN (проверьте токен в @BotFather)", file=sys.stderr)
        sys.exit(1)
