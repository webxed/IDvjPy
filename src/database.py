# Authors: markovskiy.pavel, Gemini (Google)
"""
Database module for IDvjPy_term.

Provides SQLite operations for managing tagged command history,
including adding, querying, and soft-deleting commands.
"""
import sqlite3
import datetime

def get_db_connection(db_file: str):
    """Establishes a connection to the database."""
    conn = sqlite3.connect(db_file, timeout=10) # Wait up to 10 seconds if locked
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_file: str):
    """Initializes the database and creates the commands table if it doesn't exist."""
    conn = get_db_connection(db_file)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            command TEXT NOT NULL,
            tag TEXT,
            timestamp DATETIME NOT NULL,
            deleted INTEGER DEFAULT 0
        );
    """)
    # Add the 'deleted' column if it doesn't exist, for backward compatibility
    try:
        conn.execute("ALTER TABLE commands ADD COLUMN deleted INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass # Column already exists
    conn.commit()
    conn.close()

def add_command(db_file: str, command: str, tag: str):
    """Adds a new command to the history database."""
    conn = get_db_connection(db_file)
    conn.execute(
        "INSERT INTO commands (command, tag, timestamp) VALUES (?, ?, ?)",
        (command, tag, datetime.datetime.now())
    )
    conn.commit()
    conn.close()

def delete_commands_by_tag(db_file: str, tag: str):
    """Marks all commands with a given tag as deleted."""
    conn = get_db_connection(db_file)
    conn.execute("UPDATE commands SET deleted = 1 WHERE tag = ?", (tag,))
    conn.commit()
    conn.close()

def delete_command_by_id(db_file: str, command_id: int):
    """Marks a single command as deleted by its ID."""
    conn = get_db_connection(db_file)
    conn.execute("UPDATE commands SET deleted = 1 WHERE id = ?", (command_id,))
    conn.commit()
    conn.close()

def get_all_tags(db_file: str):
    """Fetches a unique list of all tags from the database."""
    conn = get_db_connection(db_file)
    cursor = conn.execute("SELECT DISTINCT tag FROM commands WHERE deleted = 0 ORDER BY tag ASC")
    tags = [row['tag'] for row in cursor.fetchall()]
    conn.close()
    return tags

def get_commands_by_tag(db_file: str, tag: str):
    """Fetches all commands for a given tag."""
    conn = get_db_connection(db_file)
    cursor = conn.execute("SELECT id, command FROM commands WHERE tag = ? AND deleted = 0 ORDER BY id ASC", (tag,))
    commands = cursor.fetchall()
    conn.close()
    return commands

def get_all_commands_with_ids(db_file: str):
    """Fetches all commands with their IDs, sorted by id."""
    conn = get_db_connection(db_file)
    cursor = conn.execute("SELECT id, command, tag FROM commands WHERE deleted = 0 ORDER BY id ASC")
    commands = cursor.fetchall()
    conn.close()
    return commands
