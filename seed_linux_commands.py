#!/usr/bin/env python3
"""
Seed the IDvjPy_term database with a canonical set of Linux commands.

Command order and tid mapping are defined in LINUX_COMMANDS.md.
Run: python seed_linux_commands.py --seed

Uses database_tags_file from settings.yml (same as app.py).
"""
import os
import argparse
import sys

try:
    import yaml
    import database_v2 as database
except ImportError as e:
    print(f"Error: {e}", file=sys.stderr)
    print("Install dependencies: pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)

FILE_SETTINGS = "settings.yml"
ENCODING = "utf-8"
DEFAULT_DB = "history_v2.db"

# Tag comments for ? listing
TAG_COMMENTS = {
    "file": "Файлы и каталоги",
    "net": "Сеть",
    "proc": "Процессы",
    "sys": "Система",
    "find": "Поиск",
    "archive": "Архивы",
    "text": "Текст и потоки",
}

# Ordered commands per tag (tid = 1-based index). See LINUX_COMMANDS.md.
SEED_COMMANDS = {
    "file": [
        "ls -la",
        "cp -r src dest",
        "mv src dest",
        "rm -i",
        "mkdir -p",
        "rmdir",
        "touch",
        "cat",
        "less",
        "head",
        "tail -f",
    ],
    "net": [
        "ss -tulnp",
        "ping -c 3",
        "curl -sI",
        "wget -qO-",
        "ssh",
        "rsync -avz",
        "scp",
        "ip addr",
        "ip route",
    ],
    "proc": [
        "ps aux",
        "top",
        "htop",
        "kill",
        "killall",
        "pkill",
        "nohup",
        "jobs",
        "fg",
        "bg",
    ],
    "sys": [
        "uname -a",
        "uptime",
        "free -h",
        "df -h",
        "date",
        "whoami",
        "id",
        "env",
        "systemctl status",
        "journalctl -xe",
    ],
    "find": [
        'find . -name "*.py"',
        "find . -type f -mtime -7",
        "find . -type d",
        "locate",
        "which",
        "whereis",
    ],
    "archive": [
        "tar -xvf",
        "tar -cvf",
        "tar -xzvf",
        "tar -czvf",
        "gzip",
        "gunzip",
        "zip -r",
        "unzip",
    ],
    "text": [
        "grep -r",
        "grep -E",
        "sed -i",
        "awk",
        "sort",
        "uniq",
        "wc -l",
        "cut",
        "tr",
        "xargs",
    ],
}


def get_db_file():
    """Read database path from settings.yml, same logic as app.py."""
    if not os.path.exists(FILE_SETTINGS):
        return DEFAULT_DB
    try:
        with open(FILE_SETTINGS, "r", encoding=ENCODING) as f:
            settings = yaml.safe_load(f)
        if settings:
            return settings.get("database_tags_file", DEFAULT_DB)
    except Exception:
        pass
    return DEFAULT_DB


def hard_delete_commands_by_tag(db_file: str, tag: str) -> None:
    """Remove all rows for tag so new inserts get tid 1, 2, 3..."""
    conn = database.get_db_connection(db_file)
    conn.execute("DELETE FROM commands WHERE tag = ?", (tag,))
    conn.commit()
    conn.close()


def run_seed(db_file: str) -> None:
    """(Re)seed seed tags: hard-delete then add commands in order."""
    database.init_db(db_file)
    for tag, commands in SEED_COMMANDS.items():
        hard_delete_commands_by_tag(db_file, tag)
        for cmd in commands:
            database.add_command(db_file, cmd, tag)
        comment = TAG_COMMENTS.get(tag, "")
        if comment:
            database.set_tag_comment(db_file, tag, comment)
    print(f"Seeded {len(SEED_COMMANDS)} tags into {db_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Seed IDvjPy_term DB with Linux commands (see LINUX_COMMANDS.md)"
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Replace seed tags with canonical command set",
    )
    args = parser.parse_args()
    if not args.seed:
        print("Run with --seed to populate the database.", file=sys.stderr)
        sys.exit(0)
    db_file = get_db_file()
    run_seed(db_file)


if __name__ == "__main__":
    main()
