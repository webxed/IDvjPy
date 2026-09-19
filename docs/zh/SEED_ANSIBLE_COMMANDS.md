# IDvjPy ansible 手册

**`ansible`**、**`aplay`**、**`avault`**、**`agalaxy`** 标签。  
检查 playbook：`achk`、`aping`。真实的 `ansible-playbook`（不带 `--check`）和写入 vault 文件 — 仅手动执行。

```bash
python3 src/seed_ansible.py --seed
# 或连同其他 ops：
python3 src/seed_ops.py --seed
```

不触碰 linux / k8s / git。`$VAULTFILE` — ansible-vault 文件，不是 HashiCorp Vault。

```text
$INV=inventory.ini
$PLAY=site.yml
$LIMIT=
$TAGS=
$HOST=all
$MODULE=ping
$ARGS=
$VAULTFILE=secrets.yml
$ROLE=
$COLLECTION=
!! ansvars[1]
```

交互式：`> ansible-console -i $INV`、`> ansible-vault edit $VAULTFILE`。

---

## ansible — ad-hoc 和 inventory (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `ansible --version` | ansible 版本 |
| 2 | `ansible-config dump --only-changed` | 非默认配置 |
| 3 | `ansible-inventory -i $INV --list` | inventory JSON |
| 4 | `ansible-inventory -i $INV --graph` | 分组图 |
| 5 | `ansible $HOST -i $INV --list-hosts` | 匹配模式 `$HOST` 的主机 |
| 6 | `ansible $HOST -i $INV -m ping` | ping `$HOST` |
| 7 | `ansible $HOST -i $INV -m setup` | `$HOST` 的 facts |
| 8 | `setup filter=ansible_distribution*` | `$HOST` 的发行版 |
| 9 | `ansible … -m command -a '$ARGS'` | 在 `$HOST` 上以 `command` 执行 `$ARGS` |
| 10 | `ansible … -m $MODULE -a '$ARGS' --check` | 模块 `$MODULE` 的检查模式 |
| 11 | `ansible … -m $MODULE -a '$ARGS'` | 模块 `$MODULE`（会改动主机） |
| 12 | `ansible-doc $MODULE` | `$MODULE` 文档 |
| 13 | `ansible-console -i $INV` | REPL（更好: `> ansible-console …`） |

不在 playbook 中：tid 11（会改动主机），tid 13（交互式）。

---

## aplay — ansible-playbook (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `--syntax-check` | 语法检查 `$PLAY` |
| 2 | `--list-hosts` | playbook 主机 |
| 3 | `--list-tasks` | playbook 任务 |
| 4 | `--list-tags` | playbook 标签 |
| 5 | `--check --diff` | 检查 + 差异 |
| 6 | `--check --diff --limit $LIMIT` | 检查，限制 `$LIMIT` |
| 7 | `--check --diff --tags $TAGS` | 检查，标签 `$TAGS` |
| 8 | `--limit $LIMIT` | 运行，限制 `$LIMIT`（会改动主机） |
| 9 | `--tags $TAGS` | 运行，标签 `$TAGS`（会改动主机） |
| 10 | `ansible-playbook -i $INV $PLAY` | 运行 `$PLAY`（会改动主机） |

`achk` 中只有 tid 1 和 5。

---

## avault / agalaxy

`avault`：view 和 encrypt/decrypt 到 stdout — 检查；文件 encrypt/decrypt、create、edit — 会改动磁盘 / 交互式。

`agalaxy`：list/search — 检查；install/init — 写入 `~/.ansible`。

---

## playbook

| 标签 | 命令链 |
|-----|---------|
| `aping[1]` | list-hosts → ping |
| `achk[1]` | inventory `--list` → syntax-check → check `--diff` |

```text
$HOST=all
!! aping[1]
$PLAY=site.yml
!! achk[1]
!! aplay[5]
```
