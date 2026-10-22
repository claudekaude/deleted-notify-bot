"""
Конфигурация бота.

Все настройки читаются из переменных окружения (файл .env).
Обязательные: BOT_TOKEN, ADMIN_ID. Остальные имеют значения по умолчанию.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

load_dotenv()


class ConfigError(RuntimeError):
    """Ошибка конфигурации (.env)."""


@dataclass(frozen=True)
class Plan:
    """Тариф подписки."""

    code: str           # внутренний код тарифа (используется в callback и payload)
    days: int | None    # длительность в днях; None — навсегда
    stars: int          # цена в Telegram Stars (XTR)


@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_id: int                 # главный владелец (для совместимости)
    admin_ids: frozenset[int]     # все, кому разрешены админ-команды (владелец + ADMIN_IDS)
    db_path: str
    timezone: ZoneInfo
    trial_days: int
    # Сколько дней хранить метаданные сообщений (после — удаляются автоматически)
    retention_days: int
    # Как часто (в часах) повторять напоминание об истёкшей подписке
    reminder_interval_hours: int
    # Прокси для доступа к api.telegram.org (http://... или socks5://...), если он заблокирован
    proxy_url: str | None
    # Сохранять ли текст/подписи входящих сообщений, чтобы показать их при удалении
    store_message_text: bool
    # Скачивать ли медиафайлы на диск сразу при получении
    store_media: bool
    # Папка для сохранённых медиафайлов
    media_dir: str
    plans: dict[str, Plan] = field(default_factory=dict)


def _int_env(name: str, default: int | None = None) -> int:
    """Читает целочисленную переменную окружения с понятной ошибкой."""
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        if default is None:
            raise ConfigError(f"Переменная окружения {name} не задана (см. .env.example)")
        return default
    try:
        return int(raw.strip())
    except ValueError as exc:
        raise ConfigError(f"Переменная окружения {name} должна быть целым числом, получено: {raw!r}") from exc


def load_config() -> Config:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise ConfigError("BOT_TOKEN не задан. Скопируйте .env.example в .env и укажите токен от @BotFather")

    tz_name = os.getenv("TIMEZONE", "Europe/Moscow").strip() or "UTC"
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:
        raise ConfigError(f"Неизвестный часовой пояс TIMEZONE={tz_name!r}") from exc

    # Тарифы: длительность фиксирована, цена настраивается через .env.
    # Базовый — 30 дней. Длинные тарифы дешевле в пересчёте на месяц (скидка растёт).
    plans = {
        "m1": Plan(code="m1", days=30, stars=_int_env("PRICE_30D", 200)),
        "m3": Plan(code="m3", days=90, stars=_int_env("PRICE_90D", 500)),
        "y1": Plan(code="y1", days=365, stars=_int_env("PRICE_365D", 1600)),
    }
    for plan in plans.values():
        if plan.stars < 1:
            raise ConfigError(f"Цена тарифа {plan.code} должна быть >= 1 звезды")

    # Список администраторов: главный ADMIN_ID + необязательные ADMIN_IDS через запятую
    admin_id = _int_env("ADMIN_ID")
    admin_ids = {admin_id}
    for part in os.getenv("ADMIN_IDS", "").replace(";", ",").split(","):
        part = part.strip()
        if part:
            try:
                admin_ids.add(int(part))
            except ValueError as exc:
                raise ConfigError(f"ADMIN_IDS содержит нечисловое значение: {part!r}") from exc

    return Config(
        bot_token=token,
        admin_id=admin_id,
        admin_ids=frozenset(admin_ids),
        db_path=os.getenv("DB_PATH", "data/bot.db").strip() or "data/bot.db",
        timezone=tz,
        trial_days=_int_env("TRIAL_DAYS", 7),
        retention_days=_int_env("RETENTION_DAYS", 0),  # 0 = хранить бессрочно (не удалять автоматически)
        reminder_interval_hours=_int_env("REMINDER_INTERVAL_HOURS", 24),
        proxy_url=os.getenv("PROXY_URL", "").strip() or None,
        store_message_text=os.getenv("STORE_MESSAGE_TEXT", "1").strip().lower() not in ("0", "false", "no", ""),
        store_media=os.getenv("STORE_MEDIA", "1").strip().lower() not in ("0", "false", "no", ""),
        media_dir=os.getenv("MEDIA_DIR", "data/media").strip() or "data/media",
        plans=plans,
    )
