"""
Локализация.

Использование:
    from locales import t
    t("ru", "welcome", name="Иван")

Если ключа нет в выбранном языке — берётся русский, если нет и там — сам ключ.
"""
from __future__ import annotations

import logging

from . import en, ru

log = logging.getLogger(__name__)

DEFAULT_LANG = "ru"
LANGUAGES: dict[str, dict[str, str]] = {
    "ru": ru.TEXTS,
    "en": en.TEXTS,
}


def normalize_lang(lang: str | None) -> str:
    """Приводит код языка к поддерживаемому (en-US -> en, неизвестный -> ru)."""
    if not lang:
        return DEFAULT_LANG
    code = lang.lower().split("-")[0]
    return code if code in LANGUAGES else DEFAULT_LANG


def t(lang: str | None, key: str, **kwargs: object) -> str:
    texts = LANGUAGES.get(normalize_lang(lang), LANGUAGES[DEFAULT_LANG])
    template = texts.get(key) or LANGUAGES[DEFAULT_LANG].get(key)
    if template is None:
        log.warning("Нет перевода для ключа %r", key)
        return key
    try:
        return template.format(**kwargs) if kwargs else template
    except (KeyError, IndexError, ValueError):
        log.exception("Ошибка форматирования ключа %r", key)
        return template
