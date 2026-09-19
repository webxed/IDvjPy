# k8s 排查命令链 —— 规范 tid

概览与排查流程：[`K8S_CHAINS.md`](K8S_CHAINS.md)。以下是工作标签的固定 tid。

种子标签 `kube`（`seed_linux_commands.py`）是通用手册。  
本种子提供**工作**标签，带 `$NS`、`$POD`、`$DEPLOY`、`$SVC`、`$ING`、`$APP`、`$CTR`、`$QUOTA`。

```bash
python3 src/seed_k8s_chains.py --seed
```

不会改动 `proc` / `file` / `net` / `kube`。重复 `--seed` 只重写
`kvars` `kns` `kpod` `klog` `kev` `ksvc` `king` `kdep` `kres` `kjq`
`kavail` `kstore`
`kcrash` `knet` `kroll` `kwatch` `kquota` `kscale` `kvolume`。

`kubectl logs -f` / `exec -it` / `port-forward` —— 带 `>` 前缀（真正的 TTY）。  
`delete` / `rollout restart` / `undo` —— 不在运行手册中。

TUI 中的流程：`$NS=…` → 宽泛 `get` → F2 复制名称 → `$POD=` → 窄标签。  
JSON：`-o json` → F5。组装：`!! kcrash[1]`。

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

`$NS` 也会设置 `:i list -n my-ns`。

---

## kvars (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `echo ns=$NS pod=$POD … quota=$QUOTA` | 检查变量 |

---

## kns — 集群 / namespace (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `kubectl config current-context` | 当前 context |
| 2 | `kubectl config get-contexts` | 所有 context |
| 3 | `kubectl get ns` | namespace 列表 |
| 4 | `kubectl get ns $NS -o yaml` | YAML `$NS` |
| 5 | `kubectl api-resources --namespaced=true --verbs=list` | 命名空间级 API |
| 6 | `kubectl get nodes -o wide` | 节点 wide（版本/OS/地址） |
| 7 | `kubectl auth can-i --list -n $NS` | 我在 `$NS` 中的权限 |

---

## kpod — Pod (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `kubectl get pods -n $NS -o wide` | 所有 Pod |
| 2 | `kubectl get pods -n $NS --field-selector=status.phase!=Running` | 非 Running |
| 3 | `kubectl get pods -n $NS -l app=$APP -o wide` | `$APP` 的 Pod |
| 4 | `kubectl describe pod $POD -n $NS` | Describe `$POD` |
| 5 | `kubectl get pod $POD -n $NS -o json` | JSON → F5 |
| 6 | jsonpath containerStatuses name/state/lastState | 容器状态 |
| 7 | `kubectl top pod -n $NS` | Pod 指标 |
| 8 | jsonpath nodeName / podIP / hostIP | 节点与 IP |
| 9 | jsonpath phase / reason / message | Pod 为何非 Running（`Pending`、`FailedScheduling`） |
| 10 | custom-columns NAME / RESTARTS / NODE / IP | 含重启次数的概览 |

---

## klog — 不带 follow 的日志 (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `kubectl logs $POD -n $NS --tail=200` | `$POD` 的日志 |
| 2 | `kubectl logs $POD -n $NS -c $CTR --tail=200` | 容器 `$CTR` |
| 3 | `kubectl logs $POD -n $NS --previous --tail=200` | Previous |
| 4 | `kubectl logs -n $NS -l app=$APP --tail=100 --max-log-requests=10` | `$APP` 的日志 |
| 5 | `kubectl logs … \| grep -iE 'error\|exception\|fatal\|panic\|oom'` | 搜索错误 |

```text
> kubectl logs -f $POD -n $NS --tail=50
> kubectl exec -it $POD -n $NS -- sh
```

---

## kev — events (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `kubectl get events -n $NS --sort-by=.lastTimestamp` | 所有 events |
| 2 | `kubectl get events -n $NS --field-selector involvedObject.name=$POD` | `$POD` 的 events |
| 3 | `kubectl get events -n $NS --field-selector type=Warning …` | Warning |
| 4 | `kubectl events -n $NS --types=Warning` | `kubectl events`（1.23+），Warning |
| 5 | `kubectl events -n $NS --for pod/$POD` | `kubectl events` 按 `$POD` |

---

## ksvc — Service / endpoints (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `kubectl get svc,ep -n $NS` | Svc + endpoints |
| 2 | `kubectl describe svc $SVC -n $NS` | Describe `$SVC` |
| 3 | `kubectl get endpoints $SVC -n $NS -o yaml` | Endpoints YAML |
| 4 | `kubectl get endpointslice -n $NS -l kubernetes.io/service-name=$SVC` | EndpointSlice |
| 5 | `kubectl get networkpolicy -n $NS` | NetworkPolicy |

---

## king — Ingress (tid)

TUI 中相邻：`:i list -n $NS`、`:i analyze $ING`、`:i check $SVC`。

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `kubectl get ingress -n $NS -o wide` | 列表 |
| 2 | `kubectl describe ingress $ING -n $NS` | Describe `$ING` |
| 3 | `kubectl get ingress $ING -n $NS -o json` | JSON → F5 |

---

## kdep — deploy / rollout (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `kubectl get deploy,rs,sts,ds -n $NS` | Workload |
| 2 | `kubectl describe deploy $DEPLOY -n $NS` | Describe `$DEPLOY` |
| 3 | `kubectl get deploy $DEPLOY -n $NS -o json` | JSON → F5 |
| 4 | `kubectl rollout status deploy/$DEPLOY -n $NS` | 状态 |
| 5 | `kubectl rollout history deploy/$DEPLOY -n $NS` | 历史 |
| 6 | `kubectl get rs -n $NS -l app=$APP -o wide` | ReplicaSet `$APP` |

手动重启：`kubectl rollout restart deploy/$DEPLOY -n $NS`。

---

## kres — 配额 / 限制 / 节点 (tid)

`top node` 需要 metrics-server。若配额名不是 `compute-resources` —— `$QUOTA=…` 并 `!! kres[3]`。

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `kubectl get resourcequotas -n $NS` | quota 列表 |
| 2 | `kubectl describe resourcequota compute-resources -n $NS` | Describe compute-resources |
| 3 | `kubectl describe resourcequota $QUOTA -n $NS` | Describe `$QUOTA` |
| 4 | `kubectl get resourcequota -n $NS -o json` | 全部 JSON → F5 / kjq |
| 5 | `kubectl get resourcequota compute-resources -n $NS -o json` | JSON compute-resources |
| 6 | `kubectl get limitrange -n $NS` | LimitRange |
| 7 | `kubectl get limitrange -n $NS -o yaml` | LimitRange YAML |
| 8 | `kubectl top node` | 节点指标 |
| 9 | `kubectl get nodes -o custom-columns=…allocatable…` | 可分配 CPU/MEM/pods |
| 10 | events grep `quota\|exceeded\|Forbidden\|limit` | 关于 quota 的 events |

---

## kjq — 对块 stdout 使用 jq (tid)

来自 JSON 块的管道：`|` + `!kjq[N]`。

| tid | 用途 |
|-----|------------|
| 1 | Pod：name / phase / restarts / ready |
| 2 | containerStatuses：state / lastState |
| 3 | `.status.conditions` |
| 4 | containers：image / resources / ports |
| 5 | 来自 endpoints 的 IP |
| 6 | ingress 规则：host / paths / svc |
| 7 | quota 已用与硬上限（列表或单个对象） |

```text
!! kpod[1] | kjq[1]
!! kpod[5] | kjq[2]
!! kres[4] | kjq[7]
```

---

## kavail — HPA / PDB (tid)

扩缩容与 disruption（drain/evictions）防护。

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `kubectl get hpa -n $NS -o wide` | HPA：当前/目标指标 |
| 2 | `kubectl describe hpa -n $NS` | Describe `$NS` 中的 HPA（`-l app=$APP` —— 窄） |
| 3 | `kubectl get pdb -n $NS` | PDB：disruptions allowed |
| 4 | `kubectl describe pdb -n $NS` | Describe PDB |
| 5 | `kubectl get pdb -n $NS -o json` | JSON → F5 |

---

## kstore — PVC / PV (tid)

卡住的 Pod 常常在等卷（`Pending` → 缺少 PVC/StorageClass/绑定）。

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `kubectl get pvc -n $NS` | `$NS` 中的 PVC |
| 2 | `kubectl get pvc -n $NS -o wide` | PVC：volume / storageclass |
| 3 | `kubectl describe pvc -n $NS` | Describe PVC（Pending？） |
| 4 | `kubectl get pvc -n $NS -o json` | JSON → F5 |
| 5 | `kubectl get pv -o wide` | PV：状态/claim（集群） |

---

## 运行手册

| 标签 | 命令链 | 原因 |
|-----|---------|--------|
| `kcrash[1]` | kpod[2] → kpod[4] → klog[3] → kev[2] | CrashLoop / ImagePull / OOM |
| `knet[1]` | ksvc[1,2,3] → kpod[3] | 0 endpoints / 无流量 |
| `kroll[1]` | kdep[2,4,6] → kpod[2] | Rollout 卡住 |
| `kwatch[1]` | kpod[1,2] → kev[3] | `$NS` 中发生了什么 |
| `kquota[1]` | kres[1,2,4,6,8,10] | 配额 / 限制 / allocatable |
| `kscale[1]` | kavail[1,3] → kpod[7] → kev[3] | HPA/PDB：不扩缩容 / disruption |
| `kvolume[1]` | kstore[1,3,5] → kev[3] | Pending / 卷未绑定 |

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

## 症状 → 命令链

| 症状 | 变量 | 命令链 |
|---------|------------|---------|
| CrashLoopBackOff | `$NS`, `$POD` | `!! kcrash[1]` 然后 `!! klog[1]` |
| ImagePullBackOff | `$NS`, `$POD` | `!! kpod[4]` ; `!! kev[2]` |
| Pending / FailedScheduling | `$NS`, `$POD` | `!! kpod[4]` ; `!! kev[3]` ; quota —— `!! kquota[1]` |
| Exceeded quota | `$NS`, `$QUOTA` | `!! kquota[1]` 然后 `!! kres[4] \| kjq[7]` |
| 0 endpoints | `$NS`, `$SVC`, `$APP` | `!! knet[1]` |
| 5xx 来自外部 | `$NS`, `$ING`, `$SVC` | `:i analyze` + `!! king[2]` |
| Rollout 0/1 | `$NS`, `$DEPLOY`, `$APP` | `!! kroll[1]` |
| OOMKilled | `$NS`, `$POD` | `!! kpod[5]` → F5 `.resources` |
| ns 中的噪声 | `$NS` | `!! kwatch[1]` + `:/error` |
| HPA 不扩缩容 | `$NS`, `$APP` | `!! kscale[1]` (`!kavail[1]`, `!kpod[7]`) |
| Pod Pending：无卷 | `$NS`, `$POD` | `!! kvolume[1]` (`!kstore[1,3]`) |
| Forbidden / 无权限 | `$NS` | `!kns[7]` (`auth can-i --list`) ; `!kns[1]` |
| Drain/evict 卡住 | `$NS` | `!kavail[3]` ; `!kavail[4]` |
