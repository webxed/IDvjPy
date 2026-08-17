#!/usr/bin/env python3
"""
Seed sockets + firewall handbook: ss, netstat, iptables, firewall-cmd
(see SEED_NETFW_COMMANDS.md).

Does not touch the linux `net` tag. Playbooks are inspect-only
(no iptables -F / panic-on).

Run: python3 src/seed_netfw.py --seed
"""
import sys

from seed_lib import run_seed as _run_seed
from seed_lib import seed_cli

SEED_TAGS = {
    "nvars": (
        "переменные сети/firewall",
        [
            (
                "echo port=$PORT zone=$ZONE proto=$PROTO",
                "проверка $PORT/$ZONE/…",
            ),
        ],
    ),
    "ss": (
        "ss: сокеты и состояния",
        [
            ("ss -tulnp", "TCP/UDP listen + процессы"),
            ("ss -tlnp", "только TCP listen"),
            ("ss -ulnp", "только UDP listen"),
            ("ss -s", "сводка сокетов"),
            ("ss -tnp state established", "установленные TCP"),
            ("ss -tnp state time-wait", "TIME-WAIT"),
            ("ss -tnp sport = :$PORT", "по локальному порту $PORT"),
            ("ss -tnp dport = :$PORT", "по удалённому порту $PORT"),
            ("ss -xlnp", "UNIX listen"),
            ("ss -tuln | grep $PORT", "фильтр $PORT без процессов"),
        ],
    ),
    "nst": (
        "netstat (старые хосты)",
        [
            ("netstat -tulnp", "listen TCP/UDP + процессы"),
            ("netstat -tlnp", "TCP listen"),
            ("netstat -s", "статистика стека"),
            ("netstat -i", "интерфейсы"),
            ("netstat -rn", "таблица маршрутов"),
            ("netstat -tpn", "TCP с PID"),
        ],
    ),
    "ipt": (
        "iptables: осмотр правил",
        [
            ("iptables -L -n -v --line-numbers", "filter, счётчики"),
            ("iptables -t nat -L -n -v --line-numbers", "nat"),
            ("iptables -t mangle -L -n -v --line-numbers", "mangle"),
            ("iptables -S", "filter в виде -A/-P"),
            ("iptables -t nat -S", "nat в виде -A/-P"),
            ("iptables -L INPUT -n -v --line-numbers", "цепочка INPUT"),
            ("iptables -L FORWARD -n -v --line-numbers", "цепочка FORWARD"),
            ("iptables-save", "полный дамп"),
            ("ip6tables -L -n -v --line-numbers", "IPv6 filter"),
            (
                "iptables -C INPUT -p tcp --dport $PORT -j ACCEPT",
                "есть ли ACCEPT на $PORT (exit 1 = нет)",
            ),
        ],
    ),
    "fwd": (
        "firewall-cmd (firewalld)",
        [
            ("firewall-cmd --state", "запущен ли firewalld"),
            ("firewall-cmd --get-active-zones", "активные зоны"),
            ("firewall-cmd --get-default-zone", "зона по умолчанию"),
            ("firewall-cmd --list-all", "текущая зона подробно"),
            ("firewall-cmd --list-all-zones", "все зоны"),
            ("firewall-cmd --zone=$ZONE --list-all", "зона $ZONE"),
            ("firewall-cmd --zone=$ZONE --list-ports", "порты $ZONE"),
            ("firewall-cmd --zone=$ZONE --list-services", "сервисы $ZONE"),
            ("firewall-cmd --query-port=$PORT/tcp", "открыт ли $PORT/tcp"),
            ("firewall-cmd --permanent --list-all", "permanent текущей зоны"),
            ("firewall-cmd --add-port=$PORT/tcp", "открыть $PORT runtime"),
            ("firewall-cmd --permanent --add-port=$PORT/tcp", "открыть $PORT permanent"),
            ("firewall-cmd --reload", "применить permanent"),
        ],
    ),
    "nstat": (
        "обзор сокетов",
        [
            (
                "!ss[1] ; echo '--- summary ---' ; !ss[4]",
                "listen + сводка",
            ),
        ],
    ),
    "iptstat": (
        "обзор iptables",
        [
            (
                "!ipt[1] ; echo '--- nat ---' ; !ipt[2]",
                "filter + nat (без -F)",
            ),
        ],
    ),
    "fwstat": (
        "обзор firewalld",
        [
            (
                "!fwd[1] ; echo '--- zones ---' ; !fwd[2] ; echo '--- list ---' ; !fwd[4]",
                "state → zones → list-all",
            ),
        ],
    ),
}


def run_seed(db_file: str) -> int:
    return _run_seed(db_file, SEED_TAGS)


def main() -> None:
    seed_cli(
        description="Seed IDvjPy_term DB with ss/netstat/iptables/firewalld (SEED_NETFW_COMMANDS.md)",
        seed_help="Replace ss/nst/ipt/fwd/… (does not touch net/proc)",
        seed_tags=SEED_TAGS,
        argv=sys.argv,
    )


if __name__ == "__main__":
    main()
