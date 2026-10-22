"""Кнопки главного меню: статус, подключение, настройки (уведомления/язык/экспорт)."""
from __future__ import annotations

import logging
import os

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, FSInputFile, Message

from config import Config
from db import Database
from export import build_export
from handlers.common import build_status, edit_or_send, get_bot_username, menu_markup
from keyboards import MenuCb, back_kb, connect_kb, language_kb, notif_kb, settings_kb, status_kb
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


# Соответствие кнопки -> поле настройки в БД
_PREF_ACTIONS = {"nt_deleted": "notify_deleted", "nt_edited": "notify_edited", "nt_silent": "silent_mode"}


@router.callback_query(MenuCb.filter(F.action == "notif"))
async def on_notif(callback: CallbackQuery, db: Database, lang: str) -> None:
    await callback.answer()
    prefs = await db.get_prefs(callback.from_user.id)
    await edit_or_send(callback, t(lang, "notif_title"), notif_kb(lang, prefs))


@router.callback_query(MenuCb.filter(F.action.in_(_PREF_ACTIONS)))
async def on_toggle_pref(callback: CallbackQuery, callback_data: MenuCb, db: Database, lang: str) -> None:
    await db.toggle_pref(callback.from_user.id, _PREF_ACTIONS[callback_data.action])
    await callback.answer()
    prefs = await db.get_prefs(callback.from_user.id)
    await edit_or_send(callback, t(lang, "notif_title"), notif_kb(lang, prefs))


@router.callback_query(MenuCb.filter(F.action == "export"))
async def on_export(callback: CallbackQuery, db: Database, config: Config, lang: str) -> None:
    await callback.answer(t(lang, "export_building"))
    user_id = callback.from_user.id
    try:
        export_dir = os.path.join(os.path.dirname(config.db_path) or ".", "exports")
        result = await build_export(db, user_id, config.timezone, export_dir)
    except Exception:
        log.exception("Ошибка экспорта для %s", user_id)
        await callback.bot.send_message(user_id, t(lang, "export_error"))
        return
    if result is None:
        await callback.bot.send_message(user_id, t(lang, "export_empty"))
        return
    zip_path, count = result
    try:
        await callback.bot.send_document(user_id, FSInputFile(zip_path),
                                         caption=t(lang, "export_caption", count=count))
    finally:
        try:
            os.remove(zip_path)  # отданный архив на диске не храним
        except OSError:
            pass


@router.message(Command("export"))
async def cmd_export(message: Message, db: Database, config: Config, lang: str) -> None:
    export_dir = os.path.join(os.path.dirname(config.db_path) or ".", "exports")
    result = await build_export(db, message.from_user.id, config.timezone, export_dir)
    if result is None:
        await message.answer(t(lang, "export_empty"))
        return
    zip_path, count = result
    try:
        await message.answer_document(FSInputFile(zip_path), caption=t(lang, "export_caption", count=count))
    finally:
        try:
            os.remove(zip_path)
        except OSError:
            pass


@router.callback_query(MenuCb.filter(F.action == "lang"))
async def on_lang(callback: CallbackQuery, lang: str) -> None:
    # Выбор языка доступен в любой момент из «Настроек»
    await callback.answer()
    await edit_or_send(callback, t(lang, "choose_language"), language_kb())


@router.callback_query(MenuCb.filter(F.action == "help"))
async def on_help(callback: CallbackQuery, bot: Bot, config: Config, lang: str) -> None:
    await callback.answer()
    await edit_or_send(callback, await _help_text(bot, config, lang), back_kb(lang))
