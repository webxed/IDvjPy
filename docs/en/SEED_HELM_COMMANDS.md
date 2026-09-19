# helm handbook for IDvjPy

Tag **`helm`**. Playbook: `hls`. Inspection and dry-run; `upgrade`/`uninstall` without `--dry-run` are manual only.

```bash
python3 src/seed_helm.py --seed
```

Does not touch `kube` / `kpod` / the other k8s tags.

```text
$NS=default
$RELEASE=
$CHART=
$VALUES=values.yaml
!! hvars[1]
```

`$RELEASE` / `$CHART` / `$VALUES` are part of the cluster journal variable list
(`kctx_vars`, by default together with the kubectl stack `NS POD DEPLOY SVC ING APP CTR QUOTA`).
So after entering a cluster (`klogin …` / `:kctx <cluster>`), assigning any of them
writes a snapshot to `kctx.json`, and `:kctx <cluster>` / `:kctx N` restores the release together
with `$NS` — no need to remember which release and which values were in this cluster.
Only non-empty values go into the snapshot, so `$RELEASE=` (empty) adds nothing.
`VALUES` is usually a relative path: `:kctx N` returns it as is, so
run helm commands from the directory with that file (or set an absolute path).

---

## helm — commands (tid)

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `helm list -n $NS` | Releases in `$NS` |
| 2 | `helm list -A` | Releases in all namespaces |
| 3 | `helm status $RELEASE -n $NS` | Status of `$RELEASE` |
| 4 | `helm history $RELEASE -n $NS` | Revision history |
| 5 | `helm get values $RELEASE -n $NS` | Release values |
| 6 | `helm get manifest $RELEASE -n $NS` | Release manifests |
| 7 | `helm get notes $RELEASE -n $NS` | Release notes |
| 8 | `helm repo list` | Chart repositories |
| 9 | `helm search repo $CHART` | Search for chart `$CHART` |
| 10 | `helm show chart $CHART` | Chart metadata |
| 11 | `helm show values $CHART` | Default chart values |
| 12 | `helm template $RELEASE $CHART -n $NS -f $VALUES` | Render without a cluster |
| 13 | `helm upgrade --install … --dry-run --debug` | Dry-run upgrade |
| 14 | `helm upgrade --install …` | `upgrade --install` (changes the cluster) |
| 15 | `helm rollback $RELEASE 0 -n $NS --dry-run` | Dry-run rollback |
| 16 | `helm uninstall $RELEASE -n $NS --dry-run` | Dry-run uninstall |
| 17 | `helm env` | helm environment |

`rollback 0` in helm means the previous revision. A real rollback/uninstall without dry-run is not put into a playbook by the seed.

---

## Playbooks

| Tag | Chain |
|-----|---------|
| `hls[1]` | list → status → history → values |

```text
$RELEASE=myapp
!! hls[1]
!! helm[13]
```
