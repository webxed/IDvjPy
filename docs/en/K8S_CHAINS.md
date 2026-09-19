# k8s investigation chains

Working tags for a Kubernetes incident: wide `get` → name into `$POD` / `$DEPLOY` → `describe` / logs / events / JSON.

The seed tag `kube` from [`SEED_LINUX_COMMANDS.md`](SEED_LINUX_COMMANDS.md) is a general handbook.  
This set **does not touch** `proc` / `file` / `net` / `kube`.

```bash
python3 src/seed_k8s_chains.py --seed
```

A repeated `--seed` overwrites only:
`kvars` `kns` `kpod` `klog` `kev` `ksvc` `king` `kdep` `kres` `kjq`
`kavail` `kstore`
`kcrash` `knet` `kroll` `kwatch` `kquota` `kscale` `kvolume`.

Canonical tids: [`SEED_K8S_CHAINS_COMMANDS.md`](SEED_K8S_CHAINS_COMMANDS.md).

## Cycle in the TUI

1. `$NS=my-ns` (the same namespace is picked up by `:i list -n my-ns`)
2. Wide `get` (`!kpod[1]`) → block in the journal
3. Tab / click → F2 → Enter copies the name → `$POD=` + paste
4. Narrow tag: `describe` / logs / events already with `$POD`
5. JSON: `-o json` → F5. Playbook assembly: `!! kcrash[1]`
6. Not scaling — `!kavail[1]` (HPA), `!kavail[3]` (PDB), `!! kscale[1]`
7. Under Pending — volume: `!kstore[1]`, `!! kvolume[1]`; permissions: `!kns[7]` (`auth can-i --list`)
8. Events the new way: `!kev[4]` (`kubectl events --types=Warning`, 1.23+), pointwise — `!kev[5]`

`kubectl logs -f` / `exec -it` / `port-forward` — with the `>` prefix (real TTY).  
`delete` / `rollout restart` / `undo` — not in playbooks.

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
