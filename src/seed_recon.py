#!/usr/bin/env python3
"""
Seed DNS + port-scan handbook: dig, nmap (see SEED_RECON_COMMANDS.md).

Playbooks: DNS lookup and a short connect-scan. No -p-, --script vuln, -A.
Does not touch linux `net`.

Run: python3 src/seed_recon.py --seed
"""
import sys

from seed_lib import run_seed as _run_seed
from seed_lib import seed_cli

SEED_TAGS = {
    "qvars": (
        "переменные dig/nmap",
        [
            (
                "echo host=$HOST port=$PORT cidr=$CIDR dns=$DNS ip=$IP",
                "проверка $HOST/$PORT/…",
            ),
        ],
    ),
    "dig": (
        "dig: A/AAAA/MX/NS/PTR",
        [
            ("dig $HOST", "полный ответ"),
            ("dig +short $HOST", "только A/AAAA"),
            ("dig +short $HOST A", "A"),
            ("dig +short $HOST AAAA", "AAAA"),
            ("dig $HOST MX", "MX"),
            ("dig $HOST NS", "NS"),
            ("dig $HOST SOA", "SOA"),
            ("dig $HOST TXT", "TXT"),
            ("dig $HOST CNAME", "CNAME"),
            ("dig @$DNS $HOST", "через резолвер $DNS"),
            ("dig -x $IP", "PTR (reverse)"),
            ("dig +trace $HOST", "трассировка делегирования"),
            ("dig +noall +answer $HOST", "только answer-секция"),
        ],
    ),
    "nmap": (
        "nmap: ping и короткий connect-scan",
        [
            ("nmap -sn $HOST", "ping-scan (хост жив?)"),
            (
                "nmap -sT -Pn --top-ports 20 --host-timeout 15s --max-retries 1 $HOST",
                "TCP connect, top 20, без ping",
            ),
            (
                "nmap -sT -Pn -p $PORT --host-timeout 10s $HOST",
                "один порт $PORT",
            ),
            (
                "nmap -sV -Pn -p $PORT --host-timeout 20s --max-retries 1 $HOST",
                "версия сервиса на $PORT",
            ),
            ("nmap -sn $CIDR", "ping-scan сети $CIDR"),
            (
                "nmap -sT -Pn --reason -p $PORT --host-timeout 10s $HOST",
                "порт $PORT + reason",
            ),
            (
                "nmap -sU -Pn -p $PORT --host-timeout 15s $HOST",
                "UDP $PORT (часто нужен root)",
            ),
            (
                "nmap -sS -Pn --top-ports 20 --host-timeout 15s $HOST",
                "SYN-scan (нужен root)",
            ),
        ],
    ),
    "dchk": (
        "DNS: short + NS",
        [
            (
                "!dig[2] ; echo '--- NS ---' ; !dig[6]",
                "+short → NS",
            ),
        ],
    ),
    "nchk": (
        "короткий осмотр хоста",
        [
            (
                "!nmap[1] ; echo '--- top ports ---' ; !nmap[2]",
                "ping-scan → top 20 TCP (без -A/-p-)",
            ),
        ],
    ),
}


def run_seed(db_file: str) -> int:
    return _run_seed(db_file, SEED_TAGS)


def main() -> None:
    seed_cli(
        description="Seed IDvjPy_term DB with dig/nmap handbook (SEED_RECON_COMMANDS.md)",
        seed_help="Replace dig/nmap/dchk/nchk (does not touch net/ss/proc)",
        seed_tags=SEED_TAGS,
        argv=sys.argv,
    )


if __name__ == "__main__":
    main()
