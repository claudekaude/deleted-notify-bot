"""Inline-клавиатуры и фабрики callback_data."""
from __future__ import annotations

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import Plan
from locales import t


class MenuCb(CallbackData, prefix="menu"):
    """Действия главного меню: main, status, buy, lang, help, stop, stop_yes, resume."""

    action: str


class LangCb(CallbackData, prefix="lang"):
    code: str


class BuyCb(CallbackData, prefix="buy"):
    plan: str


def language_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🇷🇺 Русский", callback_data=LangCb(code="ru"))
    kb.button(text="🇬🇧 English", callback_data=LangCb(code="en"))
    kb.adjust(2)
    return kb.as_markup()


def main_menu_kb(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "btn_status"), callback_data=MenuCb(action="status"))
    kb.button(text=t(lang, "btn_history"), callback_data=MenuCb(action="history"))
    kb.button(text=t(lang, "btn_buy"), callback_data=MenuCb(action="buy"))
    kb.button(text=t(lang, "btn_connect"), callback_data=MenuCb(action="connect"))
    kb.button(text=t(lang, "btn_settings"), callback_data=MenuCb(action="settings"))
    kb.adjust(2, 2, 1)
    return kb.as_markup()


def settings_kb(lang: str) -> InlineKeyboardMarkup:
    """Настройки: уведомления, язык, экспорт, помощь, назад."""
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "btn_notifs"), callback_data=MenuCb(action="notif"))
    kb.button(text=t(lang, "btn_lang"), callback_data=MenuCb(action="lang"))
    kb.button(text=t(lang, "btn_export"), callback_data=MenuCb(action="export"))
    kb.button(text=t(lang, "btn_help"), callback_data=MenuCb(action="help"))
    kb.button(text=t(lang, "btn_back"), callback_data=MenuCb(action="main"))
    kb.adjust(1)
    return kb.as_markup()


def notif_kb(lang: str, prefs: dict) -> InlineKeyboardMarkup:
    """Переключатели уведомлений: удаления / правки / тихий режим (с индикатором вкл/выкл)."""
    def sw(val: int) -> str:
        return t(lang, "sw_on") if val else t(lang, "sw_off")

    kb = InlineKeyboardBuilder()
    kb.button(text=f"{t(lang, 'nt_deleted')}  {sw(prefs['notify_deleted'])}",
              callback_data=MenuCb(action="nt_deleted"))
    kb.button(text=f"{t(lang, 'nt_edited')}  {sw(prefs['notify_edited'])}",
              callback_data=MenuCb(action="nt_edited"))
    kb.button(text=f"{t(lang, 'nt_silent')}  {sw(prefs['silent_mode'])}",
              callback_data=MenuCb(action="nt_silent"))
    kb.button(text=t(lang, "btn_back"), callback_data=MenuCb(action="settings"))
    kb.adjust(1)
    return kb.as_markup()


def back_kb(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "btn_back"), callback_data=MenuCb(action="main"))
    return kb.as_markup()


def connect_kb(lang: str, bot_username: str) -> InlineKeyboardMarkup:
    """Экран подключения: кнопка открытия профиля бота + назад."""
    kb = InlineKeyboardBuilder()
    # Прямого перехода к экрану «Чат-боты» в Telegram нет — открываем профиль бота (ближайший вариант)
    kb.button(text=t(lang, "btn_connect_open"), url=f"https://t.me/{bot_username}")
    kb.button(text=t(lang, "btn_back"), callback_data=MenuCb(action="main"))
    kb.adjust(1)
    return kb.as_markup()


def status_kb(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "btn_buy"), callback_data=MenuCb(action="buy"))
    kb.button(text=t(lang, "btn_back"), callback_data=MenuCb(action="main"))
    kb.adjust(1)
    return kb.as_markup()


def plans_kb(lang: str, plans: dict[str, Plan]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for plan in plans.values():
        kb.button(
            text=t(lang, "plan_button", name=t(lang, f"plan_{plan.code}"), stars=plan.stars),
            callback_data=BuyCb(plan=plan.code),
        )
    kb.button(text=t(lang, "btn_back"), callback_data=MenuCb(action="main"))
    kb.adjust(1)
    return kb.as_markup()


def buy_kb(lang: str) -> InlineKeyboardMarkup:
    """Кнопка «💳 Купить» для напоминаний об истёкшей подписке."""
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "btn_buy_short"), callback_data=MenuCb(action="buy"))
    return kb.as_markup()
