"""Закреплённые теги на сессию, хранятся отдельно от общей базы библиотеки."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

PREFIX = "pins_"


def pins_file_for(session: str) -> str:
    return f"{PREFIX}{session}.json"


def pins_path(data_dir: str, session: str) -> str:
    return os.path.join(data_dir, pins_file_for(session))


def load_pins(data_dir: str, session: str) -> tuple[list[str], str]:
    path = Path(pins_path(data_dir, session))
    if not path.is_file():
        return [], ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [], f"{path.name}: {exc}"
    if not isinstance(payload, list) or not all(
        isinstance(item, str) and item.strip() for item in payload
    ):
        return [], f"{path.name}: JSON root must be an array of non-empty tag names"
    return list(dict.fromkeys(item.strip() for item in payload)), ""


def save_pins(data_dir: str, session: str, tags: list[str]) -> bool:
    path = Path(pins_path(data_dir, session))
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(list(dict.fromkeys(tags)), handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            os.chmod(temp_name, 0o600)
            os.replace(temp_name, path)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
    except OSError:
        return False
    return True
