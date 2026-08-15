#!/usr/bin/env python3
"""
Seed investigation tags for Kubernetes (see K8S_CHAINS.md).

Does not touch proc / file / net / kube from seed_linux_commands.py.

Run: python3 seed_k8s_chains.py --seed

Uses database_tags_file from settings.yml (same as app.py).
"""
import argparse
import os
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
DEFAULT_DB = "mytags.db"

# tag -> (tag comment, [(command, command comment), ...])
# tid = 1-based index in each list. Playbooks reference these tids.
SEED_TAGS = {
    "kvars": (
        "переменные инцидента",
        [
            (
                "echo ns=$NS pod=$POD deploy=$DEPLOY svc=$SVC ing=$ING app=$APP ctr=$CTR",
                "проверка $NS/$POD/…",
            ),
        ],
    ),
    "kns": (
        "кластер / namespace",
        [
            ("kubectl config current-context", "текущий context"),
            ("kubectl config get-contexts", "все context"),
            ("kubectl get ns", "список namespace"),
            ("kubectl get ns $NS -o yaml", "yaml namespace $NS"),
            ("kubectl api-resources --namespaced=true --verbs=list", "namespaced API"),
        ],
    ),
    "kpod": (
        "поды в $NS",
        [
            ("kubectl get pods -n $NS -o wide", "все поды wide"),
            (
                "kubectl get pods -n $NS --field-selector=status.phase!=Running",
                "не Running",
            ),
            ("kubectl get pods -n $NS -l app=$APP -o wide", "поды $APP"),
            ("kubectl describe pod $POD -n $NS", "describe $POD"),
            ("kubectl get pod $POD -n $NS -o json", "json $POD → F5"),
            (
                "kubectl get pod $POD -n $NS -o jsonpath="
                "'{.status.containerStatuses[*].name}{\"\\n\"}"
                "{.status.containerStatuses[*].state}{\"\\n\"}"
                "{.status.containerStatuses[*].lastState}{\"\\n\"}'",
                "state контейнеров",
            ),
            ("kubectl top pod -n $NS", "метрики подов"),
            (
                "kubectl get pod $POD -n $NS -o jsonpath="
                "'{.spec.nodeName}{\"\\n\"}{.status.podIP}{\"\\n\"}{.status.hostIP}{\"\\n\"}'",
                "node / podIP / hostIP",
            ),
        ],
    ),
    "klog": (
        "логи $POD (без follow)",
        [
            ("kubectl logs $POD -n $NS --tail=200", "логи $POD"),
            ("kubectl logs $POD -n $NS -c $CTR --tail=200", "логи контейнера $CTR"),
            ("kubectl logs $POD -n $NS --previous --tail=200", "previous logs"),
            (
                "kubectl logs -n $NS -l app=$APP --tail=100 --max-log-requests=10",
                "логи $APP",
            ),
            (
                "kubectl logs $POD -n $NS --tail=200 | grep -iE 'error|exception|fatal|panic|oom'",
                "grep ошибок",
            ),
        ],
    ),
    "kev": (
        "events $NS / $POD",
        [
            ("kubectl get events -n $NS --sort-by=.lastTimestamp", "все events"),
            (
                "kubectl get events -n $NS --field-selector involvedObject.name=$POD",
                "events $POD",
            ),
            (
                "kubectl get events -n $NS --field-selector type=Warning --sort-by=.lastTimestamp",
                "только Warning",
            ),
        ],
    ),
    "ksvc": (
        "сервис и endpoints",
        [
            ("kubectl get svc,ep -n $NS", "svc + endpoints"),
            ("kubectl describe svc $SVC -n $NS", "describe $SVC"),
            ("kubectl get endpoints $SVC -n $NS -o yaml", "endpoints yaml"),
            (
                "kubectl get endpointslice -n $NS -l kubernetes.io/service-name=$SVC",
                "endpointslice $SVC",
            ),
            ("kubectl get networkpolicy -n $NS", "NetworkPolicy"),
        ],
    ),
    "king": (
        "ingress (рядом с :i)",
        [
            ("kubectl get ingress -n $NS -o wide", "список ingress"),
            ("kubectl describe ingress $ING -n $NS", "describe $ING"),
            ("kubectl get ingress $ING -n $NS -o json", "json $ING → F5"),
        ],
    ),
    "kdep": (
        "deploy / rs / rollout",
        [
            ("kubectl get deploy,rs,sts,ds -n $NS", "workload в $NS"),
            ("kubectl describe deploy $DEPLOY -n $NS", "describe $DEPLOY"),
            ("kubectl get deploy $DEPLOY -n $NS -o json", "json $DEPLOY → F5"),
            ("kubectl rollout status deploy/$DEPLOY -n $NS", "rollout status"),
            ("kubectl rollout history deploy/$DEPLOY -n $NS", "rollout history"),
            ("kubectl get rs -n $NS -l app=$APP -o wide", "ReplicaSet $APP"),
        ],
    ),
    "kjq": (
        "jq к stdout блока",
        [
            (
                "jq '.items[] | {name:.metadata.name, phase:.status.phase, "
                "restarts:.status.containerStatuses[0].restartCount, "
                "ready:.status.containerStatuses[0].ready}'",
                "список подов → name/phase/restarts",
            ),
            (
                "jq '.status.containerStatuses[] | {name, ready, restarts:.restartCount, state, lastState}'",
                "состояние контейнеров",
            ),
            ("jq '.status.conditions'", "conditions"),
            (
                "jq '.spec.containers[] | {name, image, resources, ports}'",
                "image / resources",
            ),
            ("jq '.subsets[]?.addresses[]?.ip'", "IP из endpoints"),
            (
                "jq '.spec.rules[] | {host, paths:[.http.paths[] | {path, svc:.backend.service.name}]}'",
                "правила ingress",
            ),
        ],
    ),
    "kcrash": (
        "под не Running: describe → previous logs → events",
        [
            (
                "!kpod[2] ; echo '--- describe ---' ; !kpod[4] ; "
                "echo '--- previous logs ---' ; !klog[3] ; echo '--- events ---' ; !kev[2]",
                "CrashLoop / ImagePull / OOM",
            ),
        ],
    ),
    "knet": (
        "svc / endpoints / поды приложения",
        [
            (
                "!ksvc[1] ; echo '--- svc ---' ; !ksvc[2] ; "
                "echo '--- endpoints ---' ; !ksvc[3] ; echo '--- pods ---' ; !kpod[3]",
                "0 endpoints / нет трафика",
            ),
        ],
    ),
    "kroll": (
        "deploy + status + rs",
        [
            (
                "!kdep[2] ; echo '--- status ---' ; !kdep[4] ; "
                "echo '--- rs ---' ; !kdep[6] ; echo '--- not running ---' ; !kpod[2]",
                "rollout застрял",
            ),
        ],
    ),
    "kwatch": (
        "wide + warnings",
        [
            (
                "!kpod[1] ; echo '--- not running ---' ; !kpod[2] ; "
                "echo '--- warnings ---' ; !kev[3]",
                "что случилось в $NS",
            ),
        ],
    ),
}


def get_db_file() -> str:
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
    conn.execute("DELETE FROM tags WHERE tag = ?", (tag,))
    conn.commit()
    conn.close()


def run_seed(db_file: str) -> int:
    """Replace investigation tags; return number of commands inserted."""
    database.init_db(db_file)
    n = 0
    for tag, (tag_comment, commands) in SEED_TAGS.items():
        hard_delete_commands_by_tag(db_file, tag)
        for cmd, cmd_comment in commands:
            tid = database.add_command(db_file, cmd, tag)
            if cmd_comment:
                database.set_command_comment(db_file, tag, tid, cmd_comment)
            n += 1
        if tag_comment:
            database.set_tag_comment(db_file, tag, tag_comment)
    return n


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed IDvjPy_term DB with k8s investigation chains (K8S_CHAINS.md)"
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Replace kns/kpod/klog/…/kcrash tags (does not touch proc/file/net/kube)",
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
    print(f"Seeded {len(SEED_TAGS)} tags ({n} commands) into {db_file}")


if __name__ == "__main__":
    main()
