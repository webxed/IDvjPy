# IDvjPy helm 手册

**`helm`** 标签。playbook：`hls`。检查与 dry-run；不带 `--dry-run` 的 `upgrade`/`uninstall` — 仅手动执行。

```bash
python3 src/seed_helm.py --seed
```

不触碰 `kube` / `kpod` / 其余 k8s 标签。

```text
$NS=default
$RELEASE=
$CHART=
$VALUES=values.yaml
!! hvars[1]
```

`$RELEASE` / `$CHART` / `$VALUES` 属于集群日志变量列表
（`kctx_vars`，默认与 kubectl 栈 `NS POD DEPLOY SVC ING APP CTR QUOTA` 一起）。
因此，进入集群后（`klogin …` / `:kctx <cluster>`）对其中任一变量赋值
会把快照写入 `kctx.json`，而 `:kctx <cluster>` / `:kctx N` 会连同
`$NS` 一起恢复 release — 不必再回忆这个集群里是哪个 release 和哪份 values。
快照只包含非空值，因此 `$RELEASE=`（空）不会添加任何内容。
`VALUES` 通常是相对路径：`:kctx N` 会原样返回它，所以要
在包含该文件的目录中运行 helm 命令（或设置绝对路径）。

---

## helm — 命令 (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `helm list -n $NS` | `$NS` 中的 release |
| 2 | `helm list -A` | 所有命名空间中的 release |
| 3 | `helm status $RELEASE -n $NS` | `$RELEASE` 的状态 |
| 4 | `helm history $RELEASE -n $NS` | 版本历史 |
| 5 | `helm get values $RELEASE -n $NS` | release values |
| 6 | `helm get manifest $RELEASE -n $NS` | release manifest |
| 7 | `helm get notes $RELEASE -n $NS` | release 说明 |
| 8 | `helm repo list` | chart 仓库 |
| 9 | `helm search repo $CHART` | 搜索 chart `$CHART` |
| 10 | `helm show chart $CHART` | chart 元数据 |
| 11 | `helm show values $CHART` | chart 默认 values |
| 12 | `helm template $RELEASE $CHART -n $NS -f $VALUES` | 无需集群渲染 |
| 13 | `helm upgrade --install … --dry-run --debug` | dry-run 升级 |
| 14 | `helm upgrade --install …` | upgrade --install（会改动集群） |
| 15 | `helm rollback $RELEASE 0 -n $NS --dry-run` | dry-run 回滚 |
| 16 | `helm uninstall $RELEASE -n $NS --dry-run` | dry-run 卸载 |
| 17 | `helm env` | helm 环境 |

helm 中的 `rollback 0` — 上一个修订版本。不带 dry-run 的真实 rollback/uninstall 不会放进种子的 playbook 中。

---

## playbook

| 标签 | 命令链 |
|-----|---------|
| `hls[1]` | list → status → history → values |

```text
$RELEASE=myapp
!! hls[1]
!! helm[13]
```
