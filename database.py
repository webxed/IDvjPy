# Authors: markovskiy.pavel, Gemini (Google)
import sqlite3
import datetime

DB_FILE = "history.db"

def get_db_connection():
    """Establishes a connection to the database."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database and creates the commands table if it doesn't exist."""
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            command TEXT NOT NULL,
            tag TEXT,
            timestamp DATETIME NOT NULL
        );
    """)
    conn.commit()
    conn.close()

def add_command(command: str, tag: str):
    """Adds a new command to the history database."""
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO commands (command, tag, timestamp) VALUES (?, ?, ?)",
        (command, tag, datetime.datetime.now())
    )
    conn.commit()
    conn.close()

def get_all_commands():
    """Fetches all commands from the database in chronological order."""
    conn = get_db_connection()
    cursor = conn.execute("SELECT command, tag FROM commands ORDER BY timestamp ASC")
    commands = cursor.fetchall()
    conn.close()
    return commands

def get_all_tags():
    """Fetches a unique list of all tags from the database."""
    conn = get_db_connection()
    cursor = conn.execute("SELECT DISTINCT tag FROM commands ORDER BY tag ASC")
    tags = [row['tag'] for row in cursor.fetchall()]
    conn.close()
    return tags

def get_commands_by_tag(tag: str):
    """Fetches all commands for a given tag."""
    conn = get_db_connection()
    cursor = conn.execute("SELECT command FROM commands WHERE tag = ? ORDER BY timestamp ASC", (tag,))
    commands = [row['command'] for row in cursor.fetchall()]
    conn.close()
    return commands
