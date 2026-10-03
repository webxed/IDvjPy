"""Журнал аудита без содержимого, только на дозапись, для изменений библиотеки пользователем."""
from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
from typing import Any

AUDIT_FILE = "library_audit.jsonl"
MAX_EVENT_BYTES = 4096
ACTIONS = frozenset({"import", "save", "comment", "soft-delete", "restore"})


def record_event(
    data_dir: str,
    action: str,
    *,
    tags: list[str] | tuple[str, ...] = (),
    count: int = 0,
) -> str | None:
    """Писать только метаданные операции; никогда не сохранять команды, комментарии и исходные URL."""
    if action not in ACTIONS or count < 0:
        return "invalid audit event"
    clean_tags = sorted({str(tag)[:128] for tag in tags if str(tag).strip()})[:100]
    if any(not tag or any(ord(char) < 32 for char in tag) for tag in clean_tags):
        return "tag name is not safe for audit"
    event = {
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
        "action": action,
        "count": int(count),
        "tags": clean_tags,
    }
    line = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
    if len(line.encode("utf-8")) > MAX_EVENT_BYTES:
        return "audit event too large"
    path = Path(data_dir) / AUDIT_FILE
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as handle:
            os.chmod(path, 0o600)
            handle.write(line + "\n")
            handle.flush()
    except OSError as exc:
        return str(exc)
    return None


def read_events(data_dir: str, limit: int = 20) -> tuple[list[dict[str, Any]], str]:
    """Прочитать последние прошедшие проверку события; некорректные записи игнорируются."""
    if limit < 1:
        return [], "limit must be positive"
    path = Path(data_dir) / AUDIT_FILE
    try:
        with path.open(encoding="utf-8") as handle:
            lines = handle.readlines()[-min(limit, 200):]
    except FileNotFoundError:
        return [], ""
    except OSError as exc:
        return [], str(exc)
    events: list[dict[str, Any]] = []
    for raw in lines:
        if len(raw.encode("utf-8", "replace")) > MAX_EVENT_BYTES:
            continue
        try:
            item = json.loads(raw)
        except (ValueError, TypeError):
            continue
        if (
            isinstance(item, dict)
            and set(item) == {"timestamp", "action", "count", "tags"}
            and item.get("action") in ACTIONS
            and isinstance(item.get("timestamp"), str)
            and isinstance(item.get("count"), int)
            and not isinstance(item.get("count"), bool)
            and isinstance(item.get("tags"), list)
            and all(isinstance(tag, str) for tag in item["tags"])
        ):
            events.append(item)
    return events, ""
