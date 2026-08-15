#!/usr/bin/env python3
"""
Database import/export script for IDvjPy_term v2.

Supports exporting tagged command history to JSON and CSV, importing from JSON and CSV.
Handles tag-local IDs (tid) and comments for tags and commands.
"""
import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path
from datetime import datetime
import yaml


def load_settings():
    """Load database filename from settings.yml."""
    settings_path = Path(__file__).parent / "settings.yml"
    if settings_path.exists():
        with open(settings_path, 'r') as f:
            settings = yaml.safe_load(f)
            return settings.get('database_tags_file', 'mytags.db')
    return 'mytags.db'


def load_backup_dir():
    """Load backup directory from settings.yml."""
    settings_path = Path(__file__).parent / "settings.yml"
    if settings_path.exists():
        with open(settings_path, 'r') as f:
            settings = yaml.safe_load(f)
            backup_dir = settings.get('backup_dir', 'backups')
            # Ensure backup directory exists
            backup_path = Path(__file__).parent / backup_dir
            backup_path.mkdir(parents=True, exist_ok=True)
            return backup_dir
    return 'backups'


def resolve_backup_path(filename: str, backup_dir: str = None) -> Path:
    """
    Resolve backup file path - use backup_dir if path is relative.

    Args:
        filename: Input filename (can be relative or absolute)
        backup_dir: Backup directory from settings

    Returns:
        Resolved Path object
    """
    path = Path(filename)

    # If absolute path or explicitly starts with ./, keep as is
    if path.is_absolute() or str(path).startswith('./'):
        return path

    # Use backup_dir for relative paths
    if backup_dir is None:
        backup_dir = load_backup_dir()

    backup_path = Path(__file__).parent / backup_dir
    backup_path.mkdir(parents=True, exist_ok=True)

    return backup_path / filename


def get_db_connection(db_file: str):
    """Establishes a connection to the database."""
    conn = sqlite3.connect(db_file, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def export_db(db_file: str, output_file: str, tag: str = None, include_deleted: bool = False, use_backup_dir: bool = True):
    """
    Export commands from database to JSON file.

    Args:
        db_file: Path to SQLite database
        output_file: Path to output JSON file
        tag: Optional tag filter (export only this tag)
        include_deleted: Include soft-deleted commands
    """
    conn = get_db_connection(db_file)

    # Build query based on parameters
    if tag:
        cursor = conn.execute(
            """SELECT id, tag, tid, command, timestamp, deleted, comment
               FROM commands WHERE tag = ? ORDER BY tid ASC""",
            (tag,)
        )
    else:
        cursor = conn.execute(
            """SELECT id, tag, tid, command, timestamp, deleted, comment
               FROM commands ORDER BY tag ASC, tid ASC"""
        )

    commands = []
    for row in cursor.fetchall():
        if not include_deleted and row['deleted']:
            continue
        commands.append({
            'id': row['id'],
            'tag': row['tag'],
            'tid': row['tid'],
            'command': row['command'],
            'timestamp': row['timestamp'],
            'deleted': bool(row['deleted']),
            'comment': row['comment'] or ''
        })

    # Export tag comments
    if tag:
        tag_cursor = conn.execute(
            "SELECT tag, comment FROM tags WHERE tag = ?", (tag,)
        )
    else:
        tag_cursor = conn.execute("SELECT tag, comment FROM tags ORDER BY tag ASC")

    tag_comments = {}
    for row in tag_cursor.fetchall():
        tag_comments[row['tag']] = row['comment'] or ''

    conn.close()

    # Prepare export data
    export_data = {
        'version': '2.0',
        'schema_version': 'v2',
        'export_date': datetime.now().isoformat(),
        'source_db': db_file,
        'tag_filter': tag,
        'total_commands': len(commands),
        'total_tags': len(tag_comments),
        'tag_comments': tag_comments,
        'commands': commands
    }

    # Write to JSON file
    if use_backup_dir:
        output_path = resolve_backup_path(output_file)
    else:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)

    print(f"✓ Exported {len(commands)} commands from {len(tag_comments)} tags to {output_path}")
    if tag:
        print(f"  Filtered by tag: {tag}")


def import_db(db_file: str, input_file: str, mode: str = 'merge',
              skip_existing: bool = True, preserve_tid: bool = True):
    """
    Import commands from JSON file to database.

    Args:
        db_file: Path to SQLite database
        input_file: Path to input JSON file
        mode: Import mode - 'merge' (add new) or 'replace' (clear and import)
        skip_existing: Skip commands that already exist (by tag+tid)
        preserve_tid: Preserve original tid values (requires finding next available tid on conflict)
    """
    # Read JSON file
    input_path = Path(input_file)
    if not input_path.exists():
        # Try to find in backup directory
        backup_path = resolve_backup_path(input_file)
        if backup_path.exists():
            input_path = backup_path
        else:
            print(f"✗ Error: File not found: {input_file}", file=sys.stderr)
            sys.exit(1)

    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if 'commands' not in data:
        print("✗ Error: Invalid JSON format - missing 'commands' key", file=sys.stderr)
        sys.exit(1)

    commands = data['commands']
    tag_comments = data.get('tag_comments', {})
    print(f"Found {len(commands)} commands and {len(tag_comments)} tag comments in {input_file}")

    # Initialize database
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

    # Add comment column if needed
    try:
        conn.execute("ALTER TABLE commands ADD COLUMN comment TEXT DEFAULT ''")
    except Exception:
        pass

    # Tags table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            tag TEXT PRIMARY KEY,
            comment TEXT
        );
    """)

    # Create index
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_tag_tid
        ON commands (tag, tid) WHERE deleted = 0
    """)

    imported = 0
    skipped = 0
    errors = 0
    tid_conflicts = 0

    if mode == 'replace':
        # Clear existing commands and tags
        conn.execute("DELETE FROM commands")
        conn.execute("DELETE FROM tags")
        print("✓ Cleared existing database")

    # Import tag comments first
    for tag, comment in tag_comments.items():
        conn.execute(
            "INSERT OR REPLACE INTO tags (tag, comment) VALUES (?, ?)",
            (tag, comment)
        )

    # Import commands
    for cmd_data in commands:
        try:
            cmd_id = cmd_data.get('id')
            tag = cmd_data.get('tag')
            tid = cmd_data.get('tid')
            command = cmd_data.get('command')
            timestamp = cmd_data.get('timestamp', datetime.now().isoformat())
            deleted = 1 if cmd_data.get('deleted', False) else 0
            comment = cmd_data.get('comment', '')

            if not tag or not command:
                skipped += 1
                continue

            # Check for existing command if skip_existing is enabled
            if skip_existing and mode == 'merge':
                cursor = conn.execute(
                    "SELECT id FROM commands WHERE tag = ? AND tid = ? AND deleted = 0",
                    (tag, tid)
                )
                if cursor.fetchone():
                    skipped += 1
                    continue

            # Handle tid conflicts if preserve_tid is False
            if not preserve_tid and mode == 'merge':
                # Find next available tid for this tag
                cursor = conn.execute(
                    "SELECT COALESCE(MAX(tid), 0) + 1 FROM commands WHERE tag = ?",
                    (tag,)
                )
                new_tid = cursor.fetchone()[0]
                if new_tid != tid:
                    tid = new_tid
                    tid_conflicts += 1

            # Insert command with original ID to preserve global IDs
            try:
                conn.execute(
                    """INSERT INTO commands (id, tag, tid, command, timestamp, deleted, comment)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (cmd_id, tag, tid, command, timestamp, deleted, comment)
                )
                imported += 1
            except sqlite3.IntegrityError:
                # UNIQUE constraint failed - id or tag+tid already exists
                # If id conflict exists, try updating instead
                if cmd_id:
                    cursor = conn.execute(
                        "SELECT id FROM commands WHERE id = ?",
                        (cmd_id,)
                    )
                    if cursor.fetchone():
                        # Update existing record by id
                        conn.execute(
                            """UPDATE commands SET tag = ?, tid = ?, command = ?, timestamp = ?, deleted = ?, comment = ?
                               WHERE id = ?""",
                            (tag, tid, command, timestamp, deleted, comment, cmd_id)
                        )
                        updated += 1
                    else:
                        if preserve_tid and mode == 'merge':
                            skipped += 1
                        else:
                            errors += 1
                else:
                    if preserve_tid and mode == 'merge':
                        skipped += 1
                    else:
                        errors += 1

        except Exception as e:
            print(f"✗ Error importing command: {e}", file=sys.stderr)
            errors += 1

    conn.commit()
    conn.close()

    print(f"\n✓ Import complete:")
    print(f"  Imported: {imported}")
    print(f"  Skipped:  {skipped}")
    if tid_conflicts > 0:
        print(f"  TID reassigned: {tid_conflicts}")
    if errors > 0:
        print(f"  Errors:   {errors}")


def list_db(db_file: str, show_comments: bool = False):
    """List all tags and command counts in the database."""
    conn = get_db_connection(db_file)

    # Get all tags with counts and comments
    cursor = conn.execute("""
        SELECT c.tag, COUNT(*) as count, t.comment
        FROM commands c
        LEFT JOIN tags t ON c.tag = t.tag
        WHERE c.deleted = 0
        GROUP BY c.tag
        ORDER BY c.tag ASC
    """)

    print(f"\nDatabase: {db_file}")
    print("-" * 60)

    total = 0
    for row in cursor.fetchall():
        tag_info = f"  [{row['tag']}] {row['count']} commands"
        if show_comments and row['comment']:
            tag_info += f" - {row['comment']}"
        print(tag_info)
        total += row['count']

    print("-" * 60)
    print(f"  Total: {total} commands\n")

    conn.close()


def export_tag(db_file: str, tag: str, output_file: str):
    """
    Export a single tag with all its commands and metadata to JSON.

    Args:
        db_file: Path to SQLite database
        tag: Tag name to export
        output_file: Path to output JSON file
    """
    export_db(db_file, output_file, tag=tag, include_deleted=False)
    print(f"✓ Exported tag '{tag}' to {output_file}")


def import_tag(db_file: str, input_file: str, mode: str = 'merge'):
    """
    Import a single tag from JSON file.

    Args:
        db_file: Path to SQLite database
        input_file: Path to input JSON file
        mode: Import mode - 'merge' or 'replace'
    """
    import_db(db_file, input_file, mode=mode, skip_existing=(mode == 'merge'), preserve_tid=True)


def export_csv(db_file: str, output_file: str, tag: str = None, include_deleted: bool = False, use_backup_dir: bool = True):
    """
    Export commands from database to CSV file for editing in spreadsheet software.

    CSV format: tag,tid,command,comment

    Args:
        db_file: Path to SQLite database
        output_file: Path to output CSV file
        tag: Optional tag filter (export only this tag)
        include_deleted: Include soft-deleted commands
    """
    conn = get_db_connection(db_file)

    # Build query based on parameters
    if tag:
        cursor = conn.execute(
            """SELECT tag, tid, command, comment, deleted
               FROM commands WHERE tag = ? ORDER BY tid ASC""",
            (tag,)
        )
    else:
        cursor = conn.execute(
            """SELECT tag, tid, command, comment, deleted
               FROM commands ORDER BY tag ASC, tid ASC"""
        )

    if use_backup_dir:
        output_path = resolve_backup_path(output_file)
    else:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter=';', quoting=csv.QUOTE_MINIMAL)
        # Write header
        writer.writerow(['tag', 'tid', 'command', 'comment'])

        count = 0
        for row in cursor.fetchall():
            if not include_deleted and row['deleted']:
                continue
            writer.writerow([
                row['tag'],
                row['tid'],
                row['command'],
                row['comment'] or ''
            ])
            count += 1

    conn.close()

    print(f"✓ Exported {count} commands to {output_path}")
    if tag:
        print(f"  Filtered by tag: {tag}")
    print(f"  Edit the file and import with: python backup_db.py import-csv {output_path.name}")


def import_csv(db_file: str, input_file: str, mode: str = 'merge'):
    """
    Import commands from CSV file to database.

    CSV format: tag,tid,command,comment

    Args:
        db_file: Path to SQLite database
        input_file: Path to input CSV file
        mode: Import mode - 'merge' (update existing) or 'replace' (clear and import)
    """
    input_path = Path(input_file)
    if not input_path.exists():
        # Try to find in backup directory
        backup_path = resolve_backup_path(input_file)
        if backup_path.exists():
            input_path = backup_path
        else:
            print(f"✗ Error: File not found: {input_file}", file=sys.stderr)
            sys.exit(1)

    # Initialize database
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

    # Add comment column if needed
    try:
        conn.execute("ALTER TABLE commands ADD COLUMN comment TEXT DEFAULT ''")
    except Exception:
        pass

    if mode == 'replace':
        # Clear existing commands
        conn.execute("DELETE FROM commands")
        print("✓ Cleared existing database")

    imported = 0
    updated = 0
    errors = 0

    with open(input_path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter=';')
        header = next(reader, None)  # Skip header

        if header and 'tag' not in str(header).lower():
            print("✗ Warning: CSV header may be missing 'tag' column", file=sys.stderr)

        for row_num, row in enumerate(reader, start=2):  # Start at 2 (after header)
            try:
                if len(row) < 3:
                    print(f"✗ Warning: Row {row_num} has insufficient columns, skipping", file=sys.stderr)
                    errors += 1
                    continue

                tag = row[0].strip()
                tid_str = row[1].strip()
                command = row[2].strip()
                comment = row[3].strip() if len(row) > 3 else ''

                if not tag or not command:
                    print(f"✗ Warning: Row {row_num} has empty tag or command, skipping", file=sys.stderr)
                    errors += 1
                    continue

                try:
                    tid = int(tid_str)
                except ValueError:
                    print(f"✗ Warning: Row {row_num} has invalid tid '{tid_str}', skipping", file=sys.stderr)
                    errors += 1
                    continue

                # Check if command exists
                cursor = conn.execute(
                    "SELECT id, command, comment FROM commands WHERE tag = ? AND tid = ?",
                    (tag, tid)
                )
                existing = cursor.fetchone()

                if existing:
                    # Update existing command
                    conn.execute(
                        "UPDATE commands SET command = ?, comment = ? WHERE tag = ? AND tid = ?",
                        (command, comment, tag, tid)
                    )
                    updated += 1
                else:
                    # Insert new command
                    conn.execute(
                        """INSERT INTO commands (tag, tid, command, timestamp, deleted, comment)
                           VALUES (?, ?, ?, ?, 0, ?)""",
                        (tag, tid, command, datetime.now(), comment)
                    )
                    imported += 1

            except Exception as e:
                print(f"✗ Error importing row {row_num}: {e}", file=sys.stderr)
                errors += 1

    conn.commit()
    conn.close()

    print(f"\n✓ Import complete:")
    print(f"  Imported: {imported}")
    print(f"  Updated:  {updated}")
    if errors > 0:
        print(f"  Errors:   {errors}")


def export_tags_csv(db_file: str, output_file: str, use_backup_dir: bool = True):
    """
    Export tag comments to CSV file.

    CSV format: tag,comment

    Args:
        db_file: Path to SQLite database
        output_file: Path to output CSV file
    """
    conn = get_db_connection(db_file)

    cursor = conn.execute("SELECT tag, comment FROM tags ORDER BY tag ASC")

    if use_backup_dir:
        output_path = resolve_backup_path(output_file)
    else:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter=';', quoting=csv.QUOTE_MINIMAL)
        # Write header
        writer.writerow(['tag', 'comment'])

        count = 0
        for row in cursor.fetchall():
            writer.writerow([
                row['tag'],
                row['comment'] or ''
            ])
            count += 1

    conn.close()

    print(f"✓ Exported {count} tag comments to {output_path}")
    print(f"  Edit the file and import with: python backup_db.py import-tags-csv {output_path.name}")


def import_tags_csv(db_file: str, input_file: str):
    """
    Import tag comments from CSV file to database.

    CSV format: tag,comment

    Args:
        db_file: Path to SQLite database
        input_file: Path to input CSV file
    """
    input_path = Path(input_file)
    if not input_path.exists():
        # Try to find in backup directory
        backup_path = resolve_backup_path(input_file)
        if backup_path.exists():
            input_path = backup_path
        else:
            print(f"✗ Error: File not found: {input_file}", file=sys.stderr)
            sys.exit(1)

    # Initialize database
    conn = get_db_connection(db_file)

    # Tags table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            tag TEXT PRIMARY KEY,
            comment TEXT
        );
    """)

    imported = 0
    updated = 0
    errors = 0

    with open(input_path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter=';')
        header = next(reader, None)  # Skip header

        for row_num, row in enumerate(reader, start=2):  # Start at 2 (after header)
            try:
                if len(row) < 1:
                    continue

                tag = row[0].strip()
                comment = row[1].strip() if len(row) > 1 else ''

                if not tag:
                    continue

                # Check if tag exists
                cursor = conn.execute(
                    "SELECT tag FROM tags WHERE tag = ?",
                    (tag,)
                )
                existing = cursor.fetchone()

                if existing:
                    updated += 1
                else:
                    imported += 1

                # Insert or replace
                conn.execute(
                    "INSERT OR REPLACE INTO tags (tag, comment) VALUES (?, ?)",
                    (tag, comment)
                )

            except Exception as e:
                print(f"✗ Error importing row {row_num}: {e}", file=sys.stderr)
                errors += 1

    conn.commit()
    conn.close()

    print(f"\n✓ Import complete:")
    print(f"  Imported: {imported}")
    print(f"  Updated:  {updated}")
    if errors > 0:
        print(f"  Errors:   {errors}")


def main():
    parser = argparse.ArgumentParser(
        description="Import/export tagged command history for IDvjPy_term v2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export all commands to JSON
  python backup_db.py export backup.json

  # Export to CSV for editing in spreadsheet
  python backup_db.py export-csv commands.csv

  # Export only specific tag to CSV
  python backup_db.py export-csv commands.csv --tag python

  # Import from CSV (merge - update existing, add new)
  python backup_db.py import-csv commands.csv

  # Import from CSV (replace - clear database first)
  python backup_db.py import-csv commands.csv --mode replace

  # Export tag comments to CSV
  python backup_db.py export-tags-csv tags.csv

  # Import tag comments from CSV
  python backup_db.py import-tags-csv tags.csv

  # List all tags in database
  python backup_db.py list

  # List tags with comments
  python backup_db.py list --show-comments
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Export JSON command
    export_parser = subparsers.add_parser('export', help='Export database to JSON')
    export_parser.add_argument('output', help='Output JSON file path')
    export_parser.add_argument('--tag', help='Export only specific tag')
    export_parser.add_argument('--include-deleted', action='store_true',
                               help='Include soft-deleted commands')
    export_parser.add_argument('--db', help='Database file (default: from settings.yml)')

    # Import JSON command
    import_parser = subparsers.add_parser('import', help='Import JSON to database')
    import_parser.add_argument('input', help='Input JSON file path')
    import_parser.add_argument('--mode', choices=['merge', 'replace'], default='merge',
                               help='Import mode: merge (default) or replace')
    import_parser.add_argument('--no-preserve-tid', action='store_true',
                               help='Auto-assign new TIDs on conflict (default: preserve original TIDs)')
    import_parser.add_argument('--db', help='Database file (default: from settings.yml)')

    # Export CSV command
    export_csv_parser = subparsers.add_parser('export-csv', help='Export commands to CSV for editing')
    export_csv_parser.add_argument('output', help='Output CSV file path')
    export_csv_parser.add_argument('--tag', help='Export only specific tag')
    export_csv_parser.add_argument('--include-deleted', action='store_true',
                                   help='Include soft-deleted commands')
    export_csv_parser.add_argument('--db', help='Database file (default: from settings.yml)')

    # Import CSV command
    import_csv_parser = subparsers.add_parser('import-csv', help='Import commands from CSV')
    import_csv_parser.add_argument('input', help='Input CSV file path')
    import_csv_parser.add_argument('--mode', choices=['merge', 'replace'], default='merge',
                                   help='Import mode: merge/update (default) or replace')
    import_csv_parser.add_argument('--db', help='Database file (default: from settings.yml)')

    # Export tags CSV command
    export_tags_csv_parser = subparsers.add_parser('export-tags-csv',
                                                   help='Export tag comments to CSV')
    export_tags_csv_parser.add_argument('output', help='Output CSV file path')
    export_tags_csv_parser.add_argument('--db', help='Database file (default: from settings.yml)')

    # Import tags CSV command
    import_tags_csv_parser = subparsers.add_parser('import-tags-csv',
                                                   help='Import tag comments from CSV')
    import_tags_csv_parser.add_argument('input', help='Input CSV file path')
    import_tags_csv_parser.add_argument('--db', help='Database file (default: from settings.yml)')

    # List command
    list_parser = subparsers.add_parser('list', help='List all tags in database')
    list_parser.add_argument('--show-comments', action='store_true',
                             help='Show tag comments')
    list_parser.add_argument('--db', help='Database file (default: from settings.yml)')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Get database file
    db_file = args.db if hasattr(args, 'db') and args.db else load_settings()

    if args.command == 'export':
        export_db(db_file, args.output, args.tag, args.include_deleted)
    elif args.command == 'import':
        import_db(db_file, args.input, args.mode, skip_existing=(args.mode == 'merge'),
                  preserve_tid=not args.no_preserve_tid)
    elif args.command == 'export-csv':
        export_csv(db_file, args.output, args.tag, args.include_deleted)
    elif args.command == 'import-csv':
        import_csv(db_file, args.input, args.mode)
    elif args.command == 'export-tags-csv':
        export_tags_csv(db_file, args.output)
    elif args.command == 'import-tags-csv':
        import_tags_csv(db_file, args.input)
    elif args.command == 'list':
        list_db(db_file, args.show_comments)


if __name__ == '__main__':
    main()
