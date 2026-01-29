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

def get_db_connection(db_file: str):
    """Establishes a connection to the database."""
    conn = sqlite3.connect(db_file, timeout=10)  # Wait up to 10 seconds if locked
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_file: str):
    """
    Initializes the database and creates all required tables.

    Tables:
    - commands: stores tagged commands with tag-local IDs
    - tags: stores tag comments/descriptions
    """
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

def set_command_comment(db_file: str, tag: str, tid: int, comment: str):
    """
    Sets or updates the comment for a specific command.

    Args:
        db_file: Path to database file
        tag: Tag name
        tid: Tag-local ID
        comment: Comment text (use empty string to clear)
    """
    conn = get_db_connection(db_file)
    conn.execute(
        "UPDATE commands SET comment = ? WHERE tag = ? AND tid = ?",
        (comment, tag, tid)
    )
    conn.commit()
    conn.close()

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

