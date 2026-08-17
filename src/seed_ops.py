#!/usr/bin/env python3
"""
Seed all operational handbooks at once:

  docker, helm, http (curl/nginx/traefik), netfw (ss/iptables/firewalld),
  data (postgres/kafka), host (tar/gz), disk (df/du/lsblk/smartctl),
  vault, text (grep/awk/sed), rsync, find, recon (dig/nmap), ssh/scp.

Does not run linux / k8s / git seeds.

Run: python3 src/seed_ops.py --seed
"""
import argparse
import sys

import seed_data
import seed_disk
import seed_docker
import seed_find
import seed_helm
import seed_host
import seed_http
import seed_netfw
import seed_recon
import seed_rsync
import seed_ssh
import seed_text
import seed_vault
from seed_lib import get_db_file

MODULES = (
    ("docker", seed_docker),
    ("helm", seed_helm),
    ("http", seed_http),
    ("netfw", seed_netfw),
    ("data", seed_data),
    ("host", seed_host),
    ("disk", seed_disk),
    ("vault", seed_vault),
    ("text", seed_text),
    ("rsync", seed_rsync),
    ("find", seed_find),
    ("recon", seed_recon),
    ("ssh", seed_ssh),
)


def run_seed(db_file: str) -> int:
    total = 0
    for name, mod in MODULES:
        n = mod.run_seed(db_file)
        print(f"  {name}: {n} commands")
        total += n
    return total


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed docker/helm/http/netfw/data/host/disk/vault/text/rsync/find/recon/ssh handbooks"
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Replace ops handbook tags (does not touch proc/file/net/kube/k*/git)",
    )
    parser.add_argument(
        "--db",
        default="",
        help="SQLite file (default: settings.yml database_tags_file)",
    )
    args = parser.parse_args()
    if not args.seed:
        print("Run with --seed to populate the database.", file=sys.stderr)
        sys.exit(0)
    db_file = args.db or get_db_file()
    n = run_seed(db_file)
    print(f"Seeded {n} commands into {db_file}")


if __name__ == "__main__":
    main()
