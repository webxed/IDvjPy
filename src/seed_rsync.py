#!/usr/bin/env python3
"""
Seed rsync handbook tags (see SEED_RSYNC_COMMANDS.md).

Playbooks are dry-run / list-only. --delete is not in playbooks.
Does not touch linux `net` (basic rsync -avz stays there).

Run: python3 src/seed_rsync.py --seed
"""
import sys

from seed_lib import run_seed as _run_seed
from seed_lib import seed_cli

SEED_TAGS = {
    "rvars": (
        "переменные rsync",
        [
            (
                "echo src=$SRC dest=$DEST remote=$REMOTE excl=$EXCL",
                "проверка $SRC/$DEST/$REMOTE/…",
            ),
        ],
    ),
    "rsync": (
        "rsync: dry-run, копия, ssh",
        [
            ("rsync --list-only \"$SRC\"", "список источника, без копирования"),
            ("rsync -avn \"$SRC\" \"$DEST\"", "dry-run archive"),
            ("rsync -avni \"$SRC\" \"$DEST\"", "dry-run + itemize-changes"),
            ("rsync -avzn --delete \"$SRC\" \"$DEST\"", "dry-run с --delete"),
            ("rsync -avzn --exclude=\"$EXCL\" \"$SRC\" \"$DEST\"", "dry-run с exclude"),
            ("rsync -avn \"$SRC\" \"$REMOTE:$DEST\"", "dry-run на $REMOTE"),
            ("rsync -avn \"$REMOTE:$SRC\" \"$DEST\"", "dry-run с $REMOTE"),
            ("rsync -av \"$SRC\" \"$DEST\"", "локальная копия"),
            ("rsync -avz \"$SRC\" \"$DEST\"", "копия со сжатием"),
            ("rsync -avzP \"$SRC\" \"$DEST\"", "progress + partial"),
            ("rsync -avz --exclude=\"$EXCL\" \"$SRC\" \"$DEST\"", "копия с exclude"),
            ("rsync -avz \"$SRC\" \"$REMOTE:$DEST\"", "на $REMOTE (ssh)"),
            ("rsync -avz \"$REMOTE:$SRC\" \"$DEST\"", "с $REMOTE (ssh)"),
            ("rsync -avz --bwlimit=5000 \"$SRC\" \"$DEST\"", "лимит ~5 MB/s"),
            (
                "rsync -avz --delete \"$SRC\" \"$DEST\"",
                "копия + удалить лишнее на dest (не в плейбуке)",
            ),
        ],
    ),
    "rchk": (
        "осмотр rsync (dry-run)",
        [
            (
                "!rsync[1] ; echo '--- dry-run ---' ; !rsync[3]",
                "list-only → itemize dry-run (без --delete)",
            ),
        ],
    ),
}


def run_seed(db_file: str) -> int:
    return _run_seed(db_file, SEED_TAGS)


def main() -> None:
    seed_cli(
        description="Seed IDvjPy_term DB with rsync handbook (SEED_RSYNC_COMMANDS.md)",
        seed_help="Replace rsync/rvars/rchk (does not touch net/file/proc)",
        seed_tags=SEED_TAGS,
        argv=sys.argv,
    )


if __name__ == "__main__":
    main()
