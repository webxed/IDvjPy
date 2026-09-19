# k8s investigation chains — canonical tids

Overview and investigation cycle: [`K8S_CHAINS.md`](K8S_CHAINS.md). Below are the fixed tids of the working tags.

The seed tag `kube` (`seed_linux_commands.py`) is a general handbook.  
This seed provides **working** tags with `$NS`, `$POD`, `$DEPLOY`, `$SVC`, `$ING`, `$APP`, `$CTR`, `$QUOTA`.

```bash
python3 src/seed_k8s_chains.py --seed
```

Does not touch `proc` / `file` / `net` / `kube`. A repeated `--seed` overwrites only
`kvars` `kns` `kpod` `klog` `kev` `ksvc` `king` `kdep` `kres` `kjq`
`kavail` `kstore`
`kcrash` `knet` `kroll` `kwatch` `kquota` `kscale` `kvolume`.

`kubectl logs -f` / `exec -it` / `port-forward` — with the `>` prefix (real TTY).  
`delete` / `rollout restart` / `undo` — not in playbooks.

Cycle in the TUI: `$NS=…` → wide `get` → F2 copies the name → `$POD=` → narrow tag.  
JSON: `-o json` → F5. Assembly: `!! kcrash[1]`.

```text
$NS=default
$APP=api
$DEPLOY=api
$SVC=api
$ING=api
$POD=
$CTR=
$QUOTA=compute-resources
!! kvars[1]
```

`$NS` also drives `:i list -n my-ns`.

---

## kvars (tid)

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `echo ns=$NS pod=$POD … quota=$QUOTA` | check variables |

---

## kns — cluster / namespace (tid)

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `kubectl config current-context` | current context |
| 2 | `kubectl config get-contexts` | all contexts |
| 3 | `kubectl get ns` | list namespaces |
| 4 | `kubectl get ns $NS -o yaml` | YAML `$NS` |
| 5 | `kubectl api-resources --namespaced=true --verbs=list` | Namespaced API |
| 6 | `kubectl get nodes -o wide` | nodes wide (version/OS/addresses) |
| 7 | `kubectl auth can-i --list -n $NS` | my permissions in `$NS` |

---

## kpod — pods (tid)

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `kubectl get pods -n $NS -o wide` | all pods wide |
| 2 | `kubectl get pods -n $NS --field-selector=status.phase!=Running` | not Running |
| 3 | `kubectl get pods -n $NS -l app=$APP -o wide` | pods `$APP` |
| 4 | `kubectl describe pod $POD -n $NS` | describe `$POD` |
| 5 | `kubectl get pod $POD -n $NS -o json` | JSON → F5 |
| 6 | jsonpath containerStatuses name/state/lastState | container states |
| 7 | `kubectl top pod -n $NS` | pod metrics |
| 8 | jsonpath nodeName / podIP / hostIP | node and IP |
| 9 | jsonpath phase / reason / message | why the pod is not Running (`Pending`, `FailedScheduling`) |
| 10 | custom-columns NAME / RESTARTS / NODE / IP | summary with restarts |

---

## klog — logs without follow (tid)

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `kubectl logs $POD -n $NS --tail=200` | logs `$POD` |
| 2 | `kubectl logs $POD -n $NS -c $CTR --tail=200` | container `$CTR` |
| 3 | `kubectl logs $POD -n $NS --previous --tail=200` | previous |
| 4 | `kubectl logs -n $NS -l app=$APP --tail=100 --max-log-requests=10` | logs `$APP` |
| 5 | `kubectl logs … \| grep -iE 'error\|exception\|fatal\|panic\|oom'` | grep for errors |

```text
> kubectl logs -f $POD -n $NS --tail=50
> kubectl exec -it $POD -n $NS -- sh
```

---

## kev — events (tid)

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `kubectl get events -n $NS --sort-by=.lastTimestamp` | all events |
| 2 | `kubectl get events -n $NS --field-selector involvedObject.name=$POD` | events `$POD` |
| 3 | `kubectl get events -n $NS --field-selector type=Warning …` | Warning |
| 4 | `kubectl events -n $NS --types=Warning` | `kubectl events` (1.23+), Warning |
| 5 | `kubectl events -n $NS --for pod/$POD` | `kubectl events` for `$POD` |

---

## ksvc — Service / endpoints (tid)

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `kubectl get svc,ep -n $NS` | Svc + endpoints |
| 2 | `kubectl describe svc $SVC -n $NS` | describe `$SVC` |
| 3 | `kubectl get endpoints $SVC -n $NS -o yaml` | Endpoints YAML |
| 4 | `kubectl get endpointslice -n $NS -l kubernetes.io/service-name=$SVC` | EndpointSlice |
| 5 | `kubectl get networkpolicy -n $NS` | NetworkPolicy |

---

## king — Ingress (tid)

Nearby in the TUI: `:i list -n $NS`, `:i analyze $ING`, `:i check $SVC`.

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `kubectl get ingress -n $NS -o wide` | list |
| 2 | `kubectl describe ingress $ING -n $NS` | describe `$ING` |
| 3 | `kubectl get ingress $ING -n $NS -o json` | JSON → F5 |

---

## kdep — deploy / rollout (tid)

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `kubectl get deploy,rs,sts,ds -n $NS` | workload |
| 2 | `kubectl describe deploy $DEPLOY -n $NS` | describe `$DEPLOY` |
| 3 | `kubectl get deploy $DEPLOY -n $NS -o json` | JSON → F5 |
| 4 | `kubectl rollout status deploy/$DEPLOY -n $NS` | status |
| 5 | `kubectl rollout history deploy/$DEPLOY -n $NS` | history |
| 6 | `kubectl get rs -n $NS -l app=$APP -o wide` | ReplicaSet `$APP` |

Manual restart: `kubectl rollout restart deploy/$DEPLOY -n $NS`.

---

## kres — quotas / limits / nodes (tid)

`top node` needs metrics-server. If the quota name is not `compute-resources` — `$QUOTA=…` and `!! kres[3]`.

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `kubectl get resourcequotas -n $NS` | list quota |
| 2 | `kubectl describe resourcequota compute-resources -n $NS` | describe compute-resources |
| 3 | `kubectl describe resourcequota $QUOTA -n $NS` | describe `$QUOTA` |
| 4 | `kubectl get resourcequota -n $NS -o json` | JSON of all → F5 / kjq |
| 5 | `kubectl get resourcequota compute-resources -n $NS -o json` | JSON compute-resources |
| 6 | `kubectl get limitrange -n $NS` | LimitRange |
| 7 | `kubectl get limitrange -n $NS -o yaml` | LimitRange YAML |
| 8 | `kubectl top node` | node metrics |
| 9 | `kubectl get nodes -o custom-columns=…allocatable…` | allocatable CPU/MEM/pods |
| 10 | events grep `quota\|exceeded\|Forbidden\|limit` | events about quota |

---

## kjq — jq on block stdout (tid)

Pipe from a JSON block: `|` + `!kjq[N]`.

| tid | Purpose |
|-----|------------|
| 1 | Pods: name / phase / restarts / ready |
| 2 | containerStatuses: state / lastState |
| 3 | `.status.conditions` |
| 4 | containers: image / resources / ports |
| 5 | IP from endpoints |
| 6 | ingress rules: host / paths / svc |
| 7 | quota used vs hard (list or single object) |

```text
!! kpod[1] | kjq[1]
!! kpod[5] | kjq[2]
!! kres[4] | kjq[7]
```

---

## kavail — HPA / PDB (tid)

Scaling and protection from disruption (drain/evictions).

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `kubectl get hpa -n $NS -o wide` | HPA: current/target metrics |
| 2 | `kubectl describe hpa -n $NS` | describe HPA in `$NS` (`-l app=$APP` — narrow) |
| 3 | `kubectl get pdb -n $NS` | PDB: disruptions allowed |
| 4 | `kubectl describe pdb -n $NS` | describe PDB |
| 5 | `kubectl get pdb -n $NS -o json` | JSON → F5 |

---

## kstore — PVC / PV (tid)

A stuck Pod often waits for a volume (`Pending` → no PVC/StorageClass/binding).

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `kubectl get pvc -n $NS` | PVC in `$NS` |
| 2 | `kubectl get pvc -n $NS -o wide` | PVC: volume / storageclass |
| 3 | `kubectl describe pvc -n $NS` | describe PVC (Pending?) |
| 4 | `kubectl get pvc -n $NS -o json` | JSON → F5 |
| 5 | `kubectl get pv -o wide` | PV: status/claim (cluster) |

---

## Playbooks

| Tag | Chain | Why |
|-----|---------|--------|
| `kcrash[1]` | kpod[2] → kpod[4] → klog[3] → kev[2] | CrashLoop / ImagePull / OOM |
| `knet[1]` | ksvc[1,2,3] → kpod[3] | 0 endpoints / no traffic |
| `kroll[1]` | kdep[2,4,6] → kpod[2] | rollout stuck |
| `kwatch[1]` | kpod[1,2] → kev[3] | what happened in `$NS` |
| `kquota[1]` | kres[1,2,4,6,8,10] | quotas / limits / allocatable |
| `kscale[1]` | kavail[1,3] → kpod[7] → kev[3] | HPA/PDB: not scaling / disruption |
| `kvolume[1]` | kstore[1,3,5] → kev[3] | Pending / volume not bound |

```text
$NS=my-ns
!! kpod[2]
$POD=api-7f8c9
!! kcrash[1]
$QUOTA=compute-resources
!! kquota[1]
!! kres[4] | kjq[7]
```

---

## Symptom → chain

| Symptom | Variables | Chain |
|---------|------------|---------|
| CrashLoopBackOff | `$NS`, `$POD` | `!! kcrash[1]` then `!! klog[1]` |
| ImagePullBackOff | `$NS`, `$POD` | `!! kpod[4]` ; `!! kev[2]` |
| Pending / FailedScheduling | `$NS`, `$POD` | `!! kpod[4]` ; `!! kev[3]` ; quota — `!! kquota[1]` |
| Exceeded quota | `$NS`, `$QUOTA` | `!! kquota[1]` then `!! kres[4] \| kjq[7]` |
| 0 endpoints | `$NS`, `$SVC`, `$APP` | `!! knet[1]` |
| 5xx from outside | `$NS`, `$ING`, `$SVC` | `:i analyze` + `!! king[2]` |
| Rollout 0/1 | `$NS`, `$DEPLOY`, `$APP` | `!! kroll[1]` |
| OOMKilled | `$NS`, `$POD` | `!! kpod[5]` → F5 `.resources` |
| Noise in the ns | `$NS` | `!! kwatch[1]` + `:/error` |
| HPA not scaling | `$NS`, `$APP` | `!! kscale[1]` (`!kavail[1]`, `!kpod[7]`) |
| Pod Pending: no volume | `$NS`, `$POD` | `!! kvolume[1]` (`!kstore[1,3]`) |
| Forbidden / no permissions | `$NS` | `!kns[7]` (`auth can-i --list`) ; `!kns[1]` |
| Drain/evict stuck | `$NS` | `!kavail[3]` ; `!kavail[4]` |
