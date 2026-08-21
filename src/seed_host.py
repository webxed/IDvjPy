#!/usr/bin/env python3
"""
Seed host handbook: tar/gz/zip archives (see SEED_HOST_COMMANDS.md).

Playbooks are inspect-only (list archive, no extract to /).
Disk tools (df/du/lsblk/smartctl/…) live in seed_disk.py.

Run: python3 src/seed_host.py --seed
"""
import sys

from seed_lib import run_seed as _run_seed
from seed_lib import seed_cli

SEED_TAGS = {
    "avars": (
        "переменные архивов",
        [
            (
                "echo src=$SRC dest=$DEST archive=$ARCHIVE pattern=$PATTERN",
                "проверка $SRC/$ARCHIVE/$PATTERN",
            ),
        ],
    ),
    "tar": (
        "tar: список и упаковка",
        [
            ("tar -tf $ARCHIVE", "список файлов в архиве"),
            ("tar -tzf $ARCHIVE", "список .tar.gz"),
            ("tar -tvf $ARCHIVE | head -n 50", "список с правами, первые 50"),
            ("tar -czvf $DEST $SRC", "упаковать $SRC → $DEST (.tar.gz)"),
            ("tar -czvf $DEST --exclude='.git' $SRC", "упаковать без .git"),
            ("tar -xzvf $ARCHIVE", "распаковать в cwd"),
            ("tar -xzvf $ARCHIVE -C $DEST", "распаковать в $DEST"),
            ("tar -df $ARCHIVE $SRC", "сравнить архив с $SRC"),
        ],
    ),
    "gz": (
        "gzip / gunzip / zcat",
        [
            ("gzip -l $ARCHIVE", "размер и степень сжатия"),
            ("gzip -dk $ARCHIVE", "распаковать, оставить .gz"),
            ("gunzip -c $ARCHIVE | head -n 20", "первые строки без записи на диск"),
            ("zcat $ARCHIVE | head -n 20", "то же через zcat"),
            ("gzip -k $SRC", "сжать, оставить исходник"),
            ("zgrep -n $PATTERN $ARCHIVE", "grep внутри .gz ($PATTERN)"),
        ],
    ),
    "zip": (
        "zip / unzip",
        [
            ("zipinfo $ARCHIVE", "список и права в .zip"),
            ("unzip -l $ARCHIVE", "список файлов"),
            ("unzip -v $ARCHIVE", "список подробно"),
            ("zip -r $DEST $SRC", "упаковать $SRC → $DEST"),
            ("unzip $ARCHIVE", "распаковать в cwd"),
            ("unzip $ARCHIVE -d $DEST", "распаковать в $DEST"),
            ("zipgrep $PATTERN $ARCHIVE", "grep внутри .zip"),
        ],
    ),
    "tstat": (
        "осмотр архива",
        [
            (
                "!tar[2] ; echo '--- gzip -l ---' ; !gz[1]",
                "tar -tzf + gzip -l (без распаковки)",
            ),
        ],
    ),
    "zstat": (
        "осмотр zip",
        [
            (
                "!zip[1] ; echo '--- unzip -l ---' ; !zip[2]",
                "zipinfo + unzip -l (без распаковки)",
            ),
        ],
    ),
}


def run_seed(db_file: str) -> int:
    return _run_seed(db_file, SEED_TAGS)


def main() -> None:
    seed_cli(
        description="Seed IDvjPy_term DB with tar/gzip/zip handbook (SEED_HOST_COMMANDS.md)",
        seed_help="Replace tar/gz/zip/tstat/zstat (does not touch file/proc/smart/df)",
        seed_tags=SEED_TAGS,
        argv=sys.argv,
    )


if __name__ == "__main__":
    main()
