# Authors: markovskiy.pavel, Gemini (Google), Claude
"""
Database module v2 for IDvjPy_term.

Provides SQLite operations for managing tagged command history
with tag-local IDs (tid).

Schema:
- id: global unique ID (auto-increment)
- tag: tag name
- tid: tag-local ID (auto-increment per tag)
- command: command text
- timestamp: creation time
- deleted: soft-delete flag
"""
import sqlite3
import datetime
import json
import os
from typing import Tuple

def get_db_connection(db_file: str):
    """Establishes a connection to the database."""
    conn = sqlite3.connect(db_file, timeout=10)  # Wait up to 10 seconds if locked
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_file: str):
    """
    Initializes the database and creates all required tables.

    Creates ``db_file`` (and parent directories) if they do not exist,
    so a clone without a committed SQLite file still starts.

    Tables:
    - commands: stores tagged commands with tag-local IDs
    - tags: stores tag comments/descriptions
    """
    if not db_file:
        raise ValueError("database path is empty")
    parent = os.path.dirname(os.path.abspath(db_file))
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = get_db_connection(db_file)

    # Commands table
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

    # Add comment column to existing commands table if not exists (for migrations)
    try:
        conn.execute("ALTER TABLE commands ADD COLUMN comment TEXT DEFAULT ''")
    except Exception:
        pass  # Column already exists

    # Tags table for comments
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            tag TEXT PRIMARY KEY,
            comment TEXT
        );
    """)

    # Create index for faster tag queries
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_tag_tid
        ON commands (tag, tid) WHERE deleted = 0
    """)

    conn.commit()
    conn.close()

def _get_next_tid(conn, tag: str) -> int:
    """Get the next available tid for a given tag."""
    cursor = conn.execute(
        "SELECT COALESCE(MAX(tid), 0) + 1 FROM commands WHERE tag = ?",
        (tag,)
    )
    result = cursor.fetchone()
    return result[0] if result else 1

def add_command(db_file: str, command: str, tag: str) -> int:
    """
    Adds a new command to the history database with auto-incremented tid.

    Returns:
        The tid (tag-local ID) assigned to the command.
    """
    conn = get_db_connection(db_file)
    tid = _get_next_tid(conn, tag)

    conn.execute(
        "INSERT INTO commands (tag, tid, command, timestamp) VALUES (?, ?, ?, ?)",
        (tag, tid, command, datetime.datetime.now())
    )
    conn.commit()
    conn.close()
    return tid

def delete_commands_by_tag(db_file: str, tag: str):
    """Marks all commands with a given tag as deleted."""
    conn = get_db_connection(db_file)
    conn.execute("UPDATE commands SET deleted = 1 WHERE tag = ?", (tag,))
    conn.commit()
    conn.close()

def delete_command_by_tid(db_file: str, tag: str, tid: int):
    """Marks a single command as deleted by tag and tid."""
    conn = get_db_connection(db_file)
    conn.execute(
        "UPDATE commands SET deleted = 1 WHERE tag = ? AND tid = ?",
        (tag, tid)
    )
    conn.commit()
    conn.close()

def delete_command_by_global_id(db_file: str, global_id: int):
    """Marks a single command as deleted by global ID."""
    conn = get_db_connection(db_file)
    conn.execute("UPDATE commands SET deleted = 1 WHERE id = ?", (global_id,))
    conn.commit()
    conn.close()

def get_all_tags(db_file: str):
    """Fetches a unique list of all tags from the database."""
    conn = get_db_connection(db_file)
    cursor = conn.execute(
        "SELECT DISTINCT tag FROM commands WHERE deleted = 0 ORDER BY tag ASC"
    )
    tags = [row['tag'] for row in cursor.fetchall()]
    conn.close()
    return tags

def has_live_commands(db_file: str) -> bool:
    """True if the database has at least one non-deleted command."""
    if not db_file or not os.path.exists(db_file):
        return False
    conn = get_db_connection(db_file)
    row = conn.execute(
        "SELECT 1 FROM commands WHERE deleted = 0 LIMIT 1"
    ).fetchone()
    conn.close()
    return row is not None

def get_commands_by_tag(db_file: str, tag: str):
    """Fetches all commands for a given tag with their tids and comments."""
    conn = get_db_connection(db_file)
    cursor = conn.execute(
        "SELECT id, tid, command, comment FROM commands WHERE tag = ? AND deleted = 0 ORDER BY tid ASC",
        (tag,)
    )
    commands = cursor.fetchall()
    conn.close()
    return commands

def get_command_by_tid(db_file: str, tag: str, tid: int):
    """Fetches a single command by tag and tid."""
    conn = get_db_connection(db_file)
    cursor = conn.execute(
        "SELECT id, command FROM commands WHERE tag = ? AND tid = ? AND deleted = 0",
        (tag, tid)
    )
    result = cursor.fetchone()
    conn.close()
    return result

def get_command_by_global_id(db_file: str, global_id: int):
    """Fetches a single command by global ID."""
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
    Fetches all commands with their IDs, sorted by tag then tid.
    Returns both global ID and tag-local ID.
    """
    conn = get_db_connection(db_file)
    cursor = conn.execute(
        "SELECT id, tag, tid, command, comment FROM commands WHERE deleted = 0 ORDER BY tag ASC, tid ASC"
    )
    commands = cursor.fetchall()
    conn.close()
    return commands


def get_commands_by_prefix(db_file: str, prefix: str):
    """
    Returns distinct command strings that start with prefix (for Tab completion).
    """
    conn = get_db_connection(db_file)
    cursor = conn.execute(
        "SELECT DISTINCT command FROM commands WHERE deleted = 0 AND command LIKE ? ORDER BY command",
        (prefix + "%",)
    )
    result = [row["command"] for row in cursor.fetchall()]
    conn.close()
    return result

def set_tag_comment(db_file: str, tag: str, comment: str):
    """
    Sets or updates the comment for a tag.

    Args:
        db_file: Path to database file
        tag: Tag name
        comment: Comment text (use empty string to clear)
    """
    conn = get_db_connection(db_file)
    conn.execute(
        "INSERT OR REPLACE INTO tags (tag, comment) VALUES (?, ?)",
        (tag, comment)
    )
    conn.commit()
    conn.close()

def get_tag_comment(db_file: str, tag: str) -> str:
    """
    Fetches the comment for a tag.

    Returns:
        Comment text, or empty string if not found.
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
    Fetches all tags with their comments.

    Returns:
        List of tuples: [(tag, comment), ...]
    """
    conn = get_db_connection(db_file)
    cursor = conn.execute(
        "SELECT tag, comment FROM tags ORDER BY tag ASC"
    )
    results = cursor.fetchall()
    conn.close()
    return [(row['tag'], row['comment']) for row in results]

def _find_live_command(conn, tag: str, cmd_id: int):
    """Live command by tag-local tid, else by global id (same tag)."""
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
    Sets or updates the comment for a specific command.

    ``cmd_id`` is the tag-local tid first; if that row does not exist,
    it is treated as the global ``id`` (must belong to ``tag``).

    Returns:
        The updated row (id, tag, tid, ...), or None if not found.
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

    Returns:
        Comment text, or empty string if not found.
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
    Updates the command text for a specific command by tag and tid.

    Args:
        db_file: Path to database file
        tag: Tag name
        tid: Tag-local ID
        new_command: New command text

    Returns:
        True if command was updated, False if not found
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


def restore_commands_by_tag(db_file: str, tag: str) -> int:
    """Clears the soft-delete flag for all commands with this tag. Returns row count."""
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
    """Restores one soft-deleted command by tag and tid."""
    conn = get_db_connection(db_file)
    cursor = conn.execute(
        "UPDATE commands SET deleted = 0 WHERE tag = ? AND tid = ? AND deleted = 1",
        (tag, tid),
    )
    conn.commit()
    ok = cursor.rowcount > 0
    conn.close()
    return ok


def export_tag_to_file(db_file: str, tag: str, path: str) -> int:
    """Writes live commands of one tag to JSON. Returns how many commands were written."""
    commands = get_commands_by_tag(db_file, tag)
    payload = {
        "version": "2.0",
        "schema_version": "v2",
        "tag_filter": tag,
        "tag_comments": {tag: get_tag_comment(db_file, tag)},
        "commands": [
            {
                "tag": tag,
                "tid": row["tid"],
                "command": row["command"],
                "comment": row["comment"] or "",
            }
            for row in commands
        ],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return len(commands)


def import_tag_from_file(db_file: str, path: str) -> Tuple[str, int]:
    """Inserts commands from an export JSON (new tids). Returns (tag, count)."""
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    commands = payload.get("commands") or []
    tag = payload.get("tag_filter")
    if not tag and commands:
        tag = commands[0].get("tag")
    if not tag:
        raise ValueError("JSON has no tag_filter / commands[].tag")
    comments = payload.get("tag_comments") or {}
    comment = comments.get(tag) or ""
    if comment:
        set_tag_comment(db_file, tag, comment)
    n = 0
    for item in commands:
        if item.get("deleted"):
            continue
        cmd = (item.get("command") or "").strip()
        if not cmd:
            continue
        tid = add_command(db_file, cmd, tag)
        cmd_comment = (item.get("comment") or "").strip()
        if cmd_comment:
            set_command_comment(db_file, tag, tid, cmd_comment)
        n += 1
    return tag, n

