#!/usr/bin/env python3
"""CLI переноса библиотеки тегов (`python3 backup_db.py <команда>`).

Тонкая оболочка: разбор аргументов, пути (`settings.yml` и `backups/` — из
рабочей директории) и печать. Всё, что связано с форматами, живёт в
`src/db_transfer.py` — одна реализация с TUI (`:export`, `:import`, `:backup`),
поэтому JSON-схема и семантика импорта больше не расходятся.

Команды:
  export / import                    JSON (вся база или `--tag`)
  export-csv / import-csv            команды CSV (адресно по tid)
  export-tags-csv / import-tags-csv  комментарии тегов CSV
  list                               теги с числом команд и комментариями
  backup                             снимок SQLite + JSON + CSV в backups/
  restore <файл>                     вернуть JSON/CSV в базу (со снимком до)
"""
from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path

import yaml

import db_transfer
import seed_lib

DEFAULT_DB = "mytags.db"
DEFAULT_BACKUP_DIR = "backups"


def data_dir() -> Path:
    """settings.yml, БД и backups/ читаются из рабочей директории, не из src/."""
    return Path.cwd()


def load_settings() -> str:
    """Имя файла базы из settings.yml (`database_tags_file`)."""
    path = data_dir() / "settings.yml"
    if path.exists():
        try:
            settings = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            settings = {}
        return settings.get("database_tags_file", DEFAULT_DB) or DEFAULT_DB
    return DEFAULT_DB


def load_backup_dir() -> str:
    """Каталог бэкапов из settings.yml (`backup_dir`), по умолчанию `backups`."""
    path = data_dir() / "settings.yml"
    backup_dir = DEFAULT_BACKUP_DIR
    if path.exists():
        try:
            settings = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            backup_dir = settings.get("backup_dir", DEFAULT_BACKUP_DIR) or DEFAULT_BACKUP_DIR
        except (OSError, yaml.YAMLError):
            backup_dir = DEFAULT_BACKUP_DIR
    directory = data_dir() / backup_dir
    directory.mkdir(parents=True, exist_ok=True)
    return str(directory)


def _db_file(explicit: str | None) -> str:
    """Путь к базе: `--db`, иначе имя из settings.yml (в рабочей директории)."""
    if explicit:
        return explicit
    name = load_settings()
    candidate = Path(name)
    return str(candidate if candidate.is_absolute() else data_dir() / name)


def _import_file(
    db_file: str,
    path: str,
    *,
    mode: str,
    skip_existing: bool,
    preserve_tid: bool = False,
) -> db_transfer.ImportResult:
    """Импорт файла переноса по расширению и заголовку (JSON / CSV / CSV тегов)."""
    suffix = Path(path).suffix.lower()
    if suffix == ".json":
        return db_transfer.import_json(
            db_file,
            path,
            mode=mode,
            skip_existing=skip_existing,
            preserve_tid=preserve_tid,
        )
    if suffix == ".csv":
        if db_transfer.csv_schema(path) == "tags":
            return db_transfer.import_tags_csv(db_file, path)
        return db_transfer.import_commands_csv(db_file, path, mode=mode)
    raise ValueError(f"unsupported file type: {path} (expected .json or .csv)")


def _print_result(result: db_transfer.ImportResult) -> None:
    """Единый итог импорта для всех команд CLI."""
    print("\n✓ Import complete:")
    print(f"  Imported: {result.imported}")
    print(f"  Updated:  {result.updated}")
    if result.skipped:
        print(f"  Skipped:  {result.skipped}")
    if result.tags:
        print(f"  Tags:     {', '.join(result.tags)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="backup_db.py",
        description="Перенос библиотеки тегов IDvjPy_term (JSON/CSV) и снимки SQLite.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Примеры:\n"
            "  python3 backup_db.py export backup.json\n"
            "  python3 backup_db.py export backup.json --tag python --include-deleted\n"
            "  python3 backup_db.py import backup.json --mode replace\n"
            "  python3 backup_db.py export-csv commands.csv\n"
            "  python3 backup_db.py list --show-comments\n"
            "  python3 backup_db.py backup\n"
            "  python3 backup_db.py restore backup.json\n\n"
            "JSON: перенос и слияние (новые tid по умолчанию, глобальные id из\n"
            "файла не берутся — иначе чужой id мог затереть другую команду).\n"
            "Точный слепок базы — SQLite-снимок: `backup`, `:backup`, `--seed`.\n"
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser("export", help="Экспорт базы в JSON")
    export_parser.add_argument("output", help="Путь JSON (относительный — в backups/)")
    export_parser.add_argument("--tag", help="Только этот тег")
    export_parser.add_argument(
        "--include-deleted", action="store_true", help="Включить мягко удалённые строки"
    )
    export_parser.add_argument("--db", help="Файл базы (по умолчанию из settings.yml)")

    import_parser = subparsers.add_parser("import", help="Импорт JSON в базу")
    import_parser.add_argument("input", help="Путь JSON (ищется и в backups/)")
    import_parser.add_argument(
        "--mode", choices=["merge", "replace"], default="merge",
        help="merge (по умолчанию) или replace (очистить библиотеку перед импортом)",
    )
    import_parser.add_argument(
        "--keep-tids", action="store_true",
        help="Сохранять tid из файла, если он свободен (по умолчанию — новые)",
    )
    import_parser.add_argument("--db", help="Файл базы (по умолчанию из settings.yml)")

    export_csv_parser = subparsers.add_parser("export-csv", help="Команды в CSV")
    export_csv_parser.add_argument("output", help="Путь CSV (относительный — в backups/)")
    export_csv_parser.add_argument("--tag", help="Только этот тег")
    export_csv_parser.add_argument(
        "--include-deleted", action="store_true", help="Включить мягко удалённые строки"
    )
    export_csv_parser.add_argument("--db", help="Файл базы (по умолчанию из settings.yml)")

    import_csv_parser = subparsers.add_parser("import-csv", help="Команды из CSV")
    import_csv_parser.add_argument("input", help="Путь CSV (ищется и в backups/)")
    import_csv_parser.add_argument(
        "--mode", choices=["merge", "replace"], default="merge",
        help="merge (обновить/добавить по tid) или replace",
    )
    import_csv_parser.add_argument("--db", help="Файл базы (по умолчанию из settings.yml)")

    export_tags_parser = subparsers.add_parser(
        "export-tags-csv", help="Комментарии тегов в CSV"
    )
    export_tags_parser.add_argument("output", help="Путь CSV (относительный — в backups/)")
    export_tags_parser.add_argument("--db", help="Файл базы (по умолчанию из settings.yml)")

    import_tags_parser = subparsers.add_parser(
        "import-tags-csv", help="Комментарии тегов из CSV"
    )
    import_tags_parser.add_argument("input", help="Путь CSV (ищется и в backups/)")
    import_tags_parser.add_argument("--db", help="Файл базы (по умолчанию из settings.yml)")

    list_parser = subparsers.add_parser("list", help="Список тегов и число команд")
    list_parser.add_argument("--show-comments", action="store_true", help="С комментариями")
    list_parser.add_argument("--db", help="Файл базы (по умолчанию из settings.yml)")

    backup_parser = subparsers.add_parser(
        "backup", help="Снимок SQLite + JSON + CSV в backups/"
    )
    backup_parser.add_argument("--db", help="Файл базы (по умолчанию из settings.yml)")

    restore_parser = subparsers.add_parser(
        "restore", help="Вернуть JSON/CSV в базу (снимок SQLite делается до)"
    )
    restore_parser.add_argument("input", help="Путь файла (ищется и в backups/)")
    restore_parser.add_argument(
        "--mode", choices=["merge", "replace"], default="merge",
        help="merge (по умолчанию) или replace (очистить библиотеку перед импортом)",
    )
    restore_parser.add_argument("--db", help="Файл базы (по умолчанию из settings.yml)")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    db_file = _db_file(args.db)
    backup_dir = load_backup_dir()

    if args.command == "export":
        path = db_transfer.export_path(args.output, backup_dir)
        count = db_transfer.export_json(
            db_file, path, tag=args.tag, include_deleted=args.include_deleted
        )
        tags = db_transfer.count_tags(db_file, tag=args.tag)
        print(f"✓ Exported {count} commands from {tags} tags to {path}")
        if args.tag:
            print(f"  Filtered by tag: {args.tag}")
        return 0

    if args.command == "import":
        path = db_transfer.import_path(args.input, backup_dir)
        if not Path(path).exists():
            print(f"✗ Error: File not found: {args.input}", file=sys.stderr)
            return 1
        result = db_transfer.import_json(
            db_file,
            path,
            mode=args.mode,
            preserve_tid=args.keep_tids,
            skip_existing=args.mode == "merge",
        )
        _print_result(result)
        return 0

    if args.command == "export-csv":
        path = db_transfer.export_path(args.output, backup_dir)
        count = db_transfer.export_commands_csv(
            db_file, path, tag=args.tag, include_deleted=args.include_deleted
        )
        print(f"✓ Exported {count} commands to {path}")
        if args.tag:
            print(f"  Filtered by tag: {args.tag}")
        print(f"  Edit the file and import with: python backup_db.py import-csv {Path(path).name}")
        return 0

    if args.command == "import-csv":
        path = db_transfer.import_path(args.input, backup_dir)
        if not Path(path).exists():
            print(f"✗ Error: File not found: {args.input}", file=sys.stderr)
            return 1
        result = db_transfer.import_commands_csv(db_file, path, mode=args.mode)
        _print_result(result)
        return 0

    if args.command == "export-tags-csv":
        path = db_transfer.export_path(args.output, backup_dir)
        count = db_transfer.export_tags_csv(db_file, path)
        print(f"✓ Exported {count} tag comments to {path}")
        print(f"  Edit the file and import with: python backup_db.py import-tags-csv {Path(path).name}")
        return 0

    if args.command == "import-tags-csv":
        path = db_transfer.import_path(args.input, backup_dir)
        if not Path(path).exists():
            print(f"✗ Error: File not found: {args.input}", file=sys.stderr)
            return 1
        result = db_transfer.import_tags_csv(db_file, path)
        print(f"\n✓ Import complete: {result.updated} tag comment(s)")
        return 0

    if args.command == "list":
        rows = db_transfer.library_overview(db_file)
        print(f"\nDatabase: {db_file}")
        print("-" * 60)
        total = 0
        for tag, count, comment in rows:
            line = f"  [{tag}] {count} commands"
            if args.show_comments and comment:
                line += f" - {comment}"
            print(line)
            total += count
        print("-" * 60)
        print(f"  Total: {total} commands\n")
        return 0

    if args.command == "backup":
        return _backup(db_file, backup_dir)

    if args.command == "restore":
        path = db_transfer.import_path(args.input, backup_dir)
        if not Path(path).exists():
            print(f"✗ Error: File not found: {args.input}", file=sys.stderr)
            return 1
        # Перед возвратом — снимок текущей базы: операцию есть чем откатить.
        snapshot = seed_lib.backup_sqlite(db_file, "pre-restore", quiet=True)
        if snapshot is not None:
            print(f"Snapshot before restore: {snapshot}")
        try:
            result = _import_file(
                db_file, path, mode=args.mode, skip_existing=args.mode == "merge"
            )
        except ValueError as exc:
            print(f"✗ Error: {exc}", file=sys.stderr)
            return 1
        _print_result(result)
        return 0

    parser.print_help()
    return 1


def _backup(db_file: str, backup_dir: str) -> int:
    """Снимок SQLite (точный слепок) + JSON и CSV (переносимые копии)."""
    if not Path(db_file).exists():
        print(f"✗ Error: Database not found: {db_file}", file=sys.stderr)
        return 1
    snapshot = seed_lib.backup_sqlite(db_file, "manual", quiet=True)
    if snapshot is None:
        print("✗ Nothing to backup (empty database)", file=sys.stderr)
        return 1
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = db_transfer.export_path(f"backup_{stamp}.json", backup_dir)
    commands_csv = db_transfer.export_path(f"commands_{stamp}.csv", backup_dir)
    tags_csv = db_transfer.export_path(f"tags_{stamp}.csv", backup_dir)
    commands = db_transfer.export_json(db_file, json_path)
    db_transfer.export_commands_csv(db_file, commands_csv)
    db_transfer.export_tags_csv(db_file, tags_csv)
    print("✓ Backup complete:")
    print(f"  SQLite snapshot: {snapshot}")
    print(f"  JSON:            {json_path} ({commands} commands)")
    print(f"  CSV commands:    {commands_csv}")
    print(f"  CSV tags:        {tags_csv}")
    print("\nRestore: python3 backup_db.py restore <file>   (или скопировать .db поверх базы)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
