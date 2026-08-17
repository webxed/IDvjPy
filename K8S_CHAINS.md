# Цепочки kubectl для расследования

Рабочие теги для инцидента в Kubernetes: широкий `get` → имя в `$POD` / `$DEPLOY` → `describe` / логи / events / JSON.

Сидовый тег `kube` из [`SEED_LINUX_COMMANDS.md`](SEED_LINUX_COMMANDS.md) — общий справочник.  
Этот набор **не трогает** `proc` / `file` / `net` / `kube`.

```bash
python3 src/seed_k8s_chains.py --seed
```

Повторный `--seed` перезаписывает только:
`kvars` `kns` `kpod` `klog` `kev` `ksvc` `king` `kdep` `kres` `kjq`
`kcrash` `knet` `kroll` `kwatch` `kquota`.

Канонические tid: [`SEED_K8S_CHAINS_COMMANDS.md`](SEED_K8S_CHAINS_COMMANDS.md).

## Цикл в TUI

1. `$NS=my-ns` (то же namespace подхватывает `:i list -n my-ns`)
2. Широкий `get` (`!kpod[1]`) → блок в журнале
3. Tab / клик → F2 → Enter копирует имя → `$POD=` + вставка
4. Узкий тег: `describe` / logs / events уже с `$POD`
5. JSON: `-o json` → F5. Сборка плейбука: `!! kcrash[1]`

`kubectl logs -f` / `exec -it` / `port-forward` — с префиксом `>` (настоящий TTY).  
`delete` / `rollout restart` / `undo` — не в плейбуках.

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
