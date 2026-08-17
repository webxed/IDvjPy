#!/usr/bin/env python3
"""
Seed helm handbook tags (see SEED_HELM_COMMANDS.md).

Does not touch kube / kpod / … from seed_k8s_chains.py.

Run: python3 src/seed_helm.py --seed
"""
import sys

from seed_lib import run_seed as _run_seed
from seed_lib import seed_cli

SEED_TAGS = {
    "hvars": (
        "переменные helm",
        [
            (
                "echo ns=$NS release=$RELEASE chart=$CHART values=$VALUES",
                "проверка $NS/$RELEASE/…",
            ),
        ],
    ),
    "helm": (
        "helm: релизы, values, dry-run",
        [
            ("helm list -n $NS", "релизы в $NS"),
            ("helm list -A", "релизы во всех namespace"),
            ("helm status $RELEASE -n $NS", "статус $RELEASE"),
            ("helm history $RELEASE -n $NS", "история ревизий"),
            ("helm get values $RELEASE -n $NS", "values релиза"),
            ("helm get manifest $RELEASE -n $NS", "манифесты релиза"),
            ("helm get notes $RELEASE -n $NS", "notes релиза"),
            ("helm repo list", "chart-репозитории"),
            ("helm search repo $CHART", "поиск чарта $CHART"),
            ("helm show chart $CHART", "метаданные чарта"),
            ("helm show values $CHART", "values чарта по умолчанию"),
            ("helm template $RELEASE $CHART -n $NS -f $VALUES", "рендер без кластера"),
            (
                "helm upgrade --install $RELEASE $CHART -n $NS -f $VALUES --dry-run --debug",
                "dry-run upgrade",
            ),
            (
                "helm upgrade --install $RELEASE $CHART -n $NS -f $VALUES",
                "upgrade --install (меняет кластер)",
            ),
            ("helm rollback $RELEASE 0 -n $NS --dry-run", "dry-run rollback"),
            ("helm uninstall $RELEASE -n $NS --dry-run", "dry-run uninstall"),
            ("helm env", "окружение helm"),
        ],
    ),
    "hls": (
        "обзор helm-релиза",
        [
            (
                "!helm[1] ; echo '--- status ---' ; !helm[3] ; echo '--- history ---' ; !helm[4] ; echo '--- values ---' ; !helm[5]",
                "list → status → history → values",
            ),
        ],
    ),
}


def run_seed(db_file: str) -> int:
    return _run_seed(db_file, SEED_TAGS)


def main() -> None:
    seed_cli(
        description="Seed IDvjPy_term DB with helm handbook (SEED_HELM_COMMANDS.md)",
        seed_help="Replace helm/hvars/hls (does not touch kube/kpod/…)",
        seed_tags=SEED_TAGS,
        argv=sys.argv,
    )


if __name__ == "__main__":
    main()
