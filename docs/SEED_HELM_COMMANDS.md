# Справочник helm для IDvjPy

Тег **`helm`**. Плейбук: `hls`. Осмотр и dry-run; `upgrade`/`uninstall` без `--dry-run` — только руками.

```bash
python3 src/seed_helm.py --seed
```

Не трогает `kube` / `kpod` / остальные k8s-теги.

```text
$NS=default
$RELEASE=
$CHART=
$VALUES=values.yaml
!! hvars[1]
```

---

## helm — команды (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `helm list -n $NS` | Релизы в `$NS` |
| 2 | `helm list -A` | Все namespace |
| 3 | `helm status $RELEASE -n $NS` | Статус |
| 4 | `helm history $RELEASE -n $NS` | Ревизии |
| 5 | `helm get values $RELEASE -n $NS` | Values релиза |
| 6 | `helm get manifest $RELEASE -n $NS` | Манифесты |
| 7 | `helm get notes $RELEASE -n $NS` | Notes |
| 8 | `helm repo list` | Репозитории |
| 9 | `helm search repo $CHART` | Поиск чарта |
| 10 | `helm show chart $CHART` | Метаданные |
| 11 | `helm show values $CHART` | Default values |
| 12 | `helm template $RELEASE $CHART -n $NS -f $VALUES` | Рендер без кластера |
| 13 | `helm upgrade --install … --dry-run --debug` | Dry-run |
| 14 | `helm upgrade --install …` | Меняет кластер |
| 15 | `helm rollback $RELEASE 0 -n $NS --dry-run` | Dry-run rollback |
| 16 | `helm uninstall $RELEASE -n $NS --dry-run` | Dry-run uninstall |
| 17 | `helm env` | Окружение helm |

`rollback 0` в helm — предыдущая ревизия. Реальный rollback/uninstall без dry-run в сид не кладётся в плейбук.

---

## Плейбуки

| Тег | Цепочка |
|-----|---------|
| `hls[1]` | list → status → history → values |

```text
$RELEASE=myapp
!! hls[1]
!! helm[13]
```
