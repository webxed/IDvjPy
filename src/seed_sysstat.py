#!/usr/bin/env python3
"""
Seed sysstat handbook: vmstat, iostat, mpstat (see SEED_SYSSTAT_COMMANDS.md).

Samples are finite (`$DELAY` × `$SAMPLES`). htop/iotop/iftop need a TTY (`>`).
Does not touch linux `proc` or systemd `sstat`.

Run: python3 src/seed_sysstat.py --seed
"""
import sys

from seed_lib import run_seed as _run_seed
from seed_lib import seed_cli

SEED_TAGS = {
    "stvars": (
        "переменные sysstat",
        [
            (
                "echo delay=$DELAY samples=$SAMPLES disk=$DISK pid=$PID iface=$IFACE",
                "проверка $DELAY/$SAMPLES/…",
            ),
        ],
    ),
    "vmstat": (
        "vmstat: procs, memory, io, cpu",
        [
            ("vmstat", "один снимок"),
            ("vmstat -s", "сводка памяти"),
            ("vmstat -d", "диск"),
            ("vmstat $DELAY $SAMPLES", "каждые $DELAY с, $SAMPLES раз"),
            ("vmstat -w $DELAY $SAMPLES", "широкие колонки"),
        ],
    ),
    "iostat": (
        "iostat: CPU и диск",
        [
            ("iostat -y", "один снимок (без avg-since-boot)"),
            ("iostat -xz $DELAY $SAMPLES", "extended, $SAMPLES раз"),
            ("iostat -xz $DISK $DELAY $SAMPLES", "диск $DISK"),
            ("iostat -N -xz $DELAY $SAMPLES", "с LVM-именами"),
        ],
    ),
    "mpstat": (
        "mpstat: CPU по ядрам",
        [
            ("mpstat", "один снимок"),
            ("mpstat -P ALL $DELAY $SAMPLES", "все CPU, $SAMPLES раз"),
            ("pidstat $DELAY $SAMPLES", "процессы, CPU"),
            ("pidstat -p $PID $DELAY $SAMPLES", "PID $PID"),
            ("sar -u $DELAY $SAMPLES", "CPU через sar"),
        ],
    ),
    "monui": (
        "интерактивные мониторы (TTY)",
        [
            ("> htop", "htop"),
            ("> iotop", "iotop (часто нужен root)"),
            ("> iftop -i $IFACE", "iftop на $IFACE"),
        ],
    ),
    "oload": (
        "нагрузка: vmstat + iostat",
        [
            (
                "!vmstat[4] ; echo '--- iostat ---' ; !iostat[2]",
                "vmstat N → iostat -xz N",
            ),
        ],
    ),
}


def run_seed(db_file: str) -> int:
    return _run_seed(db_file, SEED_TAGS)


def main() -> None:
    seed_cli(
        description="Seed IDvjPy_term DB with vmstat/iostat/mpstat (SEED_SYSSTAT_COMMANDS.md)",
        seed_help="Replace vmstat/iostat/mpstat/… (does not touch proc/sstat)",
        seed_tags=SEED_TAGS,
        argv=sys.argv,
    )


if __name__ == "__main__":
    main()
