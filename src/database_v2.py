# Authors: markovskiy.pavel, Gemini (Google), Claude, DeepSeek, Grok
"""
Модуль работы с базой данных v2 для IDvjPy_term.

Предоставляет операции SQLite для управления историей команд с тегами
и локальными для тега идентификаторами (tid).

Схема:
- id: глобальный уникальный ID (автоинкремент)
- tag: имя тега
- tid: локальный для тега ID (автоинкремент внутри тега)
- command: текст команды
- timestamp: время создания
- deleted: флаг мягкого удаления
"""
import datetime
import json
import os
import sqlite3


def get_db_connection(db_file: str):
    """Устанавливает соединение с базой данных."""
    conn = sqlite3.connect(db_file, timeout=10)  # Ждём до 10 секунд, если база заблокирована
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_file: str):
    """
    Инициализирует базу данных и создаёт все необходимые таблицы.

    Создаёт ``db_file`` (и родительские каталоги), если их нет,
    чтобы клон без закоммиченного файла SQLite всё равно запускался.

    Таблицы:
    - commands: хранит команды с тегами и локальными для тега ID
    - tags: хранит комментарии/описания тегов
    """
    if not db_file:
        raise ValueError("database path is empty")
    parent = os.path.dirname(os.path.abspath(db_file))
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = get_db_connection(db_file)

    # Таблица commands
    conn.execute("""
        CREATE TABLE IF NOT EXISTS commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tag TEXT NOT NULL,
            tid INTEGER NOT NULL,
            command TEXT NOT NULL,
            timestamp DATETIME NOT NULL,
            deleted INTEGER DEFAULT 0,
            comment TEXT DEFAULT '',
            UNIQUE(tag, tid)
        );
    """)

    # Добавляем колонку comment в существующую таблицу commands, если её нет (для миграций)
    try:
        conn.execute("ALTER TABLE commands ADD COLUMN comment TEXT DEFAULT ''")
    except Exception:
        pass  # Колонка уже существует

    # Счётчики использования (v1.39): use_count / last_used добавляются на лету в live-БД.
    _cols = [row[1] for row in conn.execute("PRAGMA table_info(commands)").fetchall()]
    if "use_count" not in _cols:
        conn.execute(
            "ALTER TABLE commands ADD COLUMN use_count INTEGER NOT NULL DEFAULT 0"
        )
    if "last_used" not in _cols:
        conn.execute("ALTER TABLE commands ADD COLUMN last_used DATETIME")

    # Таблица tags для комментариев
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            tag TEXT PRIMARY KEY,
            comment TEXT
        );
    """)

    tag_cols = {row[1] for row in conn.execute("PRAGMA table_info(tags)").fetchall()}
    if "metadata" not in tag_cols:
        conn.execute("ALTER TABLE tags ADD COLUMN metadata TEXT NOT NULL DEFAULT '{}'")

    # Индекс для ускорения запросов по тегу
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_tag_tid
        ON commands (tag, tid) WHERE deleted = 0
    """)

    conn.commit()
    conn.close()

def _get_next_tid(conn, tag: str) -> int:
    """Возвращает следующий свободный tid для заданного тега."""
    cursor = conn.execute(
        "SELECT COALESCE(MAX(tid), 0) + 1 FROM commands WHERE tag = ?",
        (tag,)
    )
    result = cursor.fetchone()
    return result[0] if result else 1

def add_command(db_file: str, command: str, tag: str) -> int:
    """
    Добавляет новую команду в базу истории с автоинкрементным tid.

    Возвращает:
        tid (локальный для тега ID), назначенный команде.
    """
    conn = get_db_connection(db_file)
    try:
        conn.execute("BEGIN IMMEDIATE")
        tid = _get_next_tid(conn, tag)
        conn.execute(
            "INSERT INTO commands (tag, tid, command, timestamp) VALUES (?, ?, ?, ?)",
            (tag, tid, command, datetime.datetime.now())
        )
        conn.commit()
        return tid
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def delete_commands_by_tag(db_file: str, tag: str) -> int:
    """Помечает live-команды с заданным тегом как удалённые. Возвращает число строк."""
    conn = get_db_connection(db_file)
    cursor = conn.execute(
        "UPDATE commands SET deleted = 1 WHERE tag = ? AND deleted = 0",
        (tag,),
    )
    conn.commit()
    n = cursor.rowcount
    conn.close()
    return n

def hard_delete_commands_by_tag(db_file: str, tag: str) -> None:
    """Полностью удаляет тег, чтобы следующая add_command начиналась с tid 1."""
    conn = get_db_connection(db_file)
    conn.execute("DELETE FROM commands WHERE tag = ?", (tag,))
    conn.execute("DELETE FROM tags WHERE tag = ?", (tag,))
    conn.commit()
    conn.close()

def delete_command_by_tid(db_file: str, tag: str, tid: int):
    """Помечает одну команду как удалённую по тегу и tid."""
    conn = get_db_connection(db_file)
    conn.execute(
        "UPDATE commands SET deleted = 1 WHERE tag = ? AND tid = ?",
        (tag, tid)
    )
    conn.commit()
    conn.close()


def get_all_tags(db_file: str):
    """Возвращает уникальный список всех тегов из базы данных."""
    conn = get_db_connection(db_file)
    cursor = conn.execute(
        "SELECT DISTINCT tag FROM commands WHERE deleted = 0 ORDER BY tag ASC"
    )
    tags = [row['tag'] for row in cursor.fetchall()]
    conn.close()
    return tags


def get_hidden_tags(db_file: str) -> list[str]:
    """Теги, у которых есть только мягко-удалённые команды (ничего live)."""
    conn = get_db_connection(db_file)
    cursor = conn.execute(
        """
        SELECT DISTINCT tag FROM commands
        WHERE deleted = 1
          AND tag NOT IN (SELECT DISTINCT tag FROM commands WHERE deleted = 0)
        ORDER BY tag ASC
        """
    )
    tags = [row["tag"] for row in cursor.fetchall()]
    conn.close()
    return tags

def has_live_commands(db_file: str) -> bool:
    """True, если в базе есть хотя бы одна неудалённая команда."""
    if not db_file or not os.path.exists(db_file):
        return False
    conn = get_db_connection(db_file)
    row = conn.execute(
        "SELECT 1 FROM commands WHERE deleted = 0 LIMIT 1"
    ).fetchone()
    conn.close()
    return row is not None

def get_commands_by_tag(db_file: str, tag: str):
    """Возвращает все команды для заданного тега вместе с их tid и комментариями."""
    conn = get_db_connection(db_file)
    cursor = conn.execute(
        "SELECT id, tid, command, comment FROM commands WHERE tag = ? AND deleted = 0 ORDER BY tid ASC",
        (tag,)
    )
    commands = cursor.fetchall()
    conn.close()
    return commands

def get_command_by_tid(db_file: str, tag: str, tid: int):
    """Возвращает одну команду по тегу и tid."""
    conn = get_db_connection(db_file)
    cursor = conn.execute(
        "SELECT id, command FROM commands WHERE tag = ? AND tid = ? AND deleted = 0",
        (tag, tid)
    )
    result = cursor.fetchone()
    conn.close()
    return result

def get_command_by_global_id(db_file: str, global_id: int):
    """Возвращает одну команду по глобальному ID."""
    conn = get_db_connection(db_file)
    cursor = conn.execute(
        "SELECT id, command FROM commands WHERE id = ? AND deleted = 0",
        (global_id,)
    )
    result = cursor.fetchone()
    conn.close()
    return result

def get_all_commands_with_ids(db_file: str):
    """
    Возвращает все команды с их ID, отсортированные по тегу, затем по tid.
    Возвращает и глобальный ID, и локальный для тега ID.
    """
    conn = get_db_connection(db_file)
    cursor = conn.execute(
        "SELECT id, tag, tid, command, comment, use_count, last_used FROM commands "
        "WHERE deleted = 0 ORDER BY tag ASC, tid ASC"
    )
    commands = cursor.fetchall()
    conn.close()
    return commands


def bump_command_usage(db_file: str, command: str) -> int:
    """
    Инкрементит счётчик запусков для live-команд с этим текстом.

    Атрибуция: текст исполняемой строки совпал с сохранённой командой
    (в т.ч. через !tag[tid] / !ID / повтор из истории).

    Возвращает:
        Число обновлённых строк (0 — совпадений не было).
    """
    conn = get_db_connection(db_file)
    try:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.execute(
            "UPDATE commands SET use_count = use_count + 1, last_used = ? "
            "WHERE command = ? AND deleted = 0",
            (datetime.datetime.now(), command),
        )
        conn.commit()
        return cursor.rowcount
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def usage_stats(db_file: str) -> dict:
    """
    Сводка по библиотеке для `:stats`.

    Возвращает:
        dict: счётчики tags/live/deleted/never_run, top-10 по запускам,
        per_tag — агрегаты по каждому тегу.
    """
    conn = get_db_connection(db_file)
    try:
        live = conn.execute(
            "SELECT COUNT(*) FROM commands WHERE deleted = 0"
        ).fetchone()[0]
        deleted = conn.execute(
            "SELECT COUNT(*) FROM commands WHERE deleted = 1"
        ).fetchone()[0]
        tags = conn.execute(
            "SELECT COUNT(DISTINCT tag) FROM commands WHERE deleted = 0"
        ).fetchone()[0]
        never_run = conn.execute(
            "SELECT COUNT(*) FROM commands WHERE deleted = 0 "
            "AND (use_count IS NULL OR use_count = 0)"
        ).fetchone()[0]
        per_tag = [
            dict(row)
            for row in conn.execute(
                "SELECT tag, COUNT(*) AS live, "
                "COALESCE(SUM(use_count), 0) AS runs, "
                "MAX(last_used) AS last_used "
                "FROM commands WHERE deleted = 0 "
                "GROUP BY tag ORDER BY runs DESC, tag ASC"
            ).fetchall()
        ]
        top = [
            dict(row)
            for row in conn.execute(
                "SELECT id, tag, tid, command, use_count, last_used "
                "FROM commands WHERE deleted = 0 AND use_count > 0 "
                "ORDER BY use_count DESC, last_used DESC LIMIT 10"
            ).fetchall()
        ]
        return {
            "tags": tags,
            "live": live,
            "deleted": deleted,
            "never_run": never_run,
            "per_tag": per_tag,
            "top": top,
        }
    finally:
        conn.close()


def _escape_like(text: str) -> str:
    """Экранирует LIKE-метасимволы (% _ \\) для подстановки в pattern с ESCAPE '\\'."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_commands_by_content(db_file: str, needle: str, limit: int = 200):
    """
    Подстрочный поиск по тексту команд и комментариям (live-строки).

    Case-insensitive как LIKE (ASCII). Символы % и _ ищутся буквально.

    Возвращает:
        (rows, total): rows — до limit записей (id, tag, tid, command, comment)
        в порядке tag/tid; total — полное число совпадений.
    """
    needle = (needle or "").strip()
    if not needle:
        return [], 0
    pattern = "%" + _escape_like(needle) + "%"
    where = "(command LIKE ? ESCAPE '\\' OR comment LIKE ? ESCAPE '\\') AND deleted = 0"
    conn = get_db_connection(db_file)
    try:
        total = conn.execute(
            "SELECT COUNT(*) FROM commands WHERE " + where,
            (pattern, pattern),
        ).fetchone()[0]
        rows = conn.execute(
            "SELECT id, tag, tid, command, comment FROM commands WHERE "
            + where
            + " ORDER BY tag ASC, tid ASC LIMIT ?",
            (pattern, pattern, limit),
        ).fetchall()
    finally:
        conn.close()
    return rows, total

def set_tag_comment(db_file: str, tag: str, comment: str):
    """
    Устанавливает или обновляет комментарий для тега.

    Аргументы:
        db_file: путь к файлу базы данных
        tag: имя тега
        comment: текст комментария (пустая строка — очистить)
    """
    conn = get_db_connection(db_file)
    conn.execute(
        "INSERT INTO tags (tag, comment) VALUES (?, ?) "
        "ON CONFLICT(tag) DO UPDATE SET comment = excluded.comment",
        (tag, comment),
    )
    conn.commit()
    conn.close()

TAG_METADATA_FIELDS = frozenset({"risk", "utilities", "os", "interactive", "topic", "example"})
TAG_RISK_LEVELS = frozenset({"low", "medium", "high", "critical"})


def validate_tag_metadata(metadata: object) -> dict[str, object]:
    """Проверяет переносимую, намеренно компактную схему метаданных тега."""
    if not isinstance(metadata, dict):
        raise ValueError("tag metadata must be an object")
    unknown = set(metadata) - TAG_METADATA_FIELDS
    if unknown:
        raise ValueError(f"unknown tag metadata field(s): {', '.join(sorted(unknown))}")
    result: dict[str, object] = {}
    for key, value in metadata.items():
        if key == "risk":
            if not isinstance(value, str) or value not in TAG_RISK_LEVELS:
                raise ValueError("risk must be low, medium, high, or critical")
        elif key == "interactive":
            if not isinstance(value, bool):
                raise ValueError("interactive must be a boolean")
        elif key in {"utilities", "os"}:
            if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
                raise ValueError(f"{key} must be an array of strings")
        elif not isinstance(value, str):
            raise ValueError(f"{key} must be a string")
        result[key] = value
    if len(json.dumps(result, ensure_ascii=False)) > 8192:
        raise ValueError("tag metadata exceeds 8192 bytes")
    return result


def set_tag_metadata(db_file: str, tag: str, metadata: object) -> None:
    """Заменяет проверенные метаданные одного тега; пустой объект очищает их."""
    value = validate_tag_metadata(metadata)
    conn = get_db_connection(db_file)
    try:
        conn.execute(
            "INSERT INTO tags (tag, metadata) VALUES (?, ?) "
            "ON CONFLICT(tag) DO UPDATE SET metadata = excluded.metadata",
            (tag, json.dumps(value, ensure_ascii=False, sort_keys=True)),
        )
        conn.commit()
    finally:
        conn.close()


def get_tag_metadata(db_file: str, tag: str) -> dict[str, object]:
    conn = get_db_connection(db_file)
    try:
        row = conn.execute("SELECT metadata FROM tags WHERE tag = ?", (tag,)).fetchone()
        if not row or not row["metadata"]:
            return {}
        try:
            return validate_tag_metadata(json.loads(row["metadata"]))
        except (ValueError, json.JSONDecodeError):
            return {}
    finally:
        conn.close()


def get_all_tag_metadata(db_file: str) -> dict[str, dict[str, object]]:
    conn = get_db_connection(db_file)
    try:
        rows = conn.execute("SELECT tag, metadata FROM tags ORDER BY tag").fetchall()
        result = {}
        for row in rows:
            try:
                result[row["tag"]] = validate_tag_metadata(json.loads(row["metadata"] or "{}"))
            except (ValueError, json.JSONDecodeError):
                result[row["tag"]] = {}
        return result
    finally:
        conn.close()


def get_tag_comment(db_file: str, tag: str) -> str:
    """
    Fetches the comment for a tag.

    Возвращает:
        Текст комментария или пустую строку, если не найдено.
    """
    conn = get_db_connection(db_file)
    cursor = conn.execute(
        "SELECT comment FROM tags WHERE tag = ?",
        (tag,)
    )
    result = cursor.fetchone()
    conn.close()
    return result['comment'] if result else ""

def get_all_tags_with_comments(db_file: str):
    """
    Возвращает все теги с их комментариями.

    Возвращает:
        Список кортежей: [(tag, comment), ...]
    """
    conn = get_db_connection(db_file)
    cursor = conn.execute(
        "SELECT tag, comment FROM tags ORDER BY tag ASC"
    )
    results = cursor.fetchall()
    conn.close()
    return [(row['tag'], row['comment']) for row in results]

def _find_live_command(conn, tag: str, cmd_id: int):
    """Live-команда по локальному для тега tid, иначе по глобальному id (в том же теге)."""
    cursor = conn.execute(
        "SELECT id, tag, tid, command, comment FROM commands "
        "WHERE tag = ? AND tid = ? AND deleted = 0",
        (tag, cmd_id),
    )
    row = cursor.fetchone()
    if row:
        return row
    cursor = conn.execute(
        "SELECT id, tag, tid, command, comment FROM commands "
        "WHERE id = ? AND tag = ? AND deleted = 0",
        (cmd_id, tag),
    )
    return cursor.fetchone()


def set_command_comment(db_file: str, tag: str, cmd_id: int, comment: str):
    """
    Устанавливает или обновляет комментарий для конкретной команды.

    ``cmd_id`` — сначала локальный для тега tid; если такой строки нет,
    он трактуется как глобальный ``id`` (должен принадлежать ``tag``).

    Возвращает:
        Обновлённую строку (id, tag, tid, ...) или None, если не найдено.
    """
    conn = get_db_connection(db_file)
    row = _find_live_command(conn, tag, cmd_id)
    if not row:
        conn.close()
        return None
    conn.execute(
        "UPDATE commands SET comment = ? WHERE id = ? AND deleted = 0",
        (comment, row["id"]),
    )
    conn.commit()
    conn.close()
    return row

def get_command_comment(db_file: str, tag: str, tid: int) -> str:
    """
    Fetches the comment for a specific command.

    Возвращает:
        Текст комментария или пустую строку, если не найдено.
    """
    conn = get_db_connection(db_file)
    cursor = conn.execute(
        "SELECT comment FROM commands WHERE tag = ? AND tid = ? AND deleted = 0",
        (tag, tid)
    )
    result = cursor.fetchone()
    conn.close()
    return result['comment'] if result else ""

def update_command_by_tid(db_file: str, tag: str, tid: int, new_command: str):
    """
    Обновляет текст команды для конкретной команды по тегу и tid.

    Аргументы:
        db_file: путь к файлу базы данных
        tag: имя тега
        tid: локальный для тега ID
        new_command: новый текст команды

    Возвращает:
        True, если команда обновлена, False, если не найдена
    """
    conn = get_db_connection(db_file)
    cursor = conn.execute(
        "UPDATE commands SET command = ? WHERE tag = ? AND tid = ? AND deleted = 0",
        (new_command, tag, tid)
    )
    conn.commit()
    rows_updated = cursor.rowcount
    conn.close()
    return rows_updated > 0


def move_command_by_tid(db_file: str, tag: str, tid: int, new_tag: str):
    """
    Переносит одну live-команду в другой тег (новый tid в конце целевого тега).

    Комментарий команды переносится вместе с ней; комментарий тега не трогаем.

    Возвращает:
        (new_tid, global_id) новой строки или None, если команда не найдена.
    """
    conn = get_db_connection(db_file)
    try:
        row = conn.execute(
            "SELECT id, command, comment FROM commands WHERE tag = ? AND tid = ? AND deleted = 0",
            (tag, tid),
        ).fetchone()
        if row is None:
            return None
        new_tid = _get_next_tid(conn, new_tag)
        conn.execute(
            "UPDATE commands SET tag = ?, tid = ? WHERE id = ?",
            (new_tag, new_tid, row["id"]),
        )
        conn.commit()
        return new_tid, row["id"]
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def rename_tag(db_file: str, old_tag: str, new_tag: str) -> int:
    """
    Переименовывает тег целиком (все строки — live и мягко-удалённые).

    Комментарий тега переносится в новый тег. Возвращает число переименованных
    строк; если целевой тег уже существует — ValueError.
    """
    conn = get_db_connection(db_file)
    try:
        tag_comment_exists = conn.execute(
            "SELECT 1 FROM tags WHERE tag = ?", (new_tag,)
        ).fetchone()
        tag_rows_exist = conn.execute(
            "SELECT 1 FROM commands WHERE tag = ? LIMIT 1", (new_tag,)
        ).fetchone()
        if tag_comment_exists or tag_rows_exist:
            raise ValueError(f"Tag '{new_tag}' already exists")
        row_count = conn.execute(
            "SELECT COUNT(*) FROM commands WHERE tag = ?", (old_tag,)
        ).fetchone()[0]
        if row_count == 0:
            return 0
        conn.execute("UPDATE commands SET tag = ? WHERE tag = ?", (new_tag, old_tag))
        conn.execute(
            "UPDATE OR IGNORE tags SET tag = ? WHERE tag = ?", (new_tag, old_tag)
        )
        conn.commit()
        return row_count
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def restore_commands_by_tag(db_file: str, tag: str) -> int:
    """Снимает флаг мягкого удаления со всех команд с этим тегом. Возвращает число строк."""
    conn = get_db_connection(db_file)
    cursor = conn.execute(
        "UPDATE commands SET deleted = 0 WHERE tag = ? AND deleted = 1",
        (tag,),
    )
    conn.commit()
    n = cursor.rowcount
    conn.close()
    return n


def restore_command_by_tid(db_file: str, tag: str, tid: int) -> bool:
    """Восстанавливает одну мягко-удалённую команду по тегу и tid."""
    conn = get_db_connection(db_file)
    cursor = conn.execute(
        "UPDATE commands SET deleted = 0 WHERE tag = ? AND tid = ? AND deleted = 1",
        (tag, tid),
    )
    conn.commit()
    ok = cursor.rowcount > 0
    conn.close()
    return ok


