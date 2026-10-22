"""/start и выбор языка."""
from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from config import Config
from db import Database
from handlers.common import edit_or_send, menu_markup, onboard
from keyboards import LangCb, language_kb
from locales import LANGUAGES, t

log = logging.getLogger(__name__)
router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot, db: Database, config: Config,
                    lang: str, lang_chosen: str | None) -> None:
    # Язык ещё не выбран — сначала предлагаем выбрать
    if lang_chosen is None:
        await message.answer(t(lang, "choose_language"), reply_markup=language_kb())
        return

    for text in await onboard(bot, db, config, message.from_user, lang):
        await message.answer(text, disable_web_page_preview=True)
    await message.answer(t(lang, "menu_title"), reply_markup=await menu_markup(db, message.from_user.id, lang))


@router.message(Command("menu"))
async def cmd_menu(message: Message, db: Database, lang: str) -> None:
    await message.answer(t(lang, "menu_title"), reply_markup=await menu_markup(db, message.from_user.id, lang))


@router.message(Command("language", "lang"))
async def cmd_language(message: Message, lang: str) -> None:
    await message.answer(t(lang, "choose_language"), reply_markup=language_kb())


@router.callback_query(LangCb.filter(F.code.in_(LANGUAGES.keys())))
async def on_language(callback: CallbackQuery, callback_data: LangCb, bot: Bot, db: Database,
                      config: Config, lang_chosen: str | None) -> None:
    new_lang = callback_data.code
    first_time = lang_chosen is None
    await db.set_language(callback.from_user.id, new_lang)
    await callback.answer(t(new_lang, "language_set"))

    if first_time:
        # Первый выбор языка — это продолжение /start: приветствие + пробный период + меню
        texts = await onboard(bot, db, config, callback.from_user, new_lang)
        await edit_or_send(callback, texts[0])
        for text in texts[1:]:
            await bot.send_message(callback.from_user.id, text)
        await bot.send_message(callback.from_user.id, t(new_lang, "menu_title"),
                               reply_markup=await menu_markup(db, callback.from_user.id, new_lang))
    else:
        await edit_or_send(callback, t(new_lang, "menu_title"),
                           await menu_markup(db, callback.from_user.id, new_lang))
