"""
Работа с базой данных SQLite (aiosqlite).

Таблица messages хранит метаданные сообщений (id, чат, автор, время) и, если
включено STORE_MESSAGE_TEXT, их текст/подпись. Telegram в событии
deleted_business_messages присылает лишь номера сообщений, поэтому всё нужное
для уведомления сохраняется в момент получения. Медиафайлы не скачиваются и не
хранятся — только тип содержимого (content_type).

Схема (все данные привязаны к owner_user_id — владельцу бизнес-аккаунта):

    users          — пользователи бота (владельцы), язык, флаг уведомлений
        user_id PK, username, first_name, language, notifications_enabled,
        trial_used, created_at, updated_at

    subscriptions  — подписка владельца (1:1 с users)
        owner_user_id PK -> users.user_id, plan, expires_at (NULL = навсегда),
        is_active, last_reminder_at, updated_at

    connections    — бизнес-подключения (N:1 к users)
        business_connection_id PK, owner_user_id -> users.user_id,
        user_chat_id, is_enabled, can_reply, created_at, updated_at

    messages       — метаданные и текст сообщений (N:1 к users и connections)
        id PK, owner_user_id -> users.user_id,
        business_connection_id -> connections.business_connection_id,
        chat_id, message_id, from_user_id, from_username, from_name,
        content_type, text, sent_at, saved_at;
        UNIQUE(owner_user_id, chat_id, message_id)

    payments       — платежи звёздами (нужны для возвратов refundStarPayment)
        id PK, owner_user_id -> users.user_id, plan, amount, currency,
        telegram_payment_charge_id UNIQUE, status, created_at, refunded_at
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Iterable

import aiosqlite

log = logging.getLogger(__name__)

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    user_id               INTEGER PRIMARY KEY,
    username              TEXT,
    first_name            TEXT,
    language              TEXT,                 -- 'ru' / 'en', NULL пока не выбран
    notifications_enabled INTEGER NOT NULL DEFAULT 1,
    notify_deleted        INTEGER NOT NULL DEFAULT 1,  -- уведомлять об удалениях
    notify_edited         INTEGER NOT NULL DEFAULT 1,  -- уведомлять о правках
    silent_mode           INTEGER NOT NULL DEFAULT 0,  -- доставлять без звука
    trial_used            INTEGER NOT NULL DEFAULT 0,
    created_at            INTEGER NOT NULL,
    updated_at            INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS subscriptions (
    owner_user_id    INTEGER PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    plan             TEXT    NOT NULL,          -- trial / m1 / m3 / life / grant
    expires_at       INTEGER,                   -- unix-время; NULL = навсегда
    is_active        INTEGER NOT NULL DEFAULT 1,
    last_reminder_at INTEGER,
    updated_at       INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS connections (
    business_connection_id TEXT PRIMARY KEY,
    owner_user_id          INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    user_chat_id           INTEGER NOT NULL,
    is_enabled             INTEGER NOT NULL,
    can_reply              INTEGER NOT NULL DEFAULT 0,
    created_at             INTEGER NOT NULL,
    updated_at             INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_connections_owner ON connections(owner_user_id);

-- Метаданные + текст/подпись (медиафайлы не хранятся). Стирается после уведомления.
CREATE TABLE IF NOT EXISTS messages (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_user_id          INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    business_connection_id TEXT    NOT NULL,
    chat_id                INTEGER NOT NULL,
    message_id             INTEGER NOT NULL,
    from_user_id           INTEGER,
    from_username          TEXT,
    from_name              TEXT,
    content_type           TEXT,                 -- text / photo / video / ... (без самого файла)
    text                   TEXT,                 -- текст или подпись; NULL, если хранение выключено
    file_id                TEXT,                 -- file_id медиа (ссылка Telegram)
    media_path             TEXT,                 -- путь к скачанному файлу на диске
    media_size             INTEGER,              -- размер файла (для проверки целостности)
    forward_from           TEXT,                 -- источник пересылки (если сообщение переслано)
    is_deleted             INTEGER NOT NULL DEFAULT 0,  -- 1 = сообщение удалено собеседником
    deleted_at             INTEGER,              -- когда замечено удаление
    sent_at                INTEGER NOT NULL,
    saved_at               INTEGER NOT NULL,
    UNIQUE (owner_user_id, chat_id, message_id)
);
CREATE INDEX IF NOT EXISTS idx_messages_saved ON messages(saved_at);
-- Индекс для раздела «История»: быстрый постраничный вывод по владельцу
CREATE INDEX IF NOT EXISTS idx_messages_owner_sent ON messages(owner_user_id, sent_at);

-- История изменений сообщений: по одной строке на каждую правку (старое -> новое)
CREATE TABLE IF NOT EXISTS message_edits (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    chat_id       INTEGER NOT NULL,
    message_id    INTEGER NOT NULL,
    old_text      TEXT,              -- версия до правки (HTML; NULL если не было в базе)
    new_text      TEXT,              -- версия после правки (HTML)
    edited_at     INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_edits_msg ON message_edits(owner_user_id, chat_id, message_id);

CREATE TABLE IF NOT EXISTS payments (
    id                         INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_user_id              INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    plan                       TEXT    NOT NULL,
    amount                     INTEGER NOT NULL,
    currency                   TEXT    NOT NULL,
    telegram_payment_charge_id TEXT    NOT NULL UNIQUE,
    status                     TEXT    NOT NULL DEFAULT 'paid',  -- paid / refunded
    created_at                 INTEGER NOT NULL,
    refunded_at                INTEGER
);
CREATE INDEX IF NOT EXISTS idx_payments_owner ON payments(owner_user_id);
"""


def now_ts() -> int:
    return int(time.time())


class Database:
    """Тонкая асинхронная обёртка над одним соединением SQLite."""

    def __init__(self, path: str) -> None:
        self.path = path
        self._conn: aiosqlite.Connection | None = None
        # Защищает операции «прочитать-изменить-записать» (продление подписки и т.п.)
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------ служебное

    async def connect(self) -> None:
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode = WAL")
        await self._conn.executescript(SCHEMA)
        await self._migrate()
        await self._conn.commit()
        log.info("База данных открыта: %s", self.path)

    async def _migrate(self) -> None:
        """Добавляет новые колонки в базу, созданную старой версией бота."""
        # users: настройки уведомлений
        async with self.conn.execute("PRAGMA table_info(users)") as cur:
            ucols = {row[1] for row in await cur.fetchall()}
        for name in ("notify_deleted", "notify_edited", "silent_mode"):
            if name not in ucols:
                default = "0" if name == "silent_mode" else "1"
                await self.conn.execute(
                    f"ALTER TABLE users ADD COLUMN {name} INTEGER NOT NULL DEFAULT {default}")
                log.info("Миграция: добавлена колонка users.%s", name)
        async with self.conn.execute("PRAGMA table_info(messages)") as cur:
            columns = {row[1] for row in await cur.fetchall()}
        # name -> тип колонки
        new_cols = {"content_type": "TEXT", "text": "TEXT", "file_id": "TEXT",
                    "is_deleted": "INTEGER NOT NULL DEFAULT 0", "deleted_at": "INTEGER",
                    "media_path": "TEXT", "media_size": "INTEGER", "forward_from": "TEXT"}
        for name, coltype in new_cols.items():
            if name not in columns:
                await self.conn.execute(f"ALTER TABLE messages ADD COLUMN {name} {coltype}")
                log.info("Миграция: добавлена колонка messages.%s", name)

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("База данных не подключена: вызовите connect()")
        return self._conn

    async def _fetchone(self, sql: str, params: Iterable[Any] = ()) -> dict | None:
        async with self.conn.execute(sql, tuple(params)) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    async def _fetchall(self, sql: str, params: Iterable[Any] = ()) -> list[dict]:
        async with self.conn.execute(sql, tuple(params)) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def _execute(self, sql: str, params: Iterable[Any] = ()) -> int:
        """Выполняет запрос с коммитом, возвращает количество изменённых строк."""
        cur = await self.conn.execute(sql, tuple(params))
        await self.conn.commit()
        return cur.rowcount

    # ------------------------------------------------------------------ users

    async def upsert_user(self, user_id: int, username: str | None, first_name: str | None) -> None:
        ts = now_ts()
        await self._execute(
            """
            INSERT INTO users (user_id, username, first_name, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                updated_at = excluded.updated_at
            """,
            (user_id, username, first_name, ts, ts),
        )

    async def get_user(self, user_id: int) -> dict | None:
        return await self._fetchone("SELECT * FROM users WHERE user_id = ?", (user_id,))

    async def get_language(self, user_id: int) -> str | None:
        row = await self._fetchone("SELECT language FROM users WHERE user_id = ?", (user_id,))
        return row["language"] if row else None

    async def set_language(self, user_id: int, language: str) -> None:
        await self._execute(
            "UPDATE users SET language = ?, updated_at = ? WHERE user_id = ?",
            (language, now_ts(), user_id),
        )

    async def set_notifications(self, user_id: int, enabled: bool) -> None:
        await self._execute(
            "UPDATE users SET notifications_enabled = ?, updated_at = ? WHERE user_id = ?",
            (int(enabled), now_ts(), user_id),
        )

    # Разрешённые для переключения настройки уведомлений
    NOTIFY_PREFS = ("notify_deleted", "notify_edited", "silent_mode")

    async def get_prefs(self, user_id: int) -> dict:
        """Настройки уведомлений пользователя (с безопасными значениями по умолчанию)."""
        row = await self._fetchone(
            "SELECT notify_deleted, notify_edited, silent_mode FROM users WHERE user_id = ?", (user_id,))
        if row is None:
            return {"notify_deleted": 1, "notify_edited": 1, "silent_mode": 0}
        return dict(row)

    async def toggle_pref(self, user_id: int, key: str) -> int:
        """Переключает булеву настройку (0/1). Возвращает новое значение."""
        if key not in self.NOTIFY_PREFS:
            raise ValueError(f"Недопустимая настройка: {key}")
        prefs = await self.get_prefs(user_id)
        new_val = 0 if prefs.get(key) else 1
        await self._execute(
            f"UPDATE users SET {key} = ?, updated_at = ? WHERE user_id = ?",
            (new_val, now_ts(), user_id),
        )
        return new_val

    # ------------------------------------------------------------------ subscriptions

    async def get_subscription(self, user_id: int) -> dict | None:
        return await self._fetchone("SELECT * FROM subscriptions WHERE owner_user_id = ?", (user_id,))

    @staticmethod
    def subscription_is_active(sub: dict | None, ts: int | None = None) -> bool:
        """Подписка активна, если флаг is_active=1 и срок не истёк (NULL = навсегда)."""
        if not sub or not sub["is_active"]:
            return False
        if sub["expires_at"] is None:
            return True
        return sub["expires_at"] > (ts or now_ts())

    async def has_active_subscription(self, user_id: int) -> bool:
        return self.subscription_is_active(await self.get_subscription(user_id))

    async def start_trial_if_needed(self, user_id: int, days: int) -> bool:
        """Выдаёт пробный период один раз на пользователя. True — если выдан сейчас."""
        async with self._lock:
            user = await self.get_user(user_id)
            if user is None or user["trial_used"]:
                return False
            ts = now_ts()
            existing = await self.get_subscription(user_id)
            if existing is None:
                await self.conn.execute(
                    """
                    INSERT INTO subscriptions (owner_user_id, plan, expires_at, is_active, updated_at)
                    VALUES (?, 'trial', ?, 1, ?)
                    """,
                    (user_id, ts + days * 86400, ts),
                )
            await self.conn.execute("UPDATE users SET trial_used = 1 WHERE user_id = ?", (user_id,))
            await self.conn.commit()
            return existing is None

    async def extend_subscription(self, user_id: int, plan: str, days: int | None) -> int | None:
        """
        Продлевает подписку на days дней (None — навсегда).
        Если подписка ещё активна, дни добавляются к текущей дате окончания.
        Возвращает новую дату окончания (None = навсегда).
        """
        async with self._lock:
            ts = now_ts()
            sub = await self.get_subscription(user_id)
            if days is None:
                new_expires = None
            elif sub and self.subscription_is_active(sub, ts) and sub["expires_at"] is None:
                new_expires = None  # уже «навсегда» — оставляем как есть
            else:
                base = ts
                if sub and self.subscription_is_active(sub, ts):
                    base = max(ts, sub["expires_at"])
                new_expires = base + days * 86400
            await self.conn.execute(
                """
                INSERT INTO subscriptions (owner_user_id, plan, expires_at, is_active, last_reminder_at, updated_at)
                VALUES (?, ?, ?, 1, NULL, ?)
                ON CONFLICT(owner_user_id) DO UPDATE SET
                    plan = excluded.plan,
                    expires_at = excluded.expires_at,
                    is_active = 1,
                    last_reminder_at = NULL,
                    updated_at = excluded.updated_at
                """,
                (user_id, plan, new_expires, ts),
            )
            await self.conn.commit()
            return new_expires

    async def reduce_subscription(self, user_id: int, days: int | None) -> None:
        """Откатывает оплаченный период при возврате звёзд (None — снимает «навсегда»)."""
        async with self._lock:
            sub = await self.get_subscription(user_id)
            if not sub:
                return
            ts = now_ts()
            if days is None or sub["expires_at"] is None:
                new_expires = ts
            else:
                new_expires = max(ts, sub["expires_at"] - days * 86400)
            is_active = int(new_expires > ts)
            await self.conn.execute(
                "UPDATE subscriptions SET expires_at = ?, is_active = ?, updated_at = ? WHERE owner_user_id = ?",
                (new_expires, is_active, ts, user_id),
            )
            await self.conn.commit()

    async def revoke_subscription(self, user_id: int) -> bool:
        """Досрочно отзывает подписку (делает неактивной). False — если её не было."""
        async with self._lock:
            sub = await self.get_subscription(user_id)
            if not sub:
                return False
            await self.conn.execute(
                "UPDATE subscriptions SET expires_at = ?, is_active = 0, updated_at = ? WHERE owner_user_id = ?",
                (now_ts(), now_ts(), user_id),
            )
            await self.conn.commit()
            return True

    async def expire_subscriptions(self) -> list[int]:
        """Помечает истёкшие подписки неактивными. Возвращает id владельцев."""
        ts = now_ts()
        rows = await self._fetchall(
            "SELECT owner_user_id FROM subscriptions WHERE is_active = 1 AND expires_at IS NOT NULL AND expires_at <= ?",
            (ts,),
        )
        ids = [r["owner_user_id"] for r in rows]
        if ids:
            await self._execute(
                f"UPDATE subscriptions SET is_active = 0, updated_at = ? "
                f"WHERE owner_user_id IN ({','.join('?' * len(ids))})",
                (ts, *ids),
            )
        return ids

    async def should_remind(self, user_id: int, interval_hours: int) -> bool:
        """True, если пора снова напомнить о продлении (защита от спама)."""
        sub = await self.get_subscription(user_id)
        if sub is None:
            return True
        last = sub["last_reminder_at"]
        return last is None or now_ts() - last >= interval_hours * 3600

    async def mark_reminded(self, user_id: int) -> None:
        await self._execute(
            "UPDATE subscriptions SET last_reminder_at = ? WHERE owner_user_id = ?",
            (now_ts(), user_id),
        )

    # ------------------------------------------------------------------ connections

    async def upsert_connection(
        self,
        connection_id: str,
        owner_user_id: int,
        user_chat_id: int,
        is_enabled: bool,
        can_reply: bool,
    ) -> None:
        ts = now_ts()
        await self._execute(
            """
            INSERT INTO connections
                (business_connection_id, owner_user_id, user_chat_id, is_enabled, can_reply, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(business_connection_id) DO UPDATE SET
                owner_user_id = excluded.owner_user_id,
                user_chat_id = excluded.user_chat_id,
                is_enabled = excluded.is_enabled,
                can_reply = excluded.can_reply,
                updated_at = excluded.updated_at
            """,
            (connection_id, owner_user_id, user_chat_id, int(is_enabled), int(can_reply), ts, ts),
        )

    async def get_connection(self, connection_id: str) -> dict | None:
        return await self._fetchone(
            "SELECT * FROM connections WHERE business_connection_id = ?", (connection_id,)
        )

    async def get_owner_connections(self, owner_user_id: int) -> list[dict]:
        return await self._fetchall(
            "SELECT * FROM connections WHERE owner_user_id = ? ORDER BY updated_at DESC", (owner_user_id,)
        )

    # ------------------------------------------------------------------ messages (метаданные)

    async def save_message_meta(
        self,
        owner_user_id: int,
        connection_id: str,
        chat_id: int,
        message_id: int,
        from_user_id: int | None,
        from_username: str | None,
        from_name: str | None,
        sent_at: int,
        content_type: str | None = None,
        text: str | None = None,
        file_id: str | None = None,
        media_path: str | None = None,
        media_size: int | None = None,
        forward_from: str | None = None,
    ) -> None:
        """
        Сохраняет метаданные, текст, file_id, путь к медиа и источник пересылки.
        file_id — ссылка Telegram (запасной способ), media_path — локальная копия файла.
        """
        await self._execute(
            """
            INSERT INTO messages
                (owner_user_id, business_connection_id, chat_id, message_id,
                 from_user_id, from_username, from_name, content_type, text, file_id,
                 media_path, media_size, forward_from, sent_at, saved_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(owner_user_id, chat_id, message_id) DO NOTHING
            """,
            (owner_user_id, connection_id, chat_id, message_id,
             from_user_id, from_username, from_name, content_type, text, file_id,
             media_path, media_size, forward_from, sent_at, now_ts()),
        )

    async def update_message_text(self, owner_user_id: int, chat_id: int, message_id: int,
                                  text: str | None) -> bool:
        """Обновляет текущий текст сообщения. False — если сообщение не сохранялось."""
        rows = await self._execute(
            "UPDATE messages SET text = ? WHERE owner_user_id = ? AND chat_id = ? AND message_id = ?",
            (text, owner_user_id, chat_id, message_id),
        )
        return rows > 0

    async def get_message(self, owner_user_id: int, chat_id: int, message_id: int) -> dict | None:
        """Текущая запись сообщения по (владелец, чат, message_id)."""
        return await self._fetchone(
            "SELECT * FROM messages WHERE owner_user_id = ? AND chat_id = ? AND message_id = ?",
            (owner_user_id, chat_id, message_id),
        )

    async def add_edit(self, owner_user_id: int, chat_id: int, message_id: int,
                       old_text: str | None, new_text: str | None, edited_at: int) -> None:
        """Сохраняет одну правку (старое -> новое) в историю изменений."""
        await self._execute(
            """
            INSERT INTO message_edits (owner_user_id, chat_id, message_id, old_text, new_text, edited_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (owner_user_id, chat_id, message_id, old_text, new_text, edited_at),
        )

    async def get_edits(self, owner_user_id: int, chat_id: int, message_id: int) -> list[dict]:
        """Вся сохранённая история правок сообщения (от старых к новым)."""
        return await self._fetchall(
            "SELECT * FROM message_edits WHERE owner_user_id = ? AND chat_id = ? AND message_id = ? "
            "ORDER BY edited_at, id",
            (owner_user_id, chat_id, message_id),
        )

    async def get_messages_meta(self, owner_user_id: int, chat_id: int, message_ids: list[int]) -> dict[int, dict]:
        """Ищет метаданные по owner + chat_id + message_ids. Возвращает {message_id: row}."""
        if not message_ids:
            return {}
        result: dict[int, dict] = {}
        # SQLite ограничивает число параметров — режем на пачки
        for i in range(0, len(message_ids), 500):
            chunk = message_ids[i:i + 500]
            rows = await self._fetchall(
                f"SELECT * FROM messages WHERE owner_user_id = ? AND chat_id = ? "
                f"AND message_id IN ({','.join('?' * len(chunk))})",
                (owner_user_id, chat_id, *chunk),
            )
            result.update({r["message_id"]: r for r in rows})
        return result

    async def delete_messages_meta(self, owner_user_id: int, chat_id: int, message_ids: list[int]) -> None:
        """Удаляет метаданные, которые больше не нужны (сообщение уже удалено)."""
        for i in range(0, len(message_ids), 500):
            chunk = message_ids[i:i + 500]
            await self._execute(
                f"DELETE FROM messages WHERE owner_user_id = ? AND chat_id = ? "
                f"AND message_id IN ({','.join('?' * len(chunk))})",
                (owner_user_id, chat_id, *chunk),
            )

    async def mark_messages_deleted(self, owner_user_id: int, chat_id: int,
                                    message_ids: list[int], deleted_at: int) -> None:
        """Помечает сообщения удалёнными (строки остаются для раздела «История»)."""
        for i in range(0, len(message_ids), 500):
            chunk = message_ids[i:i + 500]
            await self._execute(
                f"UPDATE messages SET is_deleted = 1, deleted_at = ? "
                f"WHERE owner_user_id = ? AND chat_id = ? AND is_deleted = 0 "
                f"AND message_id IN ({','.join('?' * len(chunk))})",
                (deleted_at, owner_user_id, chat_id, *chunk),
            )

    async def insert_deleted_tombstones(self, owner_user_id: int, connection_id: str, chat_id: int,
                                        message_ids: list[int], deleted_at: int) -> None:
        """
        Ставит «надгробия» для удалённых сообщений, которых не было в базе
        (бот их не получал). Нужны, чтобы повторное событие удаления не слало
        уведомление ещё раз. В «Историю» такие пустые записи не попадают.
        """
        ts = now_ts()
        for mid in message_ids:
            await self.conn.execute(
                """
                INSERT INTO messages
                    (owner_user_id, business_connection_id, chat_id, message_id,
                     is_deleted, deleted_at, sent_at, saved_at)
                VALUES (?, ?, ?, ?, 1, ?, ?, ?)
                ON CONFLICT(owner_user_id, chat_id, message_id) DO NOTHING
                """,
                (owner_user_id, connection_id, chat_id, mid, deleted_at, deleted_at, ts),
            )
        await self.conn.commit()

    async def delete_owner_messages(self, owner_user_id: int) -> int:
        """Полностью стирает метаданные и историю правок владельца."""
        await self._execute("DELETE FROM message_edits WHERE owner_user_id = ?", (owner_user_id,))
        return await self._execute("DELETE FROM messages WHERE owner_user_id = ?", (owner_user_id,))

    # ------------------------------------------------------------------ история (только свои записи владельца)

    @staticmethod
    def _history_where(owner_user_id: int, query: str | None, since_ts: int | None,
                       only_deleted: bool) -> tuple[str, list]:
        """Собирает условие WHERE и параметры для выборки истории владельца."""
        # Пустые «надгробия» (неизвестные удалённые сообщения) в историю не показываем
        where = ["owner_user_id = ?",
                 "NOT (text IS NULL AND content_type IS NULL AND from_user_id IS NULL)"]
        params: list = [owner_user_id]
        if query:
            where.append("text LIKE ?")
            params.append(f"%{query}%")
        if since_ts is not None:
            where.append("sent_at >= ?")
            params.append(since_ts)
        if only_deleted:
            where.append("is_deleted = 1")
        return " AND ".join(where), params

    async def history_count(self, owner_user_id: int, query: str | None = None,
                            since_ts: int | None = None, only_deleted: bool = False) -> int:
        clause, params = self._history_where(owner_user_id, query, since_ts, only_deleted)
        row = await self._fetchone(f"SELECT COUNT(*) AS c FROM messages WHERE {clause}", params)
        return row["c"]

    async def history_page(self, owner_user_id: int, limit: int, offset: int,
                           query: str | None = None, since_ts: int | None = None,
                           only_deleted: bool = False) -> list[dict]:
        """Страница истории владельца, новые сверху. Только его собственные записи."""
        clause, params = self._history_where(owner_user_id, query, since_ts, only_deleted)
        return await self._fetchall(
            f"SELECT * FROM messages WHERE {clause} ORDER BY sent_at DESC, message_id DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        )

    async def history_item(self, owner_user_id: int, row_id: int) -> dict | None:
        """Одна запись истории по её id — строго в пределах данных владельца (изоляция)."""
        return await self._fetchone(
            "SELECT * FROM messages WHERE id = ? AND owner_user_id = ?", (row_id, owner_user_id)
        )

    async def purge_old_messages(self, older_than_days: int) -> list[str]:
        """
        Удаляет метаданные старше срока хранения (если он включён, > 0).
        Возвращает пути медиафайлов, которые нужно удалить с диска. При 0 — ничего не делает.
        """
        if older_than_days <= 0:
            return []
        border = now_ts() - older_than_days * 86400
        rows = await self._fetchall(
            "SELECT media_path FROM messages WHERE saved_at < ? AND media_path IS NOT NULL", (border,)
        )
        await self._execute("DELETE FROM messages WHERE saved_at < ?", (border,))
        return [r["media_path"] for r in rows]

    # ------------------------------------------------------------------ payments

    async def add_payment(self, owner_user_id: int, plan: str, amount: int, currency: str, charge_id: str) -> bool:
        """Сохраняет платёж. False — если такой charge_id уже был (защита от дублей)."""
        rows = await self._execute(
            """
            INSERT INTO payments (owner_user_id, plan, amount, currency, telegram_payment_charge_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(telegram_payment_charge_id) DO NOTHING
            """,
            (owner_user_id, plan, amount, currency, charge_id, now_ts()),
        )
        return rows > 0

    async def get_payment(self, charge_id: str) -> dict | None:
        return await self._fetchone(
            "SELECT * FROM payments WHERE telegram_payment_charge_id = ?", (charge_id,)
        )

    async def mark_payment_refunded(self, charge_id: str) -> bool:
        """Помечает платёж возвращённым. False — если он уже был возвращён или не найден."""
        rows = await self._execute(
            "UPDATE payments SET status = 'refunded', refunded_at = ? "
            "WHERE telegram_payment_charge_id = ? AND status = 'paid'",
            (now_ts(), charge_id),
        )
        return rows > 0

    async def list_payments(self, owner_user_id: int | None = None, limit: int = 10) -> list[dict]:
        if owner_user_id is None:
            return await self._fetchall("SELECT * FROM payments ORDER BY id DESC LIMIT ?", (limit,))
        return await self._fetchall(
            "SELECT * FROM payments WHERE owner_user_id = ? ORDER BY id DESC LIMIT ?", (owner_user_id, limit)
        )

    # ------------------------------------------------------------------ статистика

    async def stats(self) -> dict[str, int]:
        ts = now_ts()
        users = await self._fetchone("SELECT COUNT(*) AS c FROM users")
        active = await self._fetchone(
            "SELECT COUNT(*) AS c FROM subscriptions WHERE is_active = 1 AND (expires_at IS NULL OR expires_at > ?)",
            (ts,),
        )
        paid = await self._fetchone(
            "SELECT COUNT(*) AS c FROM subscriptions WHERE is_active = 1 AND plan NOT IN ('trial') "
            "AND (expires_at IS NULL OR expires_at > ?)",
            (ts,),
        )
        conns = await self._fetchone("SELECT COUNT(*) AS c FROM connections WHERE is_enabled = 1")
        stars = await self._fetchone("SELECT COALESCE(SUM(amount), 0) AS c FROM payments WHERE status = 'paid'")
        meta = await self._fetchone("SELECT COUNT(*) AS c FROM messages")
        return {
            "users": users["c"],
            "active_subs": active["c"],
            "paid_subs": paid["c"],
            "connections": conns["c"],
            "stars": stars["c"],
            "messages_meta": meta["c"],
        }

    async def list_users(self, limit: int = 20, offset: int = 0) -> list[dict]:
        """Список пользователей с их подпиской (для админской команды /users)."""
        return await self._fetchall(
            """
            SELECT u.user_id, u.username, u.first_name, u.notifications_enabled,
                   s.plan, s.expires_at, s.is_active
            FROM users u
            LEFT JOIN subscriptions s ON s.owner_user_id = u.user_id
            ORDER BY u.created_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        )

    async def user_summary(self, user_id: int) -> dict:
        """Операционная сводка по пользователю (без содержимого его переписки)."""
        conns = await self._fetchall(
            "SELECT is_enabled FROM connections WHERE owner_user_id = ?", (user_id,)
        )
        msgs = await self._fetchone(
            "SELECT COUNT(*) AS c FROM messages WHERE owner_user_id = ?", (user_id,)
        )
        return {
            "connections_total": len(conns),
            "connections_active": sum(1 for c in conns if c["is_enabled"]),
            "messages_meta": msgs["c"],
        }

    async def backup_to(self, dest_path: str) -> None:
        """Создаёт целостную резервную копию базы (безопасно при включённом WAL)."""
        directory = os.path.dirname(dest_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        # VACUUM INTO делает согласованную копию без остановки бота (SQLite 3.27+)
        await self.conn.execute("VACUUM INTO ?", (dest_path,))
