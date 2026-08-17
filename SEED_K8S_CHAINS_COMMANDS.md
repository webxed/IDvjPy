# Справочник k8s investigation chains для IDvjPy

Обзор и цикл расследования: [`K8S_CHAINS.md`](K8S_CHAINS.md). Ниже — канонические tid.

Сидовый тег `kube` (`seed_linux_commands.py`) — общий справочник.  
Этот сид — **рабочие** теги с `$NS`, `$POD`, `$DEPLOY`, `$SVC`, `$ING`, `$APP`, `$CTR`, `$QUOTA`.

```bash
python3 src/seed_k8s_chains.py --seed
```

Не трогает `proc` / `file` / `net` / `kube`. Повторный `--seed` перезаписывает только
`kvars` `kns` `kpod` `klog` `kev` `ksvc` `king` `kdep` `kres` `kjq`
`kcrash` `knet` `kroll` `kwatch` `kquota`.

`kubectl logs -f` / `exec -it` / `port-forward` — с префиксом `>` (настоящий TTY).  
`delete` / `rollout restart` / `undo` — не в плейбуках.

Цикл в TUI: `$NS=…` → широкий `get` → F2 копирует имя → `$POD=` → узкий тег.  
JSON: `-o json` → F5. Сборка: `!! kcrash[1]`.

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

`$NS` также ставит `:i list -n my-ns`.

---

## kvars (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `echo ns=$NS pod=$POD … quota=$QUOTA` | Проверка переменных |

---

## kns — кластер / namespace (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `kubectl config current-context` | Текущий context |
| 2 | `kubectl config get-contexts` | Все context |
| 3 | `kubectl get ns` | Список namespace |
| 4 | `kubectl get ns $NS -o yaml` | YAML `$NS` |
| 5 | `kubectl api-resources --namespaced=true --verbs=list` | Namespaced API |

---

## kpod — поды (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `kubectl get pods -n $NS -o wide` | Все поды |
| 2 | `kubectl get pods -n $NS --field-selector=status.phase!=Running` | Не Running |
| 3 | `kubectl get pods -n $NS -l app=$APP -o wide` | Поды `$APP` |
| 4 | `kubectl describe pod $POD -n $NS` | Describe `$POD` |
| 5 | `kubectl get pod $POD -n $NS -o json` | JSON → F5 |
| 6 | jsonpath containerStatuses name/state/lastState | State контейнеров |
| 7 | `kubectl top pod -n $NS` | Метрики подов |
| 8 | jsonpath nodeName / podIP / hostIP | Нода и IP |

---

## klog — логи без follow (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `kubectl logs $POD -n $NS --tail=200` | Логи `$POD` |
| 2 | `kubectl logs $POD -n $NS -c $CTR --tail=200` | Контейнер `$CTR` |
| 3 | `kubectl logs $POD -n $NS --previous --tail=200` | Previous |
| 4 | `kubectl logs -n $NS -l app=$APP --tail=100 --max-log-requests=10` | Логи `$APP` |
| 5 | `kubectl logs … \| grep -iE 'error\|exception\|fatal\|panic\|oom'` | Grep ошибок |

```text
> kubectl logs -f $POD -n $NS --tail=50
> kubectl exec -it $POD -n $NS -- sh
```

---

## kev — events (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `kubectl get events -n $NS --sort-by=.lastTimestamp` | Все events |
| 2 | `kubectl get events -n $NS --field-selector involvedObject.name=$POD` | Events `$POD` |
| 3 | `kubectl get events -n $NS --field-selector type=Warning …` | Warning |

---

## ksvc — Service / endpoints (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `kubectl get svc,ep -n $NS` | Svc + endpoints |
| 2 | `kubectl describe svc $SVC -n $NS` | Describe `$SVC` |
| 3 | `kubectl get endpoints $SVC -n $NS -o yaml` | Endpoints YAML |
| 4 | `kubectl get endpointslice -n $NS -l kubernetes.io/service-name=$SVC` | EndpointSlice |
| 5 | `kubectl get networkpolicy -n $NS` | NetworkPolicy |

---

## king — Ingress (tid)

Рядом в TUI: `:i list -n $NS`, `:i analyze $ING`, `:i check $SVC`.

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `kubectl get ingress -n $NS -o wide` | Список |
| 2 | `kubectl describe ingress $ING -n $NS` | Describe `$ING` |
| 3 | `kubectl get ingress $ING -n $NS -o json` | JSON → F5 |

---

## kdep — deploy / rollout (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `kubectl get deploy,rs,sts,ds -n $NS` | Workload |
| 2 | `kubectl describe deploy $DEPLOY -n $NS` | Describe `$DEPLOY` |
| 3 | `kubectl get deploy $DEPLOY -n $NS -o json` | JSON → F5 |
| 4 | `kubectl rollout status deploy/$DEPLOY -n $NS` | Status |
| 5 | `kubectl rollout history deploy/$DEPLOY -n $NS` | History |
| 6 | `kubectl get rs -n $NS -l app=$APP -o wide` | ReplicaSet `$APP` |

Рестарт руками: `kubectl rollout restart deploy/$DEPLOY -n $NS`.

---

## kres — квоты / лимиты / ноды (tid)

`top node` нужен metrics-server. Имя квоты не `compute-resources` — `$QUOTA=…` и `!! kres[3]`.

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `kubectl get resourcequotas -n $NS` | Список quota |
| 2 | `kubectl describe resourcequota compute-resources -n $NS` | Describe compute-resources |
| 3 | `kubectl describe resourcequota $QUOTA -n $NS` | Describe `$QUOTA` |
| 4 | `kubectl get resourcequota -n $NS -o json` | JSON всех → F5 / kjq |
| 5 | `kubectl get resourcequota compute-resources -n $NS -o json` | JSON compute-resources |
| 6 | `kubectl get limitrange -n $NS` | LimitRange |
| 7 | `kubectl get limitrange -n $NS -o yaml` | LimitRange YAML |
| 8 | `kubectl top node` | Метрики нод |
| 9 | `kubectl get nodes -o custom-columns=…allocatable…` | Allocatable CPU/MEM/pods |
| 10 | events grep `quota\|exceeded\|Forbidden\|limit` | Events про quota |

---

## kjq — jq к stdout блока (tid)

Пайп от JSON-блока: `|` + `!kjq[N]`.

| tid | Назначение |
|-----|------------|
| 1 | Поды: name / phase / restarts / ready |
| 2 | containerStatuses: state / lastState |
| 3 | `.status.conditions` |
| 4 | containers: image / resources / ports |
| 5 | IP из endpoints |
| 6 | Правила ingress: host / paths / svc |
| 7 | Quota used vs hard (list или один объект) |

```text
!! kpod[1] | kjq[1]
!! kpod[5] | kjq[2]
!! kres[4] | kjq[7]
```

---

## Плейбуки

| Тег | Цепочка | Зачем |
|-----|---------|--------|
| `kcrash[1]` | kpod[2] → kpod[4] → klog[3] → kev[2] | CrashLoop / ImagePull / OOM |
| `knet[1]` | ksvc[1,2,3] → kpod[3] | 0 endpoints / нет трафика |
| `kroll[1]` | kdep[2,4,6] → kpod[2] | Rollout застрял |
| `kwatch[1]` | kpod[1,2] → kev[3] | Что случилось в `$NS` |
| `kquota[1]` | kres[1,2,4,6,8,10] | Квоты / лимиты / allocatable |

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

## Симптом → цепочка

| Симптом | Переменные | Цепочка |
|---------|------------|---------|
| CrashLoopBackOff | `$NS`, `$POD` | `!! kcrash[1]` затем `!! klog[1]` |
| ImagePullBackOff | `$NS`, `$POD` | `!! kpod[4]` ; `!! kev[2]` |
| Pending / FailedScheduling | `$NS`, `$POD` | `!! kpod[4]` ; `!! kev[3]` ; quota — `!! kquota[1]` |
| Exceeded quota | `$NS`, `$QUOTA` | `!! kquota[1]` затем `!! kres[4] \| kjq[7]` |
| 0 endpoints | `$NS`, `$SVC`, `$APP` | `!! knet[1]` |
| 5xx снаружи | `$NS`, `$ING`, `$SVC` | `:i analyze` + `!! king[2]` |
| Rollout 0/1 | `$NS`, `$DEPLOY`, `$APP` | `!! kroll[1]` |
| OOMKilled | `$NS`, `$POD` | `!! kpod[5]` → F5 `.resources` |
| Шум в ns | `$NS` | `!! kwatch[1]` + `:/error` |
