#!/usr/bin/env python3
"""
Seed package-manager handbook: apt, dnf, rpm (see SEED_PKG_COMMANDS.md).

Playbooks are query-only. install/remove are in tags, not in aptq/rpmq.

Run: python3 src/seed_pkg.py --seed
"""
import sys

from seed_lib import run_seed as _run_seed
from seed_lib import seed_cli

SEED_TAGS = {
    "pkvars": (
        "переменные пакетов",
        [
            ("echo pkg=$PKG", "проверка $PKG"),
        ],
    ),
    "apt": (
        "apt / dpkg (Debian/Ubuntu)",
        [
            ("apt-cache policy $PKG", "кандидат и установленная версия"),
            ("apt-cache show $PKG", "описание пакета"),
            ("apt-cache search $PKG", "поиск"),
            ("apt list --installed 2>/dev/null | grep -i $PKG", "установлен?"),
            ("apt list --upgradable 2>/dev/null", "обновления"),
            ("dpkg -l $PKG", "статус dpkg"),
            ("dpkg -L $PKG", "файлы пакета"),
            ("dpkg -S $PKG", "какой пакет владеет путём/именем"),
            ("apt update", "обновить индексы (меняет кэш)"),
            ("apt install $PKG", "поставить $PKG (меняет систему)"),
            ("apt remove $PKG", "убрать $PKG"),
        ],
    ),
    "dnf": (
        "dnf / yum (RHEL/Fedora)",
        [
            ("dnf info $PKG", "info $PKG"),
            ("dnf list installed $PKG", "установлен?"),
            ("dnf search $PKG", "поиск"),
            ("dnf check-update", "есть ли обновления"),
            ("dnf repoquery -l $PKG", "файлы пакета"),
            ("yum info $PKG", "yum info (старые хосты)"),
            ("dnf install $PKG", "поставить $PKG (меняет систему)"),
            ("dnf remove $PKG", "убрать $PKG"),
        ],
    ),
    "rpm": (
        "rpm: запросы (RHEL и не только)",
        [
            ("rpm -q $PKG", "установлен?"),
            ("rpm -qi $PKG", "info"),
            ("rpm -ql $PKG", "файлы"),
            ("rpm -qc $PKG", "конфиги"),
            ("rpm -qf $PKG", "$PKG как путь → пакет"),
            ("rpm -Va $PKG", "verify файлов пакета"),
        ],
    ),
    "aptq": (
        "осмотр apt: policy + upgradable",
        [
            (
                "!apt[1] ; echo '--- upgradable ---' ; !apt[5]",
                "policy → list --upgradable",
            ),
        ],
    ),
    "rpmq": (
        "осмотр rpm: query + info",
        [
            (
                "!rpm[1] ; echo '--- info ---' ; !rpm[2]",
                "rpm -q → rpm -qi",
            ),
        ],
    ),
}


def run_seed(db_file: str) -> int:
    return _run_seed(db_file, SEED_TAGS)


def main() -> None:
    seed_cli(
        description="Seed IDvjPy_term DB with apt/dnf/rpm handbook (SEED_PKG_COMMANDS.md)",
        seed_help="Replace apt/dnf/rpm/… (does not touch proc/file)",
        seed_tags=SEED_TAGS,
        argv=sys.argv,
    )


if __name__ == "__main__":
    main()
