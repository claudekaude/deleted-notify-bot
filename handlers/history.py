"""
Раздел «История» — просмотр собственных сохранённых записей владельца.

Изоляция: все запросы идут строго по owner_user_id = id того, кто нажал кнопку,
поэтому один пользователь не может увидеть записи другого (проверка на сервере,
а не скрытием кнопок). Показываются только записи, которые бот реально получил
в бизнес-чатах этого владельца.

Навигация постраничная (LIMIT/OFFSET), есть поиск по тексту и фильтр по дате.
Состояние просмотра (запрос/фильтр/страница) хранится в FSM, чтобы не тащить
длинный поисковый запрос в callback_data.
"""
from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import Config
from db import Database, now_ts
from handlers.common import edit_or_send, menu_markup
from keyboards import MenuCb
from locales import t
from utils import fmt_ts, send_saved_media

log = logging.getLogger(__name__)
router = Router(name="history")

PAGE_SIZE = 5
PREVIEW_LEN = 40


class HistCb(CallbackData, prefix="hist"):
    """action: open/older/newer/start/search/item/close; arg — № страницы или id записи."""

    action: str
    arg: int = 0


class HistorySG(StatesGroup):
    browsing = State()   # листаем страницы
    searching = State()  # ждём текст поискового запроса


# Пресеты фильтра по дате: код -> сколько секунд назад (None = без ограничения)
DATE_PRESETS = {"all": None, "7d": 7 * 86400, "30d": 30 * 86400, "deleted": None}


async def _view(state: FSMContext) -> dict:
    """Текущие параметры просмотра из FSM с значениями по умолчанию."""
    data = await state.get_data()
    return {
        "q": data.get("hist_q"),
        "flt": data.get("hist_flt", "all"),
        "page": data.get("hist_page", 0),
    }


def _since_ts(flt: str) -> int | None:
    window = DATE_PRESETS.get(flt)
    return now_ts() - window if window else None


def _preview(lang: str, row: dict) -> str:
    """Короткое превью содержимого записи для строки списка."""
    if row.get("text"):
        text = row["text"].replace("\n", " ")
        return (text[:PREVIEW_LEN] + "…") if len(text) > PREVIEW_LEN else text
    if row.get("content_type") and row["content_type"] != "text":
        return f"[{row['content_type']}]"
    return "—"


async def _render_page(callback_or_msg, db: Database, config: Config, lang: str,
                       owner_id: int, view: dict) -> None:
    """Рисует страницу истории с кнопками навигации, поиска и фильтра."""
    flt, q, page = view["flt"], view["q"], view["page"]
    since = _since_ts(flt)
    only_deleted = flt == "deleted"
    total = await db.history_count(owner_id, q, since, only_deleted)
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    items = await db.history_page(owner_id, PAGE_SIZE, page * PAGE_SIZE, q, since, only_deleted)

    kb = InlineKeyboardBuilder()
    if total == 0:
        body = t(lang, "history_empty")
    else:
        lines = [t(lang, "history_page_header", page=page + 1, pages=pages, total=total)]
        if q:
            lines.append(t(lang, "history_filter_q", q=q))
        lines.append("")
        nums = []
        for i, row in enumerate(items, start=1):
            status = "🗑" if row["is_deleted"] else "·"
            when = fmt_ts(row["sent_at"], config.timezone)
            lines.append(f"<b>{i}.</b> {status} {when}\n    {_preview(lang, row)}")
            nums.append((str(i), row["id"]))
            kb.button(text=str(i), callback_data=HistCb(action="item", arg=row["id"]))
        kb.adjust(len(nums) or 1)
        body = "\n".join(lines)

    # Навигация по страницам
    nav = []
    if page > 0:
        nav.append(("⏮", HistCb(action="start")))
        nav.append(("🔼", HistCb(action="newer", arg=page - 1)))
    if (page + 1) < pages:
        nav.append(("🔽", HistCb(action="older", arg=page + 1)))
    for text_btn, cb in nav:
        kb.button(text=text_btn, callback_data=cb)
    # Фильтры по дате и статусу
    kb.button(text=t(lang, "btn_hist_all"), callback_data=HistCb(action="flt_all"))
    kb.button(text=t(lang, "btn_hist_7d"), callback_data=HistCb(action="flt_7d"))
    kb.button(text=t(lang, "btn_hist_30d"), callback_data=HistCb(action="flt_30d"))
    kb.button(text=t(lang, "btn_hist_deleted"), callback_data=HistCb(action="flt_deleted"))
    kb.button(text=t(lang, "btn_hist_search"), callback_data=HistCb(action="search"))
    kb.button(text=t(lang, "btn_back"), callback_data=MenuCb(action="main"))
    # Раскладка: номера (авто) + навигация + 4 фильтра + поиск/назад
    sizes = []
    if items:
        sizes.append(len(items))
    if nav:
        sizes.append(len(nav))
    sizes += [4, 2]
    kb.adjust(*sizes)

    title = t(lang, "history_title") + "\n\n" + body
    if isinstance(callback_or_msg, CallbackQuery):
        await edit_or_send(callback_or_msg, title, kb.as_markup())
    else:
        await callback_or_msg.answer(title, reply_markup=kb.as_markup(), disable_web_page_preview=True)


# ---------------------------------------------------------------- вход в раздел

@router.callback_query(MenuCb.filter(F.action == "history"))
async def on_history(callback: CallbackQuery, state: FSMContext, db: Database, config: Config, lang: str) -> None:
    await state.set_state(HistorySG.browsing)
    await state.update_data(hist_q=None, hist_flt="all", hist_page=0)
    await callback.answer()
    await _render_page(callback, db, config, lang, callback.from_user.id, await _view(state))


@router.message(Command("history"))
async def cmd_history(message: Message, state: FSMContext, db: Database, config: Config, lang: str) -> None:
    await state.set_state(HistorySG.browsing)
    await state.update_data(hist_q=None, hist_flt="all", hist_page=0)
    await _render_page(message, db, config, lang, message.from_user.id, await _view(state))


# ---------------------------------------------------------------- навигация

@router.callback_query(HistCb.filter(F.action.in_({"start", "newer", "older"})))
async def on_nav(callback: CallbackQuery, callback_data: HistCb, state: FSMContext,
                 db: Database, config: Config, lang: str) -> None:
    page = 0 if callback_data.action == "start" else callback_data.arg
    await state.update_data(hist_page=page)
    await callback.answer()
    await _render_page(callback, db, config, lang, callback.from_user.id, await _view(state))


@router.callback_query(HistCb.filter(F.action.startswith("flt_")))
async def on_filter(callback: CallbackQuery, callback_data: HistCb, state: FSMContext,
                    db: Database, config: Config, lang: str) -> None:
    flt = callback_data.action.removeprefix("flt_")
    await state.update_data(hist_flt=flt, hist_page=0)
    await callback.answer()
    await _render_page(callback, db, config, lang, callback.from_user.id, await _view(state))


# ---------------------------------------------------------------- поиск

@router.callback_query(HistCb.filter(F.action == "search"))
async def on_search_start(callback: CallbackQuery, state: FSMContext, lang: str) -> None:
    await state.set_state(HistorySG.searching)
    await callback.answer()
    await edit_or_send(callback, t(lang, "history_search_prompt"))


@router.message(HistorySG.searching, F.text)
async def on_search_query(message: Message, state: FSMContext, db: Database, config: Config, lang: str) -> None:
    query = message.text.strip()
    await state.set_state(HistorySG.browsing)
    await state.update_data(hist_q=query or None, hist_page=0)
    await _render_page(message, db, config, lang, message.from_user.id, await _view(state))


# ---------------------------------------------------------------- просмотр одной записи

@router.callback_query(HistCb.filter(F.action == "item"))
async def on_item(callback: CallbackQuery, callback_data: HistCb, bot: Bot,
                  db: Database, config: Config, lang: str) -> None:
    owner_id = callback.from_user.id
    row = await db.history_item(owner_id, callback_data.arg)  # изоляция: только свои записи
    await callback.answer()
    if row is None:
        await bot.send_message(owner_id, t(lang, "history_item_gone"))
        return

    from html import escape
    status = t(lang, "history_status_deleted") if row["is_deleted"] else t(lang, "history_status_active")
    lines = [t(lang, "history_item_title")]
    lines.append(t(lang, "history_item_when", when=fmt_ts(row["sent_at"], config.timezone), status=status))
    if row["is_deleted"] and row["deleted_at"]:
        lines.append(t(lang, "history_item_deleted", when=fmt_ts(row["deleted_at"], config.timezone)))
    if row.get("forward_from"):
        from html import escape as _esc
        lines.append(t(lang, "fwd_from", src=_esc(row["forward_from"])))
    if row["text"]:
        lines.append(t(lang, "history_item_text", text=escape(row["text"][:3500])))
    elif row["content_type"] and row["content_type"] != "text":
        lines.append(t(lang, "history_item_media", type=escape(row["content_type"])))
    await bot.send_message(owner_id, "\n".join(lines), disable_web_page_preview=True)

    # Если есть сохранённое медиа — присылаем его по file_id (под спойлером)
    if row.get("file_id"):
        ok = await send_saved_media(bot, owner_id, row["content_type"], row["file_id"],
                                    t(lang, "history_item_media_caption"))
        if not ok:
            await bot.send_message(owner_id, t(lang, "history_item_media_gone"))
