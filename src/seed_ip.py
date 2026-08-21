#!/usr/bin/env python3
"""
Seed iproute2 + ethtool handbook (see SEED_IP_COMMANDS.md).

Playbooks are inspect-only: link/addr/route/neigh/stats.
ip link set up/down and addr/route add are in tags, not in ilink/iiface.
Does not touch linux `net` (ip addr / ip route stay there).

Run: python3 src/seed_ip.py --seed
"""
import sys

from seed_lib import run_seed as _run_seed
from seed_lib import seed_cli

SEED_TAGS = {
    "ipvars": (
        "переменные ip/ethtool",
        [
            (
                "echo iface=$IFACE addr=$ADDR gw=$GW",
                "проверка $IFACE/$ADDR/$GW",
            ),
        ],
    ),
    "ip": (
        "ip: link, addr, route, neigh",
        [
            ("ip -br link", "интерфейсы кратко"),
            ("ip -br addr", "адреса кратко"),
            ("ip link show $IFACE", "link $IFACE"),
            ("ip addr show $IFACE", "адреса $IFACE"),
            ("ip -s link show $IFACE", "счётчики $IFACE"),
            ("ip -s -s link show $IFACE", "счётчики подробно"),
            ("ip route", "маршруты IPv4"),
            ("ip -6 route", "маршруты IPv6"),
            ("ip route show default", "default via"),
            ("ip neigh", "ARP / NDISC"),
            ("ip neigh show dev $IFACE", "neigh $IFACE"),
            ("ip -4 addr", "только IPv4"),
            ("ip -6 addr", "только IPv6"),
            ("ip rule", "policy routing"),
            ("ip netns list", "network namespaces"),
            ("ip link set $IFACE up", "поднять $IFACE"),
            ("ip link set $IFACE down", "опустить $IFACE"),
            ("ip addr add $ADDR dev $IFACE", "добавить $ADDR"),
            ("ip route add default via $GW", "default via $GW"),
        ],
    ),
    "eth": (
        "ethtool: NIC",
        [
            ("ethtool $IFACE", "скорость / duplex $IFACE"),
            ("ethtool -i $IFACE", "драйвер"),
            ("ethtool -k $IFACE", "offload"),
            ("ethtool -S $IFACE | head -n 40", "статистика, 40 строк"),
            ("ethtool --show-ring $IFACE", "ring buffers"),
        ],
    ),
    "ilink": (
        "обзор ip: link + addr + route",
        [
            (
                "!ip[1] ; echo '--- addr ---' ; !ip[2] ; echo '--- route ---' ; !ip[7]",
                "br link → br addr → route",
            ),
        ],
    ),
    "iiface": (
        "интерфейс $IFACE: link, stats, driver",
        [
            (
                "!ip[3] ; echo '--- stats ---' ; !ip[5] ; echo '--- ethtool ---' ; !eth[2]",
                "link show → -s → ethtool -i",
            ),
        ],
    ),
}


def run_seed(db_file: str) -> int:
    return _run_seed(db_file, SEED_TAGS)


def main() -> None:
    seed_cli(
        description="Seed IDvjPy_term DB with ip/ethtool handbook (SEED_IP_COMMANDS.md)",
        seed_help="Replace ip/eth/ilink/… (does not touch net/ss/proc)",
        seed_tags=SEED_TAGS,
        argv=sys.argv,
    )


if __name__ == "__main__":
    main()
