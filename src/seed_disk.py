#!/usr/bin/env python3
"""
Seed disk / filesystem handbook (see SEED_DISK_COMMANDS.md):

  df, du, mount, fdisk, lsblk, smartctl, ncdu.

Playbooks are inspect-only: no mkfs, fdisk wipe, wipefs -a, umount.
Does not touch linux `file` or host tar/gz.

Run: python3 src/seed_disk.py --seed
"""
import sys

from seed_lib import run_seed as _run_seed
from seed_lib import seed_cli

SEED_TAGS = {
    "dkvars": (
        "переменные дисков и точек монтирования",
        [
            (
                "echo disk=$DISK mnt=$MNT src=$SRC",
                "проверка $DISK/$MNT/$SRC",
            ),
        ],
    ),
    "df": (
        "df: место на файловых системах",
        [
            ("df -h", "человекочитаемо"),
            ("df -hT", "с типом FS"),
            ("df -i", "inode"),
            ("df -h $MNT", "точка $MNT"),
            (
                "df -h --output=source,fstype,size,used,avail,pcent,target",
                "колонки source/fstype/…",
            ),
        ],
    ),
    "du": (
        "du: место в каталоге",
        [
            ("du -sh \"$SRC\"", "итог $SRC"),
            ("du -h --max-depth=1 \"$SRC\"", "на один уровень"),
            ("du -h --max-depth=1 \"$SRC\" | sort -h", "тот же, по размеру"),
            ("du -x -sh \"$SRC\"", "не спускаться на другие FS"),
            ("du -h --max-depth=2 \"$SRC\" | sort -h | tail -n 30", "глубина 2, самые большие"),
        ],
    ),
    "mount": (
        "mount / findmnt: что смонтировано",
        [
            ("findmnt", "дерево монтирования"),
            ("findmnt -A", "все включая API FS"),
            ("findmnt $MNT", "точка $MNT"),
            ("mount", "таблица mount"),
            ("cat /proc/mounts", "/proc/mounts"),
            ("findmnt -T $MNT", "FS, содержащая путь $MNT"),
            ("mount $DISK $MNT", "смонтировать (меняет систему)"),
            ("umount $MNT", "размонтировать (меняет систему)"),
        ],
    ),
    "fdisk": (
        "fdisk: таблица разделов (осмотр)",
        [
            ("fdisk -l", "все диски"),
            ("fdisk -l $DISK", "разделы $DISK"),
            ("sfdisk -d $DISK", "дамп таблицы $DISK"),
            ("wipefs $DISK", "сигнатуры на $DISK (без -a)"),
        ],
    ),
    "lsblk": (
        "lsblk: блочные устройства",
        [
            ("lsblk", "дерево устройств"),
            ("lsblk -f", "FS и UUID"),
            (
                "lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,UUID,MODEL,SERIAL,ROTA",
                "размер, FS, модель",
            ),
            ("lsblk -p", "полные пути /dev/…"),
            ("lsblk $DISK", "только $DISK"),
            ("ls -l /dev/disk/by-id", "стабильные имена"),
        ],
    ),
    "smart": (
        "smartctl: здоровье диска",
        [
            ("smartctl --scan", "устройства SMART"),
            ("smartctl -i $DISK", "идентификация $DISK"),
            ("smartctl -H $DISK", "overall health"),
            ("smartctl -A $DISK", "атрибуты SMART"),
            ("smartctl -a $DISK", "полный отчёт"),
            ("smartctl -l error $DISK", "лог ошибок"),
            ("smartctl -l selftest $DISK", "история self-test"),
            ("smartctl -x $DISK", "расширенный отчёт"),
        ],
    ),
    "ncdu": (
        "ncdu: интерактивный du",
        [
            ("ncdu \"$SRC\"", "интерактивно (лучше: > ncdu \"$SRC\")"),
            ("ncdu -x \"$SRC\"", "одна файловая система (`> ncdu -x …`)"),
        ],
    ),
    "dsk": (
        "обзор дисков и места",
        [
            (
                "!lsblk[1] ; echo '--- df ---' ; !df[1] ; echo '--- smart scan ---' ; "
                "!smart[1] ; echo '--- health ---' ; !smart[3]",
                "lsblk → df -h → smartctl --scan → -H $DISK",
            ),
        ],
    ),
    "dustat": (
        "место в каталоге",
        [
            (
                "!du[2] ; echo '--- sorted ---' ; !du[3]",
                "max-depth=1 → sort -h",
            ),
        ],
    ),
}


def run_seed(db_file: str) -> int:
    return _run_seed(db_file, SEED_TAGS)


def main() -> None:
    seed_cli(
        description="Seed IDvjPy_term DB with df/du/mount/fdisk/lsblk/smartctl/ncdu (SEED_DISK_COMMANDS.md)",
        seed_help="Replace df/du/mount/fdisk/lsblk/smart/ncdu/dsk (does not touch tar/file)",
        seed_tags=SEED_TAGS,
        argv=sys.argv,
    )


if __name__ == "__main__":
    main()
