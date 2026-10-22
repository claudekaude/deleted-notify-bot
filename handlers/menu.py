"""Кнопки главного меню: статус, язык, помощь, стоп/возобновить."""
from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from config import Config
from db import Database
from handlers.common import build_status, edit_or_send, get_bot_username, menu_markup
from keyboards import MenuCb, back_kb, connect_kb, language_kb, settings_kb, status_kb
from locales import t

log = logging.getLogger(__name__)
router = Router(name="menu")


async def _help_text(bot: Bot, config: Config, lang: str) -> str:
    return t(lang, "help", bot_username=await get_bot_username(bot),
             retention=config.retention_days, privacy=t(lang, "privacy"))


# ---------------------------------------------------------------- команды-дубли кнопок

@router.message(Command("help"))
async def cmd_help(message: Message, bot: Bot, config: Config, lang: str) -> None:
    await message.answer(await _help_text(bot, config, lang), reply_markup=back_kb(lang),
                         disable_web_page_preview=True)


@router.message(Command("status"))
async def cmd_status(message: Message, bot: Bot, db: Database, config: Config, lang: str) -> None:
    await message.answer(await build_status(bot, db, config, message.from_user.id, lang),
                         reply_markup=status_kb(lang))


# ---------------------------------------------------------------- callback-кнопки

@router.callback_query(MenuCb.filter(F.action == "main"))
async def on_main(callback: CallbackQuery, db: Database, lang: str) -> None:
    await callback.answer()
    await edit_or_send(callback, t(lang, "menu_title"), await menu_markup(db, callback.from_user.id, lang))


@router.callback_query(MenuCb.filter(F.action == "status"))
async def on_status(callback: CallbackQuery, bot: Bot, db: Database, config: Config, lang: str) -> None:
    await callback.answer()
    await edit_or_send(callback, await build_status(bot, db, config, callback.from_user.id, lang), status_kb(lang))


@router.callback_query(MenuCb.filter(F.action == "connect"))
async def on_connect(callback: CallbackQuery, bot: Bot, lang: str) -> None:
    await callback.answer()
    username = await get_bot_username(bot)
    await edit_or_send(callback, t(lang, "connect_guide", bot_username=username), connect_kb(lang, username))


@router.message(Command("connect"))
async def cmd_connect(message: Message, bot: Bot, lang: str) -> None:
    username = await get_bot_username(bot)
    await message.answer(t(lang, "connect_guide", bot_username=username),
                         reply_markup=connect_kb(lang, username), disable_web_page_preview=True)


@router.callback_query(MenuCb.filter(F.action == "settings"))
async def on_settings(callback: CallbackQuery, lang: str) -> None:
    await callback.answer()
    await edit_or_send(callback, t(lang, "settings_title"), settings_kb(lang))


@router.message(Command("settings"))
async def cmd_settings(message: Message, lang: str) -> None:
    await message.answer(t(lang, "settings_title"), reply_markup=settings_kb(lang))


@router.callback_query(MenuCb.filter(F.action == "lang"))
async def on_lang(callback: CallbackQuery, lang: str) -> None:
    # Выбор языка доступен в любой момент из «Настроек»
    await callback.answer()
    await edit_or_send(callback, t(lang, "choose_language"), language_kb())


@router.callback_query(MenuCb.filter(F.action == "help"))
async def on_help(callback: CallbackQuery, bot: Bot, config: Config, lang: str) -> None:
    await callback.answer()
    await edit_or_send(callback, await _help_text(bot, config, lang), back_kb(lang))
