#!/usr/bin/env python3
"""
Seed investigation tags for Kubernetes (see K8S_CHAINS.md).

Does not touch proc / file / net / kube from seed_linux_commands.py.

Run: python3 src/seed_k8s_chains.py --seed

Uses database_tags_file from settings.yml (same as app.py).
"""
import sys

from seed_lib import run_seed as _run_seed
from seed_lib import seed_cli

# tag -> (tag comment, [(command, command comment), ...])
# tid = 1-based index in each list. Playbooks reference these tids.
SEED_TAGS = {
    "kvars": (
        "переменные инцидента",
        [
            (
                "echo ns=$NS pod=$POD deploy=$DEPLOY svc=$SVC ing=$ING app=$APP "
                "ctr=$CTR quota=$QUOTA sa=$SA",
                "проверка $NS/$POD/…/$QUOTA/$SA",
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
            ("kubectl get nodes -o wide", "ноды wide (версия/OС/адреса)"),
            ("kubectl auth can-i --list -n $NS", "мои права в $NS"),
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
            (
                "kubectl get pod $POD -n $NS -o jsonpath="
                "'{.status.phase}{\"\\n\"}{.status.reason}{\"\\n\"}{.status.message}{\"\\n\"}'",
                "phase / reason / message $POD",
            ),
            (
                "kubectl get pods -n $NS -o custom-columns="
                "NAME:.metadata.name,RESTARTS:.status.containerStatuses[*].restartCount,"
                "NODE:.spec.nodeName,IP:.status.podIP",
                "restarts / node / IP (сводка)",
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
            ("kubectl events -n $NS --types=Warning", "kubectl events: Warning (1.23+)"),
            ("kubectl events -n $NS --for pod/$POD", "kubectl events по $POD"),
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
    "kres": (
        "квоты / лимиты / свободные ресурсы",
        [
            ("kubectl get resourcequotas -n $NS", "список ResourceQuota"),
            (
                "kubectl describe resourcequota compute-resources -n $NS",
                "describe compute-resources",
            ),
            ("kubectl describe resourcequota $QUOTA -n $NS", "describe $QUOTA"),
            ("kubectl get resourcequota -n $NS -o json", "json всех quota → F5 / kjq"),
            (
                "kubectl get resourcequota compute-resources -n $NS -o json",
                "json compute-resources",
            ),
            ("kubectl get limitrange -n $NS", "LimitRange в $NS"),
            ("kubectl get limitrange -n $NS -o yaml", "LimitRange yaml"),
            ("kubectl top node", "метрики нод (metrics-server)"),
            (
                "kubectl get nodes -o custom-columns="
                "NAME:.metadata.name,CPU:.status.allocatable.cpu,"
                "MEM:.status.allocatable.memory,PODS:.status.allocatable.pods",
                "allocatable CPU/MEM/pods на нодах",
            ),
            (
                "kubectl get events -n $NS --sort-by=.lastTimestamp "
                "| grep -iE 'quota|exceeded|Forbidden|limit'",
                "events про quota/limit",
            ),
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
            (
                "jq '[((.items) // [.])[] | .metadata.name as $n "
                "| (.status.hard // {}) as $h | (.status.used // {}) as $u "
                "| $h | to_entries[] "
                "| {quota:$n, resource:.key, hard:.value, used:($u[.key] // \"0\")}]'",
                "quota used vs hard (list или один объект)",
            ),
        ],
    ),
    "kavail": (
        "HPA / PDB: масштабирование и disruption",
        [
            ("kubectl get hpa -n $NS -o wide", "HPA: текущие/целевые метрики"),
            ("kubectl describe hpa -n $NS", "describe HPA в $NS"),
            ("kubectl get pdb -n $NS", "PDB: disruptions allowed"),
            ("kubectl describe pdb -n $NS", "describe PDB в $NS"),
            ("kubectl get pdb -n $NS -o json", "json PDB → F5"),
        ],
    ),
    "kstore": (
        "PVC / PV: тома",
        [
            ("kubectl get pvc -n $NS", "PVC в $NS"),
            ("kubectl get pvc -n $NS -o wide", "PVC: volume / storageclass"),
            ("kubectl describe pvc -n $NS", "describe PVC (Pending?)"),
            ("kubectl get pvc -n $NS -o json", "json PVC → F5"),
            ("kubectl get pv -o wide", "PV: статус/claim (кластер)"),
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
    "kquota": (
        "ResourceQuota + LimitRange + ноды",
        [
            (
                "!kres[1] ; echo '--- compute-resources ---' ; !kres[2] ; "
                "echo '--- json ---' ; !kres[4] ; echo '--- limitrange ---' ; !kres[6] ; "
                "echo '--- top node ---' ; !kres[8] ; echo '--- quota events ---' ; !kres[10]",
                "квоты / лимиты / allocatable",
            ),
        ],
    ),
    "kscale": (
        "HPA / PDB / метрики при нагрузке",
        [
            (
                "!kavail[1] ; echo '--- pdb ---' ; !kavail[3] ; "
                "echo '--- metrics ---' ; !kpod[7] ; echo '--- events ---' ; !kev[3]",
                "не масштабируется / disruption",
            ),
        ],
    ),
    "kvolume": (
        "PVC / PV / events — том не привязан",
        [
            (
                "!kstore[1] ; echo '--- describe ---' ; !kstore[3] ; "
                "echo '--- pv ---' ; !kstore[5] ; echo '--- events ---' ; !kev[3]",
                "Pending / нет тома",
            ),
        ],
    ),
    "kdns": (
        "DNS: dnsPolicy, resolv.conf, endpoints",
        [
            (
                "kubectl get pod $POD -n $NS -o jsonpath="
                "'{.spec.dnsPolicy}{\"\\n\"}{.spec.dnsConfig}{\"\\n\"}'",
                "dnsPolicy / dnsConfig пода",
            ),
            (
                "kubectl exec $POD -n $NS -- cat /etc/resolv.conf",
                "resolv.conf внутри пода (read-only)",
            ),
            ("kubectl get endpoints $SVC -n $NS -o yaml", "Endpoints: IP и порты $SVC"),
            (
                "kubectl get endpointslice -n $NS -l kubernetes.io/service-name=$SVC -o wide",
                "EndpointSlice $SVC",
            ),
            (
                "kubectl get pods -n kube-system -l k8s-app=kube-dns -o wide",
                "поды CoreDNS",
            ),
            ("kubectl get svc kube-dns -n kube-system -o wide", "сервис CoreDNS"),
        ],
    ),
    "krbac": (
        "RBAC: что можно токену / ServiceAccount",
        [
            ("kubectl auth can-i get pods -n $NS", "читать поды?"),
            ("kubectl auth can-i create deployments -n $NS", "создавать deployments?"),
            ("kubectl auth can-i get secrets -n $NS", "читать secrets?"),
            ("kubectl get sa -n $NS", "ServiceAccount в $NS"),
            (
                "kubectl auth can-i get pods -n $NS --as=system:serviceaccount:$NS:$SA",
                "права SA $SA (impersonation)",
            ),
            (
                "kubectl auth can-i --list -n $NS --as=system:serviceaccount:$NS:$SA",
                "полный список прав SA $SA",
            ),
            ("kubectl describe sa $SA -n $NS", "describe SA $SA"),
        ],
    ),
}


# Разметка канонических тегов (машинные токены, не переводятся; см. :tagmeta).
SEED_METADATA = {
    "kns": {
        "risk": "low",
        "utilities": ["kubectl"],
        "os": ["linux", "macos", "windows"],
        "interactive": False,
        "topic": "inspect",
        "example": "kubectl config current-context",
    },
    "kpod": {
        "risk": "low",
        "utilities": ["kubectl"],
        "os": ["linux", "macos", "windows"],
        "interactive": False,
        "topic": "inspect",
        "example": "kubectl get pods -n $NS -o wide",
    },
    "klog": {
        "risk": "low",
        "utilities": ["kubectl"],
        "os": ["linux", "macos", "windows"],
        "interactive": False,
        "topic": "logs",
        "example": "kubectl logs $POD -n $NS --tail=200",
    },
    "kdns": {
        "risk": "low",
        "utilities": ["kubectl"],
        "os": ["linux", "macos", "windows"],
        "interactive": False,
        "topic": "network",
        "example": "kubectl get pod $POD -n $NS -o jsonpath='{.spec.dnsPolicy}'",
    },
    "krbac": {
        "risk": "low",
        "utilities": ["kubectl"],
        "os": ["linux", "macos", "windows"],
        "interactive": False,
        "topic": "rbac",
        "example": "kubectl auth can-i get pods -n $NS",
    },
}


def run_seed(db_file: str) -> int:
    """Replace investigation tags; return number of commands inserted."""
    return _run_seed(db_file, SEED_TAGS, label="k8s", metadata=SEED_METADATA)


def main() -> None:
    seed_cli(
        description="Seed IDvjPy_term DB with k8s investigation chains (K8S_CHAINS.md)",
        seed_help="Replace kns/kpod/kres/kquota/… tags (does not touch proc/file/net/kube)",
        seed_tags=SEED_TAGS,
        argv=sys.argv,
        label="k8s",
    )


if __name__ == "__main__":
    main()
