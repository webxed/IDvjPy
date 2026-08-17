#!/usr/bin/env python3
"""
Seed HashiCorp Vault handbook tags (see SEED_VAULT_COMMANDS.md).

Playbooks are inspect-only: no seal, revoke, kv put/delete.
vvars does not echo VAULT_TOKEN (only set/unset).

Run: python3 src/seed_vault.py --seed
"""
import sys

from seed_lib import run_seed as _run_seed
from seed_lib import seed_cli

SEED_TAGS = {
    "vvars": (
        "переменные vault (токен не печатается)",
        [
            (
                "echo addr=$VAULT_ADDR ns=$VAULT_NAMESPACE mount=$MOUNT "
                "secret=$SECRET role=$ROLE policy=$POLICY field=$FIELD "
                "token=$( [ -n \"$VAULT_TOKEN\" ] && echo set || echo unset )",
                "проверка $VAULT_ADDR/$SECRET/…; token=set|unset",
            ),
        ],
    ),
    "vault": (
        "vault: статус, auth, kv metadata",
        [
            ("vault status", "sealed / HA / версия"),
            ("vault status -format=json", "status JSON → F5"),
            ("vault read sys/health", "health (нужен адрес)"),
            (
                "curl -sS $VAULT_ADDR/v1/sys/health",
                "health HTTP без CLI (часто без токена)",
            ),
            ("vault auth list", "методы auth"),
            ("vault secrets list", "secret engines"),
            ("vault policy list", "политики"),
            ("vault policy read $POLICY", "текст политики $POLICY"),
            ("vault audit list", "audit devices"),
            ("vault token lookup", "текущий токен: ttl, policies (не сам token)"),
            ("vault token lookup -format=json", "lookup JSON → F5"),
            ("vault kv list $MOUNT", "ключи на mount $MOUNT"),
            ("vault kv list $SECRET", "ключи в $SECRET"),
            ("vault kv metadata get $SECRET", "метаданные KV (без значений)"),
            (
                "vault kv metadata get -format=json $SECRET",
                "metadata JSON → F5",
            ),
            ("vault kv get $SECRET", "прочитать секрет (попадёт в журнал)"),
            ("vault kv get -field=$FIELD $SECRET", "одно поле $FIELD"),
            ("vault operator raft list-peers", "Raft peers (HA)"),
            ("vault operator raft autopilot state", "autopilot"),
            ("vault read auth/approle/role/$ROLE", "AppRole $ROLE"),
            ("vault login", "login (лучше: > vault login)"),
            ("vault kv put $SECRET $FIELD=value", "записать поле (меняет Vault)"),
        ],
    ),
    "vstat": (
        "обзор Vault",
        [
            (
                "!vault[1] ; echo '--- health ---' ; !vault[4] ; "
                "echo '--- auth ---' ; !vault[5] ; echo '--- secrets ---' ; !vault[6]",
                "status → health HTTP → auth → engines",
            ),
        ],
    ),
    "vkv": (
        "осмотр KV без значений",
        [
            (
                "!vault[13] ; echo '--- metadata ---' ; !vault[14]",
                "kv list $SECRET → metadata get (не kv get)",
            ),
        ],
    ),
}


def run_seed(db_file: str) -> int:
    return _run_seed(db_file, SEED_TAGS)


def main() -> None:
    seed_cli(
        description="Seed IDvjPy_term DB with Vault handbook (SEED_VAULT_COMMANDS.md)",
        seed_help="Replace vault/vvars/vstat/vkv (does not touch proc/kube/git)",
        seed_tags=SEED_TAGS,
        argv=sys.argv,
    )


if __name__ == "__main__":
    main()
