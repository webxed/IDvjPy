"""Перенос библиотеки тегов: JSON, CSV и Markdown — один код на все входы.

Раньше JSON-экспорт/импорт был реализован дважды: в TUI (`database_v2`) и в
CLI (`backup_db.py`, со своей SQL-обвязкой), причём обе стороны писали
``schema_version: "v2"`` при разных наборах полей. Здесь один канонический вид
записи и терпимое чтение (оба исторических вида), один insert-путь и один путь
чтения из БД — `database_v2`.

Импорт JSON **не переносит глобальные ``id``**: чужой ``id`` мог совпасть с
существующей строкой и затереть другую команду (старый CLI-импорт именно так и
делал — UPDATE по совпавшему id). Точный слепок базы — это SQLite-снимок
(`:backup` / `--seed` / `backup_db.py backup`), а JSON/CSV — перенос и правка.

Модуль не зависит от Textual.
"""
from __future__ import annotations

import csv
import datetime
import json
import os
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import database_v2 as database

JSON_VERSION = "2.0"
JSON_SCHEMA_VERSION = "v2"
CSV_DELIMITER = ";"
COMMAND_FIELDS = ("tag", "tid", "command", "comment")


@dataclass(frozen=True)
class ImportResult:
    """Итог импорта: сколько строк добавлено/обновлено/пропущено и какие теги."""

    imported: int = 0
    updated: int = 0
    skipped: int = 0
    tags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def total(self) -> int:
        """Сколько строк реально записано (новые + обновлённые)."""
        return self.imported + self.updated


# --- чтение из БД ------------------------------------------------------------


def count_tags(db_file: str, *, tag: str | None = None) -> int:
    """Сколько тегов попадает в выгрузку (для сообщений CLI)."""
    return len(_tag_comments(db_file, tag=tag))


def csv_schema(path: str) -> str:
    """Что за CSV: `"commands"` (`tag;tid;…`) или `"tags"` (`tag;comment`).

    Определяем по заголовку — так `restore` принимает любой из двух файлов.
    """
    try:
        rows = _read_csv(path)
    except OSError:
        return "commands"
    if not rows:
        return "commands"
    header = [cell.strip().lower() for cell in rows[0]]
    return "tags" if "tid" not in header else "commands"


def _command_rows(
    db_file: str, *, tag: str | None = None, include_deleted: bool = False
) -> list[dict[str, Any]]:
    """Строки команд для выгрузки (по тегу или вся библиотека)."""
    conn = database.get_db_connection(db_file)
    try:
        where = "" if include_deleted else " WHERE deleted = 0"
        params: tuple[Any, ...] = ()
        if tag:
            where = " WHERE tag = ?" + ("" if include_deleted else " AND deleted = 0")
            params = (tag,)
        rows = conn.execute(
            "SELECT id, tag, tid, command, timestamp, deleted, comment FROM commands"
            + where
            + " ORDER BY tag ASC, tid ASC",
            params,
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "id": row["id"],
            "tag": row["tag"],
            "tid": row["tid"],
            "command": row["command"],
            "timestamp": row["timestamp"],
            "deleted": 1 if row["deleted"] else 0,
            "comment": row["comment"] or "",
        }
        for row in rows
    ]


def _tag_comments(db_file: str, *, tag: str | None = None) -> dict[str, str]:
    """Комментарии тегов (одного или всех)."""
    if tag:
        return {tag: database.get_tag_comment(db_file, tag)}
    return dict(database.get_all_tags_with_comments(db_file))


def library_overview(db_file: str) -> list[tuple[str, int, str]]:
    """Теги для отчёта `backup_db.py list`: (тег, число живых команд, комментарий)."""
    conn = database.get_db_connection(db_file)
    try:
        rows = conn.execute(
            "SELECT c.tag AS tag, COUNT(*) AS n, t.comment AS comment "
            "FROM commands c LEFT JOIN tags t ON c.tag = t.tag "
            "WHERE c.deleted = 0 GROUP BY c.tag ORDER BY c.tag ASC"
        ).fetchall()
    finally:
        conn.close()
    return [(row["tag"], int(row["n"]), row["comment"] or "") for row in rows]


# --- JSON --------------------------------------------------------------------


def export_json(
    db_file: str,
    path: str,
    *,
    tag: str | None = None,
    include_deleted: bool = False,
) -> int:
    """Записать библиотеку (или один тег) в JSON. Возвращает число команд."""
    commands = _command_rows(db_file, tag=tag, include_deleted=include_deleted)
    comments = _tag_comments(db_file, tag=tag)
    payload = {
        "version": JSON_VERSION,
        "schema_version": JSON_SCHEMA_VERSION,
        "export_date": datetime.datetime.now().isoformat(timespec="seconds"),
        "source_db": os.path.basename(db_file),
        "tag_filter": tag,
        "total_commands": len(commands),
        "total_tags": len(comments),
        "tag_comments": comments,
        "commands": commands,
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return len(commands)


def read_json(path: str) -> dict[str, Any]:
    """Прочитать файл переноса (любой из исторических видов)."""
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("JSON root must be an object")
    return payload


def payload_tag(payload: dict[str, Any]) -> str:
    """Тег файла для однoтегового импорта (`:import`): `tag_filter` или первый ряд."""
    tag = (payload.get("tag_filter") or "").strip()
    if tag:
        return tag
    for item in payload.get("commands") or []:
        row_tag = (item.get("tag") or "").strip()
        if row_tag:
            return row_tag
    raise ValueError("JSON has no tag_filter / commands[].tag")


def _clear_library(conn) -> None:
    conn.execute("DELETE FROM commands")
    conn.execute("DELETE FROM tags")


def _next_tid(conn, tag: str) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(tid), 0) + 1 FROM commands WHERE tag = ?", (tag,)
    ).fetchone()
    return int(row[0]) if row else 1


def _tid_taken(conn, tag: str, tid: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM commands WHERE tag = ? AND tid = ? AND deleted = 0", (tag, tid)
    ).fetchone()
    return row is not None


def _insert_command(conn, tag: str, tid: int, command: str, comment: str) -> None:
    cursor = conn.execute(
        "INSERT INTO commands (tag, tid, command, timestamp) VALUES (?, ?, ?, ?)",
        (tag, tid, command, datetime.datetime.now()),
    )
    if comment:
        conn.execute(
            "UPDATE commands SET comment = ? WHERE id = ?", (comment, cursor.lastrowid)
        )


def import_json(
    db_file: str,
    path: str,
    *,
    mode: str = "merge",
    preserve_tid: bool = False,
    skip_existing: bool = False,
    include_deleted: bool = False,
    only_tag: str | None = None,
) -> ImportResult:
    """Импортировать команды из JSON.

    ``mode="replace"`` сначала очищает библиотеку (команды и комментарии тегов).
    ``skip_existing`` пропускает строки, у которых пара (тег, tid) уже занята живой
    командой — так повторный импорт ничего не добавляет (CLI: merge). Без него
    каждая строка вставляется с новым tid — так работает `:import` в TUI, где
    импорт — это «добавить команды», а не «восстановить базу».
    """
    payload = read_json(path)
    commands: Sequence[Any] = payload.get("commands") or []
    tag_override = (only_tag or "").strip() or None
    comments = payload.get("tag_comments") or {}
    database.init_db(db_file)
    conn = database.get_db_connection(db_file)
    tags: set[str] = set()
    imported = updated = skipped = 0
    try:
        conn.execute("BEGIN IMMEDIATE")
        if mode == "replace":
            _clear_library(conn)
        for item in commands:
            if not isinstance(item, dict):
                skipped += 1
                continue
            if item.get("deleted") and not include_deleted:
                skipped += 1
                continue
            tag = tag_override or (item.get("tag") or "").strip()
            command = (item.get("command") or "").strip()
            if not tag or not command:
                skipped += 1
                continue
            comment = (item.get("comment") or "").strip()
            raw_tid = item.get("tid")
            source_tid = raw_tid if isinstance(raw_tid, int) else 0
            same = source_tid > 0
            if skip_existing and mode == "merge" and same and _tid_taken(conn, tag, source_tid):
                skipped += 1
                continue
            tid = source_tid if (preserve_tid and same) else _next_tid(conn, tag)
            if preserve_tid and same and _tid_taken(conn, tag, tid):
                tid = _next_tid(conn, tag)
            _insert_command(conn, tag, tid, command, comment)
            tags.add(tag)
            imported += 1
        for tag, comment in (comments or {}).items():
            if tag_override and tag != tag_override:
                continue
            if not isinstance(comment, str):
                continue
            conn.execute(
                "INSERT OR REPLACE INTO tags (tag, comment) VALUES (?, ?)",
                (tag, comment),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return ImportResult(imported, updated, skipped, tuple(sorted(tags)))


# --- CSV ---------------------------------------------------------------------


def export_commands_csv(
    db_file: str,
    path: str,
    *,
    tag: str | None = None,
    include_deleted: bool = False,
) -> int:
    """Команды в CSV (`tag;tid;command;comment`) для правки в таблице."""
    rows = _command_rows(db_file, tag=tag, include_deleted=include_deleted)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter=CSV_DELIMITER, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(list(COMMAND_FIELDS))
        for row in rows:
            writer.writerow([row["tag"], row["tid"], row["command"], row["comment"]])
    return len(rows)


def _read_csv(path: str) -> list[list[str]]:
    with open(path, newline="", encoding="utf-8") as handle:
        return [row for row in csv.reader(handle, delimiter=CSV_DELIMITER)]


def import_commands_csv(db_file: str, path: str, *, mode: str = "merge") -> ImportResult:
    """Импорт команд из CSV: строка адресуется парой (тег, tid).

    Существующая команда обновляется, отсутствующая — добавляется (в отличие от
    JSON-импорта, который всегда заводит новую строку).
    """
    rows = _read_csv(path)
    database.init_db(db_file)
    conn = database.get_db_connection(db_file)
    tags: set[str] = set()
    imported = updated = skipped = errors = 0
    try:
        conn.execute("BEGIN IMMEDIATE")
        if mode == "replace":
            _clear_library(conn)
        for row in rows[1:] if rows and _looks_like_header(rows[0]) else rows:
            if len(row) < 3:
                skipped += 1
                continue
            tag = row[0].strip()
            command = row[2].strip()
            comment = row[3].strip() if len(row) > 3 else ""
            try:
                tid = int(row[1].strip())
            except ValueError:
                errors += 1
                continue
            if not tag or not command:
                skipped += 1
                continue
            existing = conn.execute(
                "SELECT id FROM commands WHERE tag = ? AND tid = ?", (tag, tid)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE commands SET command = ?, comment = ?, deleted = 0 WHERE id = ?",
                    (command, comment, existing["id"]),
                )
                updated += 1
            else:
                _insert_command(conn, tag, tid, command, comment)
                imported += 1
            tags.add(tag)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return ImportResult(imported, updated, skipped + errors, tuple(sorted(tags)))


def _looks_like_header(row: Sequence[str]) -> bool:
    return bool(row) and row[0].strip().lower() == COMMAND_FIELDS[0]


def export_tags_csv(db_file: str, path: str) -> int:
    """Комментарии тегов в CSV (`tag;comment`)."""
    comments = _tag_comments(db_file)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter=CSV_DELIMITER, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["tag", "comment"])
        for tag, comment in sorted(comments.items()):
            writer.writerow([tag, comment or ""])
    return len(comments)


def import_tags_csv(db_file: str, path: str) -> ImportResult:
    """Импорт комментариев тегов из CSV (существующий комментарий заменяется)."""
    rows = _read_csv(path)
    database.init_db(db_file)
    conn = database.get_db_connection(db_file)
    tags: set[str] = set()
    updated = skipped = 0
    try:
        conn.execute("BEGIN IMMEDIATE")
        for row in rows[1:] if rows and _looks_like_header(rows[0]) else rows:
            if len(row) < 2 or not row[0].strip():
                skipped += 1
                continue
            tag = row[0].strip()
            comment = row[1].strip()
            conn.execute(
                "INSERT OR REPLACE INTO tags (tag, comment) VALUES (?, ?)", (tag, comment)
            )
            tags.add(tag)
            updated += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return ImportResult(0, updated, skipped, tuple(sorted(tags)))


# --- Markdown ----------------------------------------------------------------


def _md_inline(text: str) -> str:
    """Код-инлайн с защитой от внутренних бэктиков."""
    return text.replace("`", "\\`")


def export_markdown(db_file: str, path: str, title: str = "Command library") -> int:
    """Весь каталог живых команд как Markdown (группировка по тегам).

    Каждая команда — строка списка `cmd` (с комментарием строки, если есть),
    у тега — заголовок уровня 2 и комментарий тега. Возвращает число команд.
    """
    rows = _command_rows(db_file)
    comments = _tag_comments(db_file)
    lines = [f"# {title}", ""]
    current: str | None = None
    for row in rows:
        tag = row["tag"]
        if tag != current:
            current = tag
            comment = (comments.get(tag) or "").strip()
            lines.append(f"## {tag}" + (f" — {comment}" if comment else "") + "")
        item = f"- `{_md_inline(row['command'])}`"
        if row["comment"].strip():
            item += f"  — {row['comment'].strip()}"
        lines.append(item)
    if not rows:
        lines.append("_Empty library — run a seed or save a command._")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    return len(rows)


def export_path(filename: str, backup_dir: str) -> str:
    """Куда писать файл переноса: относительное имя — в каталог бэкапов."""
    path = Path(filename)
    if path.is_absolute() or str(filename).startswith("./"):
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)
    Path(backup_dir).mkdir(parents=True, exist_ok=True)
    return str(Path(backup_dir) / path.name)


def import_path(filename: str, backup_dir: str) -> str:
    """Откуда читать файл переноса: как указано, иначе — поиск в каталоге бэкапов."""
    path = Path(filename)
    if path.exists() or path.is_absolute() or str(filename).startswith("./"):
        return str(path)
    in_backups = Path(backup_dir) / path.name
    return str(in_backups if in_backups.exists() else path)
