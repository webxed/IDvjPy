#!/usr/bin/env python3
"""
Seed find handbook tags (see SEED_FIND_COMMANDS.md).

Playbooks list/count only. -delete is not in playbooks.
Does not touch linux `file`.

Run: python3 src/seed_find.py --seed
"""
import sys

from seed_lib import run_seed as _run_seed
from seed_lib import seed_cli

SEED_TAGS = {
    "fvars": (
        "переменные find",
        [
            (
                "echo src=$SRC pattern=$PATTERN days=$DAYS size=$SIZE",
                "проверка $SRC/$PATTERN/…; pattern — glob (-name)",
            ),
        ],
    ),
    "find": (
        "find: файлы, glob, время, размер",
        [
            ("find \"$SRC\" -type f", "файлы"),
            ("find \"$SRC\" -type d", "каталоги"),
            ("find \"$SRC\" -name \"$PATTERN\"", "glob $PATTERN"),
            ("find \"$SRC\" -iname \"$PATTERN\"", "glob без регистра"),
            ("find \"$SRC\" -type f -name \"$PATTERN\"", "файлы по glob"),
            ("find \"$SRC\" -mtime -$DAYS", "изменены меньше чем $DAYS суток назад"),
            ("find \"$SRC\" -mtime +$DAYS", "старше $DAYS суток"),
            ("find \"$SRC\" -size +$SIZE", "больше $SIZE (например 100M)"),
            ("find \"$SRC\" -empty", "пустые файлы и каталоги"),
            ("find \"$SRC\" -type l", "симлинки"),
            ("find \"$SRC\" -name \"$PATTERN\" -ls", "как ls -dils"),
            (
                "find \"$SRC\" -type f -printf '%s %p\\n' | sort -n | tail -n 20",
                "20 самых больших файлов",
            ),
            ("find \"$SRC\" -type f -name \"$PATTERN\" | head -n 50", "первые 50 путей"),
            ("find \"$SRC\" -type f -name \"$PATTERN\" | wc -l", "сколько файлов"),
            (
                "find \"$SRC\" \\( -name .git -o -name .venv -o -name node_modules \\) "
                "-prune -o -type f -name \"$PATTERN\" -print",
                "поиск без .git/.venv/node_modules",
            ),
            (
                "find \"$SRC\" -type f -name \"$PATTERN\" -delete",
                "удалить найденные (не в плейбуке)",
            ),
        ],
    ),
    "fchk": (
        "поиск файлов по glob",
        [
            (
                "!find[5] ; echo '--- count ---' ; !find[14]",
                "type f -name → wc -l (без -delete)",
            ),
        ],
    ),
}


def run_seed(db_file: str) -> int:
    return _run_seed(db_file, SEED_TAGS)


def main() -> None:
    seed_cli(
        description="Seed IDvjPy_term DB with find handbook (SEED_FIND_COMMANDS.md)",
        seed_help="Replace find/fvars/fchk (does not touch file/proc)",
        seed_tags=SEED_TAGS,
        argv=sys.argv,
    )


if __name__ == "__main__":
    main()
