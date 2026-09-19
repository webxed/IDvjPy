"""Shared helpers for handbook seed scripts (git, docker, helm, …)."""
from __future__ import annotations

import argparse
import os
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

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
DEFAULT_BACKUP_DIR = "backups"
# Комментарии сидов по языкам: `src/seed_text/<lang>/<handbook>.yml`.
SEED_TEXT_DIR = Path(__file__).resolve().parent / "seed_text"
DEFAULT_SEED_LANG = "en"

# One SQLite snapshot per database path per process (seed_ops runs many modules).
_BACKED_UP: dict[str, Path | None] = {}


def reset_seed_backup_cache() -> None:
    """Tests: allow a second snapshot of the same path in one process."""
    _BACKED_UP.clear()


def _db_key(db_file: str) -> str:
    src = Path(db_file)
    try:
        return str(src.resolve())
    except OSError:
        return str(src)


def get_db_file() -> str:
    if not os.path.exists(FILE_SETTINGS):
        return DEFAULT_DB
    try:
        with open(FILE_SETTINGS, encoding=ENCODING) as f:
            settings = yaml.safe_load(f)
        if settings:
            return settings.get("database_tags_file", DEFAULT_DB)
    except Exception:
        pass
    return DEFAULT_DB


def _backup_dir_for(db_file: str) -> Path:
    name = DEFAULT_BACKUP_DIR
    settings = Path(FILE_SETTINGS)
    if settings.is_file():
        try:
            with open(settings, encoding=ENCODING) as fh:
                data = yaml.safe_load(fh) or {}
            raw = data.get("backup_dir", DEFAULT_BACKUP_DIR)
            if raw:
                name = str(raw)
        except Exception:
            pass
    dest = Path(name)
    if not dest.is_absolute():
        dest = Path(db_file).resolve().parent / dest
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def _safe_backup_label(label: str, default: str = "seed") -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", label or default).strip("._")
    return safe or default


def _unique_backup_dest(directory: Path, stem: str, suffix: str) -> Path:
    dest = directory / f"{stem}{suffix}"
    n = 1
    while dest.exists():
        n += 1
        dest = directory / f"{stem}-{n}{suffix}"
    return dest


def _copy_sqlite(src: Path, dest: Path) -> None:
    src_conn = sqlite3.connect(str(src), timeout=10)
    try:
        dst_conn = sqlite3.connect(str(dest), timeout=10)
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
    finally:
        src_conn.close()


def backup_sqlite(
    db_file: str,
    label: str = "manual",
    *,
    skip_empty: bool = True,
    once: bool = False,
    remember_empty: bool = False,
    quiet: bool = False,
    pre: bool = False,
) -> Path | None:
    """Copy the live DB into ``backup_dir``.

    ``once`` (seed): the same file is snapshotted at most once per process.
    ``pre``: filename ``<stem>-pre-<label>-<stamp>.db`` (seed); else ``<stem>-<label>-<stamp>.db``.
    """
    src = Path(db_file)
    if not src.is_file():
        return None
    key = _db_key(str(src))
    if once and key in _BACKED_UP:
        return _BACKED_UP[key]
    try:
        if skip_empty and not database.has_live_commands(str(src)):
            if once and remember_empty:
                _BACKED_UP[key] = None
            return None
    except Exception:
        return None
    safe = _safe_backup_label(label, "manual" if not pre else "seed")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    mid = f"pre-{safe}" if pre else safe
    dest = _unique_backup_dest(
        _backup_dir_for(str(src)),
        f"{src.stem}-{mid}-{stamp}",
        src.suffix or ".db",
    )
    try:
        _copy_sqlite(src, dest)
    except Exception as exc:
        dest.unlink(missing_ok=True)
        if not quiet:
            print(f"Backup failed: {exc}", file=sys.stderr)
        return None
    if once:
        _BACKED_UP[key] = dest
    if not quiet:
        print(f"Backup: {dest}")
    return dest


def backup_sqlite_before_seed(
    db_file: str,
    label: str = "seed",
    *,
    remember_empty: bool = False,
) -> Path | None:
    """Copy the live DB into ``backup_dir`` before a replace.

    Skips an empty database. The same file is snapshotted at most once per process
    so ``seed_ops.py`` does not write twenty copies.
    """
    return backup_sqlite(
        db_file,
        label,
        skip_empty=True,
        once=True,
        remember_empty=remember_empty,
        pre=True,
    )


def hard_delete_commands_by_tag(db_file: str, tag: str) -> None:
    conn = database.get_db_connection(db_file)
    conn.execute("DELETE FROM commands WHERE tag = ?", (tag,))
    conn.execute("DELETE FROM tags WHERE tag = ?", (tag,))
    conn.commit()
    conn.close()


def resolve_seed_language() -> str:
    """Язык комментариев сидов: settings.yml → $IDVJPY_LANG → $LANG(auto) → en.

    Отдельного `--lang` у seed-скриптов нет: язык — это настройка приложения
    (`language`), поэтому засеянная библиотека говорит на том же языке, что и UI.
    """
    settings_lang: object = None
    if os.path.exists(FILE_SETTINGS):
        try:
            with open(FILE_SETTINGS, encoding=ENCODING) as fh:
                data = yaml.safe_load(fh) or {}
            if isinstance(data, dict):
                settings_lang = data.get("language")
        except Exception:
            settings_lang = None
    try:
        from i18n import resolve_language
    except ImportError:  # запуск без src/ в sys.path — остаёмся на en
        return DEFAULT_SEED_LANG
    return resolve_language(None, settings_lang)


def _translated(value: object, fallback: str) -> str:
    text = str(value).strip() if value is not None else ""
    return text or fallback


_TEXT_CACHE: dict[str, dict[str, dict]] = {}


def load_seed_text(lang: str | None = None) -> dict[str, dict]:
    """Комментарии сидов для языка: слияние `seed_text/<lang>/*.yml` по тегам.

    Формат файла::

        tags:
          git:
            comment: "git: status, diff, branches"
            commands:
              0: "full status"

    Тег встречается ровно в одном файле (сторожит `tests/test_seed_i18n.py`),
    поэтому label/имя хэндбука для поиска не нужно. Результат кешируется на
    процесс — `apply_comments` ходит в индекс на каждую строку БД.
    """
    code = lang or resolve_seed_language()
    cached = _TEXT_CACHE.get(code)
    if cached is not None:
        return cached
    directory = SEED_TEXT_DIR / code
    index: dict[str, dict] = {}
    if directory.is_dir():
        for path in sorted(directory.glob("*.yml")):
            try:
                data = yaml.safe_load(path.read_text(encoding=ENCODING))
            except (OSError, UnicodeDecodeError, yaml.YAMLError):
                continue
            tags = data.get("tags") if isinstance(data, dict) else None
            if not isinstance(tags, dict):
                continue
            for tag, block in tags.items():
                if isinstance(block, dict):
                    index[str(tag)] = block
    _TEXT_CACHE[code] = index
    return index


def reset_seed_text_cache() -> None:
    """Тесты: перечитать `seed_text/*` после правки файлов."""
    _TEXT_CACHE.clear()


def localized_tag_comment(tag: str, fallback: str, lang: str | None = None) -> str:
    """Подпись тега на текущем языке; нет перевода — fallback (базовый текст)."""
    block = load_seed_text(lang).get(str(tag)) or {}
    return _translated(block.get("comment"), fallback)


def localized_comment(
    tag: str, position: int, fallback: str, lang: str | None = None
) -> str:
    """Комментарий команды по позиции (tid - 1) на текущем языке."""
    block = load_seed_text(lang).get(str(tag)) or {}
    value = (block.get("commands") or {}).get(position)
    return _translated(value, fallback)


def localized_tags(seed_tags: dict, lang: str | None = None) -> dict:
    """Тот же набор тегов, но комментарии — из `seed_text/<lang>/*.yml`.

    Ключа нет — остаётся встроенный комментарий (это базовый текст хэндбука).
    """
    index = load_seed_text(lang)
    if not index:
        return seed_tags
    out: dict = {}
    for tag, (tag_comment, commands) in seed_tags.items():
        block = index.get(str(tag)) or {}
        command_map = block.get("commands") or {}
        new_commands = [
            (cmd, _translated(command_map.get(index_), cmd_comment))
            for index_, (cmd, cmd_comment) in enumerate(commands)
        ]
        out[tag] = (_translated(block.get("comment"), tag_comment), new_commands)
    return out

def run_seed(db_file: str, seed_tags: dict, *, label: str = "seed") -> int:
    """Replace tags in seed_tags; return number of commands inserted."""
    backup_sqlite_before_seed(db_file, label)
    database.init_db(db_file)
    n = 0
    for tag, (tag_comment, commands) in localized_tags(seed_tags).items():
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
    script = Path(argv[0]).stem
    label = script[5:] if script.startswith("seed_") else script
    n = run_seed(db_file, seed_tags, label=label or "seed")
    print(f"Seeded {len(seed_tags)} tags ({n} commands) into {db_file}")
