"""Shared helpers for handbook seed scripts (git, docker, helm, …)."""
import argparse
import os
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
DEFAULT_DB = "mytags.db"


def get_db_file() -> str:
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
    conn = database.get_db_connection(db_file)
    conn.execute("DELETE FROM commands WHERE tag = ?", (tag,))
    conn.execute("DELETE FROM tags WHERE tag = ?", (tag,))
    conn.commit()
    conn.close()


def run_seed(db_file: str, seed_tags: dict) -> int:
    """Replace tags in seed_tags; return number of commands inserted."""
    database.init_db(db_file)
    n = 0
    for tag, (tag_comment, commands) in seed_tags.items():
        hard_delete_commands_by_tag(db_file, tag)
        for cmd, cmd_comment in commands:
            tid = database.add_command(db_file, cmd, tag)
            if cmd_comment:
                database.set_command_comment(db_file, tag, tid, cmd_comment)
            n += 1
        if tag_comment:
            database.set_tag_comment(db_file, tag, tag_comment)
    return n


def seed_cli(
    *,
    description: str,
    seed_help: str,
    seed_tags: dict,
    argv: list[str],
) -> None:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--seed", action="store_true", help=seed_help)
    parser.add_argument(
        "--db",
        default="",
        help="SQLite file (default: settings.yml database_tags_file)",
    )
    args = parser.parse_args(argv[1:])
    if not args.seed:
        print("Run with --seed to populate the database.", file=sys.stderr)
        sys.exit(0)
    db_file = args.db or get_db_file()
    n = run_seed(db_file, seed_tags)
    print(f"Seeded {len(seed_tags)} tags ({n} commands) into {db_file}")
