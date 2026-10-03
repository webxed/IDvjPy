#!/usr/bin/env python3
"""
Сид справочника sqlite3 для собственной библиотеки тегов приложения (см.
SEED_SQLITE_COMMANDS.md).

SQL отрабатывается на живой базе библиотеки: SELECT/WHERE/GROUP BY/ORDER BY,
LIKE, sqlite_master, EXPLAIN QUERY PLAN — и жёсткое удаление, которое не умеет `#tag-`
(строка показана приложением: мягкое удаление). Команды осмотра идут первыми; те, что
меняют базу, — это tid 11–13, и об этом сказано в комментарии. Tid 17 копирует файл
перед ручным SQL, tid 18 — учебная транзакция с откатом. Больше ничего не
затрагивается; приложение подставляет `$DBFILE` (открытый им файл библиотеки).

Run: python3 src/seed_sqlite.py --seed
"""
import sys

from seed_lib import run_seed as _run_seed
from seed_lib import seed_cli

SEED_TAGS = {
    "sqlvars": (
        "переменные sqlite / базы библиотеки",
        [
            (
                "echo db=$DBFILE tag=$TAG text=$TEXT",
                "проверка $DBFILE/$TAG/$TEXT",
            ),
        ],
    ),
    "sqlite": (
        "sqlite3: схема, теги, правка базы библиотеки (меняет базу: tid 11–13)",
        [
            (
                "command -v sqlite3 || echo 'sqlite3 not found: install sqlite3'",
                "есть ли CLI sqlite3",
            ),
            (
                'sqlite3 $DBFILE ".tables"',
                "таблицы базы",
            ),
            (
                'sqlite3 $DBFILE ".schema"',
                "схема базы: таблицы commands/tags и индекс",
            ),
            (
                "sqlite3 $DBFILE \"SELECT name, type FROM sqlite_master WHERE type IN "
                "('table','index') ORDER BY type, name;\"",
                "таблицы и индекс по sqlite_master",
            ),
            (
                "sqlite3 -header -column $DBFILE \"SELECT tag, COUNT(*) AS n FROM commands "
                "WHERE deleted = 0 GROUP BY tag ORDER BY n DESC;\"",
                "теги по числу команд (COUNT/GROUP BY)",
            ),
            (
                "sqlite3 -header -column $DBFILE \"SELECT tag, tid, command FROM commands "
                "WHERE deleted = 0 ORDER BY tag, tid;\"",
                "живые команды с tid",
            ),
            (
                "sqlite3 -header -column $DBFILE \"SELECT tag, comment FROM tags ORDER BY tag;\"",
                "комментарии тегов",
            ),
            (
                "sqlite3 -header -column $DBFILE \"SELECT tag, tid, command FROM commands "
                "WHERE deleted = 1 ORDER BY tag, tid;\"",
                "что лежит в мягком удалении",
            ),
            (
                "sqlite3 $DBFILE \"SELECT command FROM commands WHERE command LIKE "
                "'%$TEXT%' AND deleted = 0 LIMIT 20;\"",
                "поиск по тексту команды (LIKE)",
            ),
            (
                "sqlite3 $DBFILE \"EXPLAIN QUERY PLAN SELECT command FROM commands WHERE "
                "tag = '$TAG' AND deleted = 0;\"",
                "план запроса: индекс idx_tag_tid",
            ),
            (
                "sqlite3 $DBFILE \"DELETE FROM commands WHERE tag = '$TAG'; DELETE FROM tags "
                "WHERE tag = '$TAG';\"",
                "стереть тег из базы жёстко (меняет базу)",
            ),
            (
                "sqlite3 $DBFILE \"DELETE FROM commands WHERE deleted = 1; DELETE FROM tags "
                "WHERE tag NOT IN (SELECT DISTINCT tag FROM commands);\"",
                "вычистить мягко удалённое (меняет базу)",
            ),
            (
                'sqlite3 $DBFILE "VACUUM;"',
                "сжать файл после удаления (меняет файл)",
            ),
            (
                'sqlite3 $DBFILE "PRAGMA integrity_check;"',
                "целостность базы",
            ),
            (
                'sqlite3 $DBFILE ".dump" > mytags.sql',
                "SQL-дамп базы в mytags.sql (в текущий каталог)",
            ),
            (
                "sqlite3 $DBFILE",
                "интерактивный sqlite3 (лучше: > sqlite3 $DBFILE)",
            ),
            (
                'cp "$DBFILE" "mytags-before-manual-sqlite-$(date +%Y%m%d-%H%M%S).db"',
                "снимок файла базы перед ручным SQL (создаёт файл)",
            ),
            (
                "sqlite3 \"$DBFILE\" \"BEGIN; DELETE FROM commands WHERE tag = '$TAG'; "
                "SELECT changes(); ROLLBACK;\"",
                "учебный пример: транзакция с откатом (изменения не сохраняются)",
            ),
        ],
    ),
    "sqlstat": (
        "обзор базы библиотеки",
        [
            (
                "!sqlite[5] ; echo '--- deleted ---' ; !sqlite[8] ; "
                "echo '--- integrity ---' ; !sqlite[14]",
                "живые теги → мягко удалённое → целостность",
            ),
        ],
    ),
}


# Разметка канонических тегов (машинные токены, не переводятся; см. :tagmeta).
# `risk` — описательная пометка, а не защита: мутирующие шаги держит `run:manual`.
SEED_METADATA = {
    "sqlite": {
        "risk": "high",
        "utilities": ["sqlite3"],
        "os": ["linux", "macos", "windows"],
        "interactive": False,
        "topic": "database",
        "example": 'sqlite3 -header -column $DBFILE "SELECT tag, COUNT(*) FROM commands GROUP BY tag;"',
    },
}


def run_seed(db_file: str) -> int:
    return _run_seed(db_file, SEED_TAGS, metadata=SEED_METADATA)


def main() -> None:
    seed_cli(
        description="Seed IDvjPy_term DB with the sqlite3 handbook (SEED_SQLITE_COMMANDS.md)",
        seed_help="Replace sqlvars/sqlite/sqlstat (does not touch other tags)",
        seed_tags=SEED_TAGS,
        argv=sys.argv,
    )


if __name__ == "__main__":
    main()
