#!/usr/bin/env python3
"""
Seed host-info / lsof / strace handbook (see SEED_SYSINFO_COMMANDS.md).

Playbooks are inspect-only and time-bounded: no live strace -p without timeout.
Does not touch linux `proc` (ps/top/kill) or netfw `ss`.

Run: python3 src/seed_sysinfo.py --seed
"""
import sys

from seed_lib import run_seed as _run_seed
from seed_lib import seed_cli

SEED_TAGS = {
    "hivars": (
        "переменные hostinfo / lsof / strace",
        [
            (
                "echo pid=$PID port=$PORT file=$FILE cmd=$CMD proc=$PROC trace=$TRACE",
                "проверка $PID/$PORT/$CMD/…",
            ),
        ],
    ),
    "hinfo": (
        "хост: kernel, время, память, CPU",
        [
            ("uname -a", "ядро и hostname"),
            ("cat /etc/os-release", "дистрибутив"),
            ("hostnamectl --no-pager", "hostname / machine-id"),
            ("timedatectl --no-pager", "часы и NTP"),
            ("uptime", "uptime и load"),
            ("free -h", "RAM / swap"),
            ("lscpu", "CPU"),
            ("nproc", "число CPU"),
        ],
    ),
    "lsof": (
        "lsof: файлы, порты, PID",
        [
            (
                "lsof -nP -iTCP:$PORT -sTCP:LISTEN",
                "кто слушает TCP $PORT",
            ),
            ("lsof -nP -i :$PORT", "сокеты на $PORT"),
            ("lsof -nP -p $PID", "файлы процесса $PID"),
            ('lsof -nP "$FILE"', "кто открыл $FILE"),
            ("lsof -nP -c $PROC", "процессы имени $PROC"),
            (
                "lsof -nP -iTCP -sTCP:LISTEN | head -n 40",
                "первые 40 TCP listen",
            ),
            (
                "lsof -nP -u $USER | head -n 40",
                "файлы пользователя $USER",
            ),
        ],
    ),
    "strace": (
        "strace: системные вызовы",
        [
            ("strace -V", "версия strace"),
            ("strace -c -- $CMD", "сводка сисвызовов $CMD"),
            ("strace -f -c -- $CMD", "сводка, с детьми"),
            (
                "strace -f -c -e trace=$TRACE -- $CMD",
                "сводка фильтра $TRACE",
            ),
            (
                "strace -f -e trace=$TRACE -- $CMD",
                "трасса $CMD (короткая команда)",
            ),
            (
                "timeout 8 strace -c -p $PID",
                "сводка $PID, 8с (нужен ptrace)",
            ),
            (
                "timeout 8 strace -f -e trace=$TRACE -p $PID",
                "фильтр $TRACE на $PID, 8с",
            ),
            (
                "strace -p $PID",
                "follow $PID (лучше: > strace -p $PID)",
            ),
        ],
    ),
    "hstat": (
        "обзор хоста",
        [
            (
                "!hinfo[1] ; echo '--- uptime ---' ; !hinfo[5] ; echo '--- mem ---' ; !hinfo[6]",
                "uname → uptime → free",
            ),
        ],
    ),
    "lport": (
        "кто слушает $PORT",
        [
            (
                "!lsof[1] ; echo '--- all on port ---' ; !lsof[2]",
                "LISTEN TCP → все сокеты $PORT",
            ),
        ],
    ),
    "pdbg": (
        "процесс: lsof + strace -c",
        [
            (
                "!lsof[3] ; echo '--- strace -c ---' ; !strace[6]",
                "lsof -p → timeout strace -c -p",
            ),
        ],
    ),
}


def run_seed(db_file: str) -> int:
    return _run_seed(db_file, SEED_TAGS)


def main() -> None:
    seed_cli(
        description="Seed IDvjPy_term DB with hostinfo/lsof/strace (SEED_SYSINFO_COMMANDS.md)",
        seed_help="Replace hinfo/lsof/strace/… (does not touch proc/ss/file)",
        seed_tags=SEED_TAGS,
        argv=sys.argv,
    )


if __name__ == "__main__":
    main()
