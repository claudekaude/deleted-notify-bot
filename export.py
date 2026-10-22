"""
Экспорт личного архива владельца в HTML / TXT / JSON (упаковывается в ZIP).

Берутся ТОЛЬКО собственные записи владельца (строгая изоляция по owner_user_id).
Если на диске есть сохранённые медиафайлы — они добавляются в архив в папку media/.
Содержимое не раскрывается третьим лицам: экспорт получает только сам владелец.
"""
from __future__ import annotations

import html
import json
import logging
import os
import re
import zipfile
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from db import Database

log = logging.getLogger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")
# Сколько места максимум занимают медиа в архиве (защита от гигантских выгрузок)
MAX_MEDIA_BYTES = 40 * 1024 * 1024


def _plain(html_text: str | None) -> str:
    """HTML -> простой текст (для TXT/JSON): убираем теги и разэкранируем."""
    if not html_text:
        return ""
    return html.unescape(_TAG_RE.sub("", html_text))


def _fmt(ts: int | None, tz: ZoneInfo) -> str:
    if not ts:
        return ""
    return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")


async def build_export(db: Database, owner_user_id: int, tz: ZoneInfo, dest_dir: str) -> tuple[str, int] | None:
    """
    Собирает ZIP с архивом владельца. Возвращает (путь_к_zip, число_сообщений)
    или None, если экспортировать нечего.
    """
    rows = await db.history_page(owner_user_id, limit=100000, offset=0)
    if not rows:
        return None

    # Подтягиваем историю правок для каждого сообщения
    edits_by_msg: dict[tuple[int, int], list[dict]] = {}
    for r in rows:
        key = (r["chat_id"], r["message_id"])
        if key not in edits_by_msg:
            edits_by_msg[key] = await db.get_edits(owner_user_id, r["chat_id"], r["message_id"])

    os.makedirs(dest_dir, exist_ok=True)
    stamp = datetime.now(tz).strftime("%Y%m%d-%H%M%S")
    base = os.path.join(dest_dir, f"archive-{owner_user_id}-{stamp}")

    # --- JSON (структурированные данные)
    data = []
    for r in rows:
        key = (r["chat_id"], r["message_id"])
        data.append({
            "chat_id": r["chat_id"],
            "message_id": r["message_id"],
            "from_user_id": r["from_user_id"],
            "from_username": r["from_username"],
            "from_name": r["from_name"],
            "content_type": r["content_type"],
            "forward_from": r["forward_from"],
            "text": _plain(r["text"]),
            "media_file": os.path.basename(r["media_path"]) if r.get("media_path") else None,
            "sent_at": _fmt(r["sent_at"], tz),
            "is_deleted": bool(r["is_deleted"]),
            "deleted_at": _fmt(r["deleted_at"], tz),
            "edits": [{"old": _plain(e["old_text"]), "new": _plain(e["new_text"]),
                       "edited_at": _fmt(e["edited_at"], tz)} for e in edits_by_msg.get(key, [])],
        })
    json_path = base + ".json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # --- TXT (простой текст)
    txt_path = base + ".txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        for d in data:
            author = d["from_username"] and f"@{d['from_username']}" or d["from_name"] or str(d["from_user_id"])
            mark = "[УДАЛЕНО] " if d["is_deleted"] else ""
            f.write(f"{d['sent_at']} | {mark}{author}\n")
            if d["text"]:
                f.write(d["text"] + "\n")
            elif d["content_type"] and d["content_type"] != "text":
                f.write(f"[{d['content_type']}{': ' + d['media_file'] if d['media_file'] else ''}]\n")
            for e in d["edits"]:
                f.write(f"    ✎ {e['edited_at']}: «{e['old']}» → «{e['new']}»\n")
            f.write("\n")

    # --- HTML (читаемая переписка)
    html_path = base + ".html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write("<!doctype html><meta charset='utf-8'><title>Архив</title>"
                "<style>body{font-family:system-ui,Segoe UI,Arial;background:#0f1116;color:#e6e6e6;"
                "max-width:720px;margin:0 auto;padding:16px}.m{border-left:3px solid #2b6cff;"
                "background:#171a21;border-radius:8px;padding:8px 12px;margin:10px 0}.t{color:#8a93a3;"
                "font-size:12px}.d{color:#ff6b6b}.e{color:#c9a227;font-size:13px;margin-top:4px}"
                "img{max-width:220px;border-radius:8px;display:block;margin-top:6px}</style>"
                "<h2>📨 Архив переписки</h2>")
        for d in data:
            author = d["from_username"] and f"@{d['from_username']}" or d["from_name"] or str(d["from_user_id"])
            cls = "t d" if d["is_deleted"] else "t"
            tag = " · удалено" if d["is_deleted"] else ""
            f.write(f"<div class='m'><div class='{cls}'>{html.escape(author)} · {d['sent_at']}{tag}</div>")
            if d["text"]:
                f.write(f"<div>{html.escape(d['text']).replace(chr(10), '<br>')}</div>")
            if d["media_file"]:
                ext = os.path.splitext(d["media_file"])[1].lower()
                if ext in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
                    f.write(f"<img src='media/{html.escape(d['media_file'])}'>")
                else:
                    f.write(f"<div class='t'>📎 media/{html.escape(d['media_file'])} ({d['content_type']})</div>")
            for e in d["edits"]:
                f.write(f"<div class='e'>✎ {e['edited_at']}: «{html.escape(e['old'])}» → «{html.escape(e['new'])}»</div>")
            f.write("</div>")

    # --- ZIP: три файла + медиа (пока помещается в лимит)
    zip_path = base + ".zip"
    used = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in (json_path, txt_path, html_path):
            z.write(p, os.path.basename(p))
        for r in rows:
            mp = r.get("media_path")
            if mp and os.path.exists(mp):
                try:
                    size = os.path.getsize(mp)
                except OSError:
                    continue
                if used + size > MAX_MEDIA_BYTES:
                    continue
                z.write(mp, os.path.join("media", os.path.basename(mp)))
                used += size

    # Промежуточные файлы больше не нужны — оставляем только zip
    for p in (json_path, txt_path, html_path):
        try:
            os.remove(p)
        except OSError:
            pass
    return zip_path, len(rows)
