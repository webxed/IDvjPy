# Цепочки для расследования k8s

Рабочие теги для инцидента в Kubernetes: широкий `get` → имя в `$POD` / `$DEPLOY` → `describe` / логи / events / JSON.

Сидовый тег `kube` из [`SEED_LINUX_COMMANDS.md`](docs/SEED_LINUX_COMMANDS.md) — общий справочник.  
Этот набор **не трогает** `proc` / `file` / `net` / `kube`.

```bash
python3 src/seed_k8s_chains.py --seed
```

Повторный `--seed` перезаписывает только:
`kvars` `kns` `kpod` `klog` `kev` `ksvc` `king` `kdep` `kres` `kjq`
`kavail` `kstore`
`kcrash` `knet` `kroll` `kwatch` `kquota` `kscale` `kvolume`.

Канонические tid: [`SEED_K8S_CHAINS_COMMANDS.md`](docs/SEED_K8S_CHAINS_COMMANDS.md).

## Цикл в TUI

1. `$NS=my-ns` (то же namespace подхватывает `:i list -n my-ns`)
2. Широкий `get` (`!kpod[1]`) → блок в журнале
3. Tab / клик → F2 → Enter копирует имя → `$POD=` + вставка
4. Узкий тег: `describe` / logs / events уже с `$POD`
5. JSON: `-o json` → F5. Сборка плейбука: `!! kcrash[1]`
6. Не масштабируется — `!kavail[1]` (HPA), `!kavail[3]` (PDB), `!! kscale[1]`
7. Под Pending — том: `!kstore[1]`, `!! kvolume[1]`; права: `!kns[7]` (`auth can-i --list`)
8. Events по-новому: `!kev[4]` (`kubectl events --types=Warning`, 1.23+), точечно — `!kev[5]`

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
