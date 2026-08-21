#!/usr/bin/env python3
"""
Seed L4/L7 debug handbook: tcpdump, nc, traceroute/mtr, openssl
(see SEED_NETDBG_COMMANDS.md).

Captures are bounded (`timeout` + `tcpdump -c`). mtr uses report mode (`-r`).
Does not touch linux `net`, recon nmap/dig, or netfw ss.

Run: python3 src/seed_netdbg.py --seed
"""
import sys

from seed_lib import run_seed as _run_seed
from seed_lib import seed_cli

SEED_TAGS = {
    "ndvars": (
        "переменные tcpdump/nc/tls",
        [
            (
                "echo host=$HOST port=$PORT iface=$IFACE sni=$SNI count=$COUNT",
                "проверка $HOST/$PORT/$IFACE/…",
            ),
        ],
    ),
    "pcap": (
        "tcpdump: короткий захват",
        [
            (
                "timeout 8 tcpdump -nn -c $COUNT -i $IFACE",
                "до $COUNT пакетов на $IFACE, 8с",
            ),
            (
                "timeout 8 tcpdump -nn -c $COUNT -i $IFACE port $PORT",
                "порт $PORT",
            ),
            (
                "timeout 8 tcpdump -nn -c $COUNT -i $IFACE host $HOST",
                "хост $HOST",
            ),
            (
                "timeout 8 tcpdump -nn -c $COUNT -i $IFACE 'tcp[tcpflags] & tcp-syn != 0'",
                "SYN",
            ),
            (
                "tcpdump -nn -i $IFACE",
                "follow (лучше: > tcpdump -nn -i $IFACE)",
            ),
        ],
    ),
    "ncat": (
        "nc: connect-check",
        [
            ("nc -vz $HOST $PORT", "TCP $HOST:$PORT"),
            ("timeout 5 nc -vz -w 3 $HOST $PORT", "TCP, таймаут 3с"),
            ("timeout 5 nc -vzu -w 3 $HOST $PORT", "UDP (ненадёжно)"),
            ("nc -vz $HOST 80 443 $PORT", "несколько портов"),
        ],
    ),
    "hops": (
        "traceroute / mtr",
        [
            ("traceroute -n $HOST", "hops, без DNS"),
            ("traceroute -n -T -p $PORT $HOST", "TCP SYN на $PORT"),
            ("tracepath $HOST", "tracepath"),
            ("mtr -c $COUNT -r -n $HOST", "mtr report, $COUNT циклов"),
            ("mtr -c $COUNT -r -n -T -P $PORT $HOST", "mtr TCP $PORT"),
            ("> mtr $HOST", "интерактивный mtr"),
        ],
    ),
    "tls": (
        "openssl s_client / x509",
        [
            (
                "echo | timeout 8 openssl s_client -connect $HOST:$PORT "
                "-servername $SNI -brief",
                "handshake $HOST:$PORT SNI $SNI",
            ),
            (
                "echo | timeout 8 openssl s_client -connect $HOST:$PORT "
                "-servername $SNI 2>/dev/null | openssl x509 -noout -dates -subject -issuer",
                "сертификат: dates/subject",
            ),
            (
                "echo | timeout 8 openssl s_client -connect $HOST:$PORT "
                "-servername $SNI 2>/dev/null | openssl x509 -noout -text | head -n 40",
                "x509 text, 40 строк",
            ),
            ("openssl version", "версия openssl"),
            (
                "> openssl s_client -connect $HOST:$PORT -servername $SNI",
                "интерактивный s_client",
            ),
        ],
    ),
    "npath": (
        "путь до $HOST",
        [
            (
                "!ncat[1] ; echo '--- hops ---' ; !hops[1] ; echo '--- mtr ---' ; !hops[4]",
                "nc -vz → traceroute → mtr -r",
            ),
        ],
    ),
    "tlschk": (
        "TLS handshake + даты сертификата",
        [
            (
                "!tls[1] ; echo '--- cert ---' ; !tls[2]",
                "s_client -brief → x509 dates",
            ),
        ],
    ),
}


def run_seed(db_file: str) -> int:
    return _run_seed(db_file, SEED_TAGS)


def main() -> None:
    seed_cli(
        description="Seed IDvjPy_term DB with tcpdump/nc/mtr/openssl (SEED_NETDBG_COMMANDS.md)",
        seed_help="Replace pcap/ncat/hops/tls/… (does not touch net/ss/nmap)",
        seed_tags=SEED_TAGS,
        argv=sys.argv,
    )


if __name__ == "__main__":
    main()
