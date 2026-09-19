# IDvjPy 的 HashiCorp Vault 手册

标签 **`vault`**。运行手册：`vstat`、`vkv`、`vapprole`（检查与登录）。  
`kv get` 会把密钥**打印到日志** —— 不会进入自动命令链；检查路径请用 `kv metadata get`。

`vvars` 不打印 `VAULT_TOKEN`，只打印 `token=set` / `token=unset`。

```bash
python3 src/seed_vault.py --seed
# 或与其余 ops 一起：
python3 src/seed_ops.py --seed
```

```text
$VAULT_ADDR=https://vault.example.com:8200
$VAULT_NAMESPACE=
$MOUNT=secret
$SECRET=secret/app
$ROLE=
$POLICY=default
$FIELD=
!! vvars[1]
```

令牌放在环境变量中（`export VAULT_TOKEN=…` 或 `vault login`），不在种子命令里。

---

## vault — 命令 (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `vault status` | Sealed / HA / 版本 |
| 2 | `vault status -format=json` | JSON → F5 |
| 3 | `vault read sys/health` | 通过 CLI 的 Health |
| 4 | `curl -sS $VAULT_ADDR/v1/sys/health` | Health HTTP，通常无需令牌 |
| 5 | `vault auth list` | 认证方法 |
| 6 | `vault secrets list` | Secret engines |
| 7 | `vault policy list` | 策略 |
| 8 | `vault policy read $POLICY` | `$POLICY` 的文本 |
| 9 | `vault audit list` | Audit devices |
| 10 | `vault token lookup` | 当前令牌的 TTL 与 policies |
| 11 | `vault token lookup -format=json` | Lookup JSON |
| 12 | `vault kv list $MOUNT` | `$MOUNT` 上的键 |
| 13 | `vault kv list $SECRET` | `$SECRET` 中的键 |
| 14 | `vault kv metadata get $SECRET` | 元数据，不含值 |
| 15 | `vault kv metadata get -format=json $SECRET` | Metadata JSON |
| 16 | `vault kv get $SECRET` | **密钥值会进入日志** |
| 17 | `vault kv get -field=$FIELD $SECRET` | 单个字段 |
| 18 | `vault operator raft list-peers` | Raft peers |
| 19 | `vault operator raft autopilot state` | Autopilot |
| 20 | `vault read auth/approle/role/$ROLE` | AppRole `$ROLE` |
| 21 | `vault login` | 登录（`> vault login`） |
| 22 | `vault kv put $SECRET $FIELD=value` | 写入（会修改 Vault） |

不在运行手册中：`operator seal`、`token revoke`、`kv delete` / `destroy`、`kv put`。

对于 KV v2，CLI 路径是 `secret/app`，而不是 `secret/data/app`。

---

## AppRole：登录（标签 `vapprole`）

流程：令牌 → 角色名 → `role_id` → `secret_id` → `login` → 临时令牌。
`vault` 表格中的值会直接从块输出带入变量 —— 写法
`$VAR=@key` / `$$VAR=@key` 取该行的剩余部分，其第一个词元等于
`key`（只考虑聚焦的或最后一个**已完成**的块）。
`@last` —— 最后一行非空内容（在 `| jq -r .field` 后很方便）。

各步骤用运行指令（`run:`）标记：需要人来决定的地方是
`run:manual`，其余自动执行。因此命令链用一条命令启动
`:run vapprole`（见 `:? run`）：运行会在令牌、角色名和
签发 `secret_id` 处停下，而 `role_id`/`secret_id`/`token` 会从块输出中获取。
步骤 1 和 2 是前缀行（`$$VAULT_TOKEN=`、`$ROLE=`）：值
**追加在 `=` 之后**，所以未改动该行就按 Enter 不会发送
虚构的角色名（以前那里是 `$ROLE=custom-role`，按 Enter 就会执行它）。

| tid | 步骤 | 模式 | 作用 |
|-----|-----|-------|------------|
| 1 | `$$VAULT_TOKEN=` | `run:manual` | 来自 vault.website 的令牌：在 `=` 后粘贴值并按 Enter |
| 2 | `$ROLE=` | `run:manual` | AppRole 名称：在 `=` 后补上（例如 `custom-role`） |
| 3 | `vault read auth/approle/role/$ROLE/role-id` | `run:auto` | `role_id` |
| 4 | `$$ROLE_ID=@role_id` | `run:auto` | 来自步骤 3 的密钥 |
| 5 | `vault write -force auth/approle/role/$ROLE/secret-id` | `run:manual` | 新的 `secret_id`（签发需确认） |
| 6 | `$$SECRET_ID=@secret_id` | `run:auto` | 来自步骤 5 的密钥 |
| 7 | `vault write auth/approle/login role_id="$ROLE_ID" secret_id="$SECRET_ID"` | `run:auto` | 登录，`token` |
| 8 | `$$VAULT_TOKEN=@token` | `run:auto` | 更新令牌 |
| 9 | `vault read $SECRET` | `run:auto` | 用新令牌检查访问 |

```text
# 整条命令链（半自动）：在需要人的地方停下
:run vapprole

# 相同，但在每一步都停下（编辑该行并按 Enter），
# 或者不执行 —— 仅生成计划：
:run vapprole --step
:run vapprole --dry

# 在步骤之间中断：Esc 或
:run stop
```

手动时同样的步骤仍留在库中：`!vapprole[N]` 把该行插入输入框，
启动用单独的 Enter（`$$VAR=@key` 是变量前缀，不能通过 `;`
粘到命令上）。在 `:run` 中，带 `run:manual` 的步骤会自己插入该行并等待，
而空 Enter 会跳过该步骤（例如令牌已经存在）；步骤 1–2 需要在 `=` 后
补上值。

已代入值的现成登录行：在步骤 7（login 块）之后
`:cmd` 会把展开后的命令放入剪贴板
`vault write auth/approle/login role_id="2474…" secret_id="3ab7…"`；
日志中得到的是掩码版本（`****`），`:cmd show` 打印完整行。

密钥（`$$…`）不会显示在屏幕上，并且只在退出
应用前存在（`secrets_<instance>.json` 会在退出时删除）。

---

## 运行手册

| 标签 | 命令链 |
|-----|---------|
| `vstat[1]` | status → health HTTP → auth list → secrets list |
| `vkv[1]` | `kv list $SECRET` → `kv metadata get` |

```text
!! vstat[1]
$SECRET=secret/app
!! vkv[1]
```
