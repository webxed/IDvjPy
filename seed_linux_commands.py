#!/usr/bin/env python3
"""
Seed the IDvjPy_term database with a canonical set of Linux commands.

Command order and tid mapping are defined in LINUX_COMMANDS.md.
Run: python seed_linux_commands.py --seed

Uses database_tags_file from settings.yml (same as app.py).
"""
import os
import argparse
import sys

try:
    import yaml
    import database_v2 as database
except ImportError as e:
    print(f"Error: {e}", file=sys.stderr)
    print("Install dependencies: pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)

FILE_SETTINGS = "settings.yml"
ENCODING = "utf-8"
DEFAULT_DB = "history_v2.db"

# Порядок тегов: процессы → файлы → сеть → kubectl
TAG_COMMENTS = {
    "proc": "Процессы",
    "file": "Файлы и каталоги",
    "net": "Сеть",
    "kube": "Kubernetes (kubectl + tsh)",
}

# Команды по тегам (tid = 1, 2, 3…). Порядок тегов: proc, file, net, kube.
SEED_COMMANDS = {
    "proc": [
        "ps aux",
        "top",
        "htop",
        "kill",
        "killall",
        "pkill",
        "nohup",
        "jobs",
        "fg",
        "bg",
    ],
    "file": [
        "ls -la",
        "cp -r src dest",
        "mv src dest",
        "rm -i",
        "mkdir -p",
        "rmdir",
        "touch",
        "cat",
        "less",
        "head",
        "tail -f",
    ],
    "net": [
        "ss -tulnp",
        "ping -c 3",
        "curl -sI",
        "wget -qO-",
        "ssh",
        "rsync -avz",
        "scp",
        "ip addr",
        "ip route",
    ],
    "kube": [
        "tsh kube login CLUSTER",
        "kubectl config get-contexts",
        "kubectl config current-context",
        "kubectl cluster-info",
        "kubectl get ns",
        "kubectl get all -n $NS",
        "kubectl get pods -n $NS",
        "kubectl describe pod POD -n $NS",
        "kubectl logs POD -n $NS",
        "kubectl logs -f POD -n $NS",
        "kubectl exec -it POD -n $NS -- sh",
        "kubectl get deploy -n $NS",
        "kubectl describe deploy DEPLOY -n $NS",
        "kubectl rollout status deploy/DEPLOY -n $NS",
        "kubectl rollout restart deploy/DEPLOY -n $NS",
        "kubectl get svc -n $NS",
        "kubectl port-forward svc/SVC 8080:80 -n $NS",
        "kubectl apply -f FILE.yaml -n $NS",
        "kubectl delete -f FILE.yaml -n $NS",
    ],
}


def get_db_file():
    """Read database path from settings.yml, same logic as app.py."""
    if not os.path.exists(FILE_SETTINGS):
        return DEFAULT_DB
    try:
        with open(FILE_SETTINGS, "r", encoding=ENCODING) as f:
            settings = yaml.safe_load(f)
        if settings:
            return settings.get("database_tags_file", DEFAULT_DB)
    except Exception:
        pass
    return DEFAULT_DB


def hard_delete_commands_by_tag(db_file: str, tag: str) -> None:
    """Remove all rows for tag so new inserts get tid 1, 2, 3..."""
    conn = database.get_db_connection(db_file)
    conn.execute("DELETE FROM commands WHERE tag = ?", (tag,))
    conn.commit()
    conn.close()


def run_seed(db_file: str) -> None:
    """(Re)seed seed tags: hard-delete then add commands in order."""
    database.init_db(db_file)
    for tag, commands in SEED_COMMANDS.items():
        hard_delete_commands_by_tag(db_file, tag)
        for cmd in commands:
            database.add_command(db_file, cmd, tag)
        comment = TAG_COMMENTS.get(tag, "")
        if comment:
            database.set_tag_comment(db_file, tag, comment)
    print(f"Seeded {len(SEED_COMMANDS)} tags into {db_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Seed IDvjPy_term DB with Linux commands (see LINUX_COMMANDS.md)"
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Replace seed tags with canonical command set",
    )
    args = parser.parse_args()
    if not args.seed:
        print("Run with --seed to populate the database.", file=sys.stderr)
        sys.exit(0)
    db_file = get_db_file()
    run_seed(db_file)


if __name__ == "__main__":
    main()
