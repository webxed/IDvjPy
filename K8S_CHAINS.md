# Цепочки kubectl для расследования (IDvjPy)

Сидовый тег `kube` — справочник (`POD`, `DEPLOY` как текст). Ниже — **рабочие** теги: плейсхолдеры только через `$NS`, `$POD`, `$DEPLOY`, `$SVC`, `$ING`, `$APP`, `$CTR`.

Набить БД (не трогает `proc` / `file` / `net` / `kube`):

```bash
python3 seed_k8s_chains.py --seed
```

Повторный `--seed` перезаписывает только теги `kvars`, `kns`, `kpod`, `klog`, `kev`, `ksvc`, `king`, `kdep`, `kjq`, `kcrash`, `knet`, `kroll`, `kwatch` (tid с 1). Ручные правки этих тегов будут стёрты.

Цикл в TUI:

1. Выставить namespace: `$NS=my-ns`
2. Широкий `get` → блок в журнале
3. `Tab` / клик → `F2` → Enter копирует имя (`api-7f8c9`) → `$POD=` + вставка
4. Узкий тег (`describe` / `logs` / `events`) — уже с `$POD`
5. JSON: `-o json` → `F5` → Enter на узле → `| jq '…'` или `jq $JSON`

`kubectl logs -f` и `exec -it` — только с префиксом `>` (настоящий TTY).

Ссылки в `#pipeline …` **не** раскрываются при сохранении. Сборка: `!! kcrash[1]` или `!! kpod[1] ; kpod[4]`.

---

## 0. Переменные (один раз за инцидент)

```text
$NS=default
$APP=api
$DEPLOY=api
$SVC=api
$ING=api
$POD=
$CTR=
```

`$NS` также ставит `:i list -n my-ns`.

Проверка: `echo ns=$NS pod=$POD deploy=$DEPLOY svc=$SVC`.

---

## 1. Набить теги (копировать блоки в приложение)

Порядок tids = порядок строк. Если тег уже есть — tids сдвинутся; сверь `?kpod`.

### kns — контекст и namespace

```text
#kns=кластер / namespace
#kns kubectl config current-context
#kns kubectl config get-contexts
#kns kubectl get ns
#kns kubectl get ns $NS -o yaml
#kns kubectl api-resources --namespaced=true --verbs=list
```

### kpod — поды

```text
#kpod=поды в $NS
#kpod kubectl get pods -n $NS -o wide
#kpod kubectl get pods -n $NS --field-selector=status.phase!=Running
#kpod kubectl get pods -n $NS -l app=$APP -o wide
#kpod kubectl describe pod $POD -n $NS
#kpod kubectl get pod $POD -n $NS -o json
#kpod kubectl get pod $POD -n $NS -o jsonpath='{.status.containerStatuses[*].name}{"\n"}{.status.containerStatuses[*].state}{"\n"}{.status.containerStatuses[*].lastState}{"\n"}'
#kpod kubectl top pod -n $NS
#kpod kubectl get pod $POD -n $NS -o jsonpath='{.spec.nodeName}{"\n"}{.status.podIP}{"\n"}{.status.hostIP}{"\n"}'
```

### klog — логи (без follow)

```text
#klog=логи $POD
#klog kubectl logs $POD -n $NS --tail=200
#klog kubectl logs $POD -n $NS -c $CTR --tail=200
#klog kubectl logs $POD -n $NS --previous --tail=200
#klog kubectl logs -n $NS -l app=$APP --tail=100 --max-log-requests=10
#klog kubectl logs $POD -n $NS --tail=200 | grep -iE 'error|exception|fatal|panic|oom'
```

Follow / exec — не теги на Enter, а TTY:

```text
> kubectl logs -f $POD -n $NS --tail=50
> kubectl exec -it $POD -n $NS -- sh
```

### kev — события

```text
#kev=events $NS / $POD
#kev kubectl get events -n $NS --sort-by=.lastTimestamp
#kev kubectl get events -n $NS --field-selector involvedObject.name=$POD
#kev kubectl get events -n $NS --field-selector type=Warning --sort-by=.lastTimestamp
```

### ksvc — Service → Endpoints → Pod

```text
#ksvc=сервис и endpoints
#ksvc kubectl get svc,ep -n $NS
#ksvc kubectl describe svc $SVC -n $NS
#ksvc kubectl get endpoints $SVC -n $NS -o yaml
#ksvc kubectl get endpointslice -n $NS -l kubernetes.io/service-name=$SVC
#ksvc kubectl get networkpolicy -n $NS
```

### king — Ingress (плюс встроенный `:i`)

```text
#king=ingress
#king kubectl get ingress -n $NS -o wide
#king kubectl describe ingress $ING -n $NS
#king kubectl get ingress $ING -n $NS -o json
```

В TUI, не теги:

```text
:i list -n $NS
:i analyze $ING
:i check $SVC
```

### kdep — workload / rollout

```text
#kdep=deploy / rs / rollout
#kdep kubectl get deploy,rs,sts,ds -n $NS
#kdep kubectl describe deploy $DEPLOY -n $NS
#kdep kubectl get deploy $DEPLOY -n $NS -o json
#kdep kubectl rollout status deploy/$DEPLOY -n $NS
#kdep kubectl rollout history deploy/$DEPLOY -n $NS
#kdep kubectl get rs -n $NS -l app=$APP -o wide
```

Рестарт — отдельным Enter, когда решите:

```text
kubectl rollout restart deploy/$DEPLOY -n $NS
```

### kjq — фильтры на `|` с фокуса JSON-блока

```text
#kjq=jq к stdout блока
#kjq jq '.items[] | {name:.metadata.name, phase:.status.phase, restarts:.status.containerStatuses[0].restartCount, ready:.status.containerStatuses[0].ready}'
#kjq jq '.status.containerStatuses[] | {name, ready, restarts:.restartCount, state, lastState}'
#kjq jq '.status.conditions'
#kjq jq '.spec.containers[] | {name, image, resources, ports}'
#kjq jq '.subsets[]?.addresses[]?.ip'
#kjq jq '.spec.rules[] | {host, paths:[.http.paths[] | {path, svc:.backend.service.name}]}'
```

---

## 2. Плейбуки (сохранить как теги-сборки)

Имена `kcrash`, `knet`, `kroll` — один tid = одна цепочка. Смотреть `?kcrash` → `!! kcrash[1]`.

Точка с запятой — все шаги подряд (ошибка на середине не останавливает). `&&` — стоп на ошибке.

### CrashLoop / ImagePull / OOM

```text
#kcrash=под не Running: список → describe → previous logs → events
#kcrash !kpod[2] ; echo '--- describe ---' ; !kpod[4] ; echo '--- previous logs ---' ; !klog[3] ; echo '--- events ---' ; !kev[2]
```

Как гонять:

```text
$NS=my-ns
!! kpod[2]                 # не-Running, F2 → имя в $POD
$POD=api-7f8c9
!! kcrash[1]
```

JSON-состояние контейнера: `!! kpod[5]` → `F5` → `|` + `!kjq[2]`.

### Сервис жив, трафик нет (SVC → EP → Pod)

```text
#knet=svc / endpoints / поды приложения
#knet !ksvc[1] ; echo '--- svc ---' ; !ksvc[2] ; echo '--- endpoints ---' ; !ksvc[3] ; echo '--- pods ---' ; !kpod[3]
```

```text
$SVC=api
$APP=api
!! knet[1]
```

Пустые endpoints: селектор vs labels (`F2` по `describe svc`, сравнить с `kpod[3]`). Дальше NetworkPolicy: `!! ksvc[5]`.

### Ingress / 5xx

```text
$ING=api
:i list -n $NS
:i analyze $ING
:i check $SVC
!! king[2]
!! king[3]
```

JSON правил: фокус на `king[3]` → `F5` или `|` + `!kjq[6]`.

С ноды/ноутбука (тег `net` из сида):

```text
!! net[3] https://$HOST/healthz
```

### Rollout застрял

```text
#kroll=deploy + status + rs
#kroll !kdep[2] ; echo '--- status ---' ; !kdep[4] ; echo '--- rs ---' ; !kdep[6] ; echo '--- not running ---' ; !kpod[2]
```

```text
$DEPLOY=api
$APP=api
!! kroll[1]
```

Частые причины в `describe deploy`: quota, probe, missing image, PDB, old ReplicaSet.

### «Что случилось в namespace за 10 минут»

```text
#kwatch=wide + warnings
#kwatch !kpod[1] ; echo '--- not running ---' ; !kpod[2] ; echo '--- warnings ---' ; !kev[3]
```

```text
!! kwatch[1]
```

Поиск по журналу: на блоке `/` → `BackOff` / `OOMKilled` / `FailedScheduling`, затем `n`.

---

## 3. Короткие сборки без плейбук-тега

Ввод как есть, Tab по `!kpod` подставляет ссылку:

```text
!! kpod[1] | kjq[1]
!! kpod[5] | kjq[2]
!! kpod[5] | kjq[3]
!! ksvc[3] | kjq[5]
!! king[3] | kjq[6]
```

Пайп от **уже выполненного** блока (фокус на нём):

```text
| grep -i crash
| jq '.status.containerStatuses'
```

Повторить ту же kubectl-команду: фокус на блоке → `:r`.

---

## 4. Карта «симптом → цепочка»

| Симптом | Переменные | Цепочка |
|---|---|---|
| Под в CrashLoopBackOff | `$NS`, `$POD` | `!! kcrash[1]` затем `!! klog[1]` |
| ImagePullBackOff | `$NS`, `$POD` | `!! kpod[4]` ; `!! kev[2]` |
| Pending / FailedScheduling | `$NS`, `$POD` | `!! kpod[4]` ; `!! kev[3]` |
| 0 endpoints | `$NS`, `$SVC`, `$APP` | `!! knet[1]` |
| 5xx снаружи | `$NS`, `$ING`, `$SVC` | `:i analyze` + `!! king[2]` |
| Rollout 0/1 | `$NS`, `$DEPLOY`, `$APP` | `!! kroll[1]` |
| OOMKilled | `$NS`, `$POD` | `!! kpod[5]` → F5 `.resources` ; `!! kpod[7]` |
| Неясный шум в ns | `$NS` | `!! kwatch[1]` + `:/error` |

---

## 5. Что не класть в `#tag`

- `kubectl logs -f`, `exec -it`, `port-forward`, `htop` — только `> cmd`.
- `kubectl delete` / `rollout restart` / `rollout undo` — руками, не в автоцепочку.
- Имена подов с hash — в `$POD` с журнала, не зашивать в тег.

Экспорт набора коллеге: `:export kcrash /tmp/kcrash.json` (один тег за раз).
