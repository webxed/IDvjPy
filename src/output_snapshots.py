"""Bounded, secret-safe output snapshots kept outside the tag database."""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

SNAPSHOT_FILE = "output_snapshots.json"
MAX_SNAPSHOTS = 20
MAX_SNAPSHOT_BYTES = 256 * 1024
MAX_STORE_BYTES = 5 * 1024 * 1024
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


class SnapshotError(ValueError):
    """Invalid name or snapshot store."""


def validate_name(name: str) -> str:
    value = str(name).strip()
    if not _NAME_RE.fullmatch(value):
        raise SnapshotError("snapshot name must match [A-Za-z0-9][A-Za-z0-9_-]{0,63}")
    return value


def load_snapshots(data_dir: str) -> tuple[list[dict[str, Any]], str]:
    path = Path(data_dir) / SNAPSHOT_FILE
    if not path.exists():
        return [], ""
    try:
        if path.stat().st_size > MAX_STORE_BYTES:
            return [], f"{SNAPSHOT_FILE}: file exceeds {MAX_STORE_BYTES} bytes"
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [], f"{SNAPSHOT_FILE}: {exc}"
    if not isinstance(payload, list) or len(payload) > MAX_SNAPSHOTS:
        return [], f"{SNAPSHOT_FILE}: expected an array of at most {MAX_SNAPSHOTS} snapshots"
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in payload:
        if not isinstance(item, dict) or set(item) != {"name", "created", "text", "truncated"}:
            return [], f"{SNAPSHOT_FILE}: invalid snapshot record"
        try:
            name = validate_name(item["name"])
        except (SnapshotError, TypeError) as exc:
            return [], f"{SNAPSHOT_FILE}: {exc}"
        text = item["text"]
        if name in seen or not isinstance(text, str) or len(text.encode("utf-8")) > MAX_SNAPSHOT_BYTES:
            return [], f"{SNAPSHOT_FILE}: duplicate name or oversized/invalid text"
        if not isinstance(item["created"], str) or not isinstance(item["truncated"], bool):
            return [], f"{SNAPSHOT_FILE}: invalid snapshot metadata"
        seen.add(name)
        result.append({"name": name, "created": item["created"], "text": text, "truncated": item["truncated"]})
    return result, ""


def save_snapshot(data_dir: str, name: str, text: str, *, created: str) -> str | None:
    try:
        safe_name = validate_name(name)
        encoded = text.encode("utf-8")
        truncated = len(encoded) > MAX_SNAPSHOT_BYTES
        if truncated:
            encoded = encoded[:MAX_SNAPSHOT_BYTES]
            text = encoded.decode("utf-8", errors="ignore")
        snapshots, error = load_snapshots(data_dir)
        if error:
            raise SnapshotError(error)
        existing = next((item for item in snapshots if item["name"] == safe_name), None)
        if existing is None and len(snapshots) >= MAX_SNAPSHOTS:
            raise SnapshotError(f"snapshot limit reached ({MAX_SNAPSHOTS}); remove one first")
        record = {"name": safe_name, "created": created, "text": text, "truncated": truncated}
        snapshots = [item for item in snapshots if item["name"] != safe_name]
        snapshots.append(record)
        payload = json.dumps(snapshots, ensure_ascii=False, indent=2) + "\n"
        if len(payload.encode("utf-8")) > MAX_STORE_BYTES:
            raise SnapshotError(f"snapshot store limit reached ({MAX_STORE_BYTES} bytes)")
        path = Path(data_dir) / SNAPSHOT_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
            os.chmod(temp_name, 0o600)
            os.replace(temp_name, path)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
    except (OSError, SnapshotError) as exc:
        return str(exc)
    return None


def delete_snapshot(data_dir: str, name: str) -> str | None:
    try:
        safe_name = validate_name(name)
        snapshots, error = load_snapshots(data_dir)
        if error:
            raise SnapshotError(error)
        if not any(item["name"] == safe_name for item in snapshots):
            return f"snapshot not found: {safe_name}"
        snapshots = [item for item in snapshots if item["name"] != safe_name]
        path = Path(data_dir) / SNAPSHOT_FILE
        if not snapshots:
            path.unlink(missing_ok=True)
            return None
        payload = json.dumps(snapshots, ensure_ascii=False, indent=2) + "\n"
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
            os.chmod(temp_name, 0o600)
            os.replace(temp_name, path)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
    except (OSError, SnapshotError) as exc:
        return str(exc)
    return None
