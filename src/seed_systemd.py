#!/usr/bin/env python3
"""
Seed systemd handbook: systemctl, journalctl, dmesg (see SEED_SYSTEMD_COMMANDS.md).

Playbooks are inspect-only: failed units, unit status+journal, kernel messages.
start/stop/restart/reload are in sctl but not in sstat/sfail/kmsg.
Follow (-f / -w) is marked for `> cmd`. Does not touch linux `logs` / `proc`.

Run: python3 src/seed_systemd.py --seed
"""
import sys

from seed_lib import run_seed as _run_seed
from seed_lib import seed_cli

SEED_TAGS = {
    "sysvars": (
        "переменные systemd",
        [
            (
                "echo unit=$UNIT since=$SINCE boot=$BOOT",
                "проверка $UNIT/$SINCE/$BOOT",
            ),
        ],
    ),
    "sctl": (
        "systemctl: units, status, start/stop",
        [
            ("systemctl --no-pager --failed", "упавшие units"),
            (
                "systemctl --no-pager list-units --type=service --state=failed",
                "failed services",
            ),
            ("systemctl --no-pager status $UNIT", "статус $UNIT"),
            ("systemctl show $UNIT --no-pager", "свойства $UNIT"),
            ("systemctl cat $UNIT --no-pager", "unit-файл $UNIT"),
            ("systemctl is-active $UNIT", "active/inactive $UNIT"),
            ("systemctl is-enabled $UNIT", "enabled/disabled $UNIT"),
            (
                "systemctl --no-pager list-units --type=service --state=running",
                "запущенные services",
            ),
            ("systemctl list-timers --all --no-pager", "таймеры"),
            ("systemctl daemon-reload", "перечитать unit-файлы"),
            ("systemctl reload $UNIT", "reload $UNIT (меняет сервис)"),
            ("systemctl restart $UNIT", "restart $UNIT (меняет сервис)"),
            ("systemctl start $UNIT", "start $UNIT"),
            ("systemctl stop $UNIT", "stop $UNIT"),
            ("systemctl reset-failed $UNIT", "сбросить failed $UNIT"),
        ],
    ),
    "jctl": (
        "journalctl: журнал systemd",
        [
            ("journalctl --no-pager -n 80", "последние 80 строк"),
            ("journalctl --no-pager -p err -n 80", "ошибки"),
            ("journalctl --no-pager -u $UNIT -n 100", "журнал $UNIT"),
            ("journalctl --no-pager -u $UNIT -p err -n 80", "ошибки $UNIT"),
            (
                'journalctl --no-pager -u $UNIT --since "$SINCE"',
                "журнал $UNIT с $SINCE",
            ),
            ("journalctl --no-pager --list-boots", "список загрузок"),
            ("journalctl --no-pager -b $BOOT -n 80", "журнал загрузки $BOOT"),
            ("journalctl --no-pager -k -n 80", "ядро (как dmesg)"),
            ("journalctl --disk-usage", "место журнала"),
            (
                "journalctl --no-pager -u $UNIT -o json-pretty -n 20",
                "JSON $UNIT → F5",
            ),
            (
                "journalctl -f -u $UNIT",
                "follow $UNIT (лучше: > journalctl -f -u $UNIT)",
            ),
        ],
    ),
    "dmesg": (
        "dmesg: кольцевой буфер ядра",
        [
            ("dmesg --color=never | tail -n 80", "последние 80 строк"),
            ("dmesg -T --color=never | tail -n 80", "с человеческим временем"),
            ("dmesg -T --level=err,warn --color=never", "err+warn"),
            ("dmesg -T --level=err --color=never", "только err"),
            (
                "dmesg --color=never -w",
                "follow (лучше: > dmesg -w)",
            ),
        ],
    ),
    "sfail": (
        "упавшие systemd units",
        [
            (
                "!sctl[1] ; echo '--- failed services ---' ; !sctl[2]",
                "--failed → list-units failed",
            ),
        ],
    ),
    "sstat": (
        "обзор unit: status + journal",
        [
            (
                "!sctl[3] ; echo '--- active ---' ; !sctl[6] ; echo '--- journal ---' ; !jctl[3]",
                "status → is-active → journal -u",
            ),
        ],
    ),
    "kmsg": (
        "сообщения ядра",
        [
            (
                "!dmesg[3] ; echo '--- journal -k ---' ; !jctl[8]",
                "dmesg err/warn → journalctl -k",
            ),
        ],
    ),
}


def run_seed(db_file: str) -> int:
    return _run_seed(db_file, SEED_TAGS)


def main() -> None:
    seed_cli(
        description="Seed IDvjPy_term DB with systemd handbook (SEED_SYSTEMD_COMMANDS.md)",
        seed_help="Replace sctl/jctl/dmesg/… (does not touch proc/logs/file)",
        seed_tags=SEED_TAGS,
        argv=sys.argv,
    )


if __name__ == "__main__":
    main()
