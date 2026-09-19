# k8s 排障命令链

用于 Kubernetes 故障处理的实用标签：宽泛的 `get` → 名称写入 `$POD` / `$DEPLOY` → `describe` / 日志 / events / JSON。

来自 [`SEED_LINUX_COMMANDS.md`](SEED_LINUX_COMMANDS.md) 的种子标签 `kube` 是通用手册。  
本套标签**不改动** `proc` / `file` / `net` / `kube`。

```bash
python3 src/seed_k8s_chains.py --seed
```

重复执行 `--seed` 只会覆盖：
`kvars` `kns` `kpod` `klog` `kev` `ksvc` `king` `kdep` `kres` `kjq`
`kavail` `kstore`
`kcrash` `knet` `kroll` `kwatch` `kquota` `kscale` `kvolume`。

规范的 tid：[`SEED_K8S_CHAINS_COMMANDS.md`](SEED_K8S_CHAINS_COMMANDS.md)。

## TUI 中的循环

1. `$NS=my-ns`（同一个 namespace 会被 `:i list -n my-ns` 采用）
2. 宽泛的 `get`（`!kpod[1]`）→ 日志中的块
3. Tab / 点击 → F2 → Enter 复制名称 → `$POD=` + 粘贴
4. 精细化标签：`describe` / logs / events 已带上 `$POD`
5. JSON：`-o json` → F5。组装剧本：`!! kcrash[1]`
6. 无法扩容——`!kavail[1]` (HPA)、`!kavail[3]` (PDB)、`!! kscale[1]`
7. 处于 Pending 时——卷：`!kstore[1]`、`!! kvolume[1]`；权限：`!kns[7]`（`auth can-i --list`）
8. 新版 Events：`!kev[4]`（`kubectl events --types=Warning`，1.23+），定点使用——`!kev[5]`

`kubectl logs -f` / `exec -it` / `port-forward` —— 需加 `>` 前缀（真正的 TTY）。  
`delete` / `rollout restart` / `undo` —— 不放入剧本。

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
