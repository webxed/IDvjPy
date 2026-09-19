# IDvjPy systemd 手册

**`sctl`**（systemctl）、**`jctl`**（journalctl）、**`dmesg`** 标签。  
检查 playbook：`sfail`、`sstat`、`kmsg`。`start` / `stop` / `restart` / `reload` — 仅手动执行。

凡是会打开 `less` 的地方都用 `--no-pager`。跟随（`-f` / `-w`）最好通过 `> cmd`。部分命令需要 root。

```bash
python3 src/seed_systemd.py --seed
# 或连同其他 ops：
python3 src/seed_ops.py --seed
```

不触碰 Linux 标签 `proc` / `file` / `logs`。不要把 `sctl` 与内核的 `sysctl` 混淆。

```text
$UNIT=nginx.service
$SINCE=1 hour ago
$BOOT=0
!! sysvars[1]
```

`$BOOT`：`0` — 当前启动，`-1` — 上一次。

---

## sctl — systemctl (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `systemctl --no-pager --failed` | 失败的 unit |
| 2 | `list-units --type=service --state=failed` | 失败的 service |
| 3 | `systemctl --no-pager status $UNIT` | `$UNIT` 状态 |
| 4 | `systemctl show $UNIT --no-pager` | `$UNIT` 属性 |
| 5 | `systemctl cat $UNIT --no-pager` | `$UNIT` unit 文件 |
| 6 | `systemctl is-active $UNIT` | `$UNIT` 活动/非活动 |
| 7 | `systemctl is-enabled $UNIT` | `$UNIT` 已启用/已禁用 |
| 8 | `list-units --type=service --state=running` | 运行中的 service |
| 9 | `systemctl list-timers --all --no-pager` | 定时器 |
| 10 | `systemctl daemon-reload` | 重新加载 unit 文件 |
| 11 | `systemctl reload $UNIT` | 重新加载 `$UNIT`（会改动服务） |
| 12 | `systemctl restart $UNIT` | 重启 `$UNIT`（会改动服务） |
| 13 | `systemctl start $UNIT` | 启动 `$UNIT`（会改动服务） |
| 14 | `systemctl stop $UNIT` | 停止 `$UNIT`（会改动服务） |
| 15 | `systemctl reset-failed $UNIT` | 重置 `$UNIT` 的失败状态 |

playbook 中没有 tid 10–15。

---

## jctl — journalctl (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `journalctl --no-pager -n 80` | 最近 80 行 |
| 2 | `-p err -n 80` | 错误 |
| 3 | `-u $UNIT -n 100` | `$UNIT` 的日志 |
| 4 | `-u $UNIT -p err` | `$UNIT` 的错误 |
| 5 | `-u $UNIT --since "$SINCE"` | `$UNIT` 自 `$SINCE` 起的日志 |
| 6 | `--list-boots` | 列出启动记录 |
| 7 | `-b $BOOT -n 80` | 启动 `$BOOT` 的日志 |
| 8 | `-k -n 80` | 内核（类似 dmesg） |
| 9 | `--disk-usage` | 日志磁盘占用 |
| 10 | `-u $UNIT -o json-pretty -n 20` | JSON `$UNIT` → F5 |
| 11 | `journalctl -f -u $UNIT` | 跟随 `$UNIT`（更好: `> journalctl -f …`） |

---

## dmesg (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `dmesg --color=never \| tail -n 80` | 最近 80 行 |
| 2 | `dmesg -T --color=never \| tail -n 80` | 人类可读时间 |
| 3 | `dmesg -T --level=err,warn` | err+warn |
| 4 | `dmesg -T --level=err` | 仅 err |
| 5 | `dmesg -w` | 跟随（更好: `> dmesg -w`） |

---

## playbook

| 标签 | 命令链 |
|-----|---------|
| `sfail[1]` | `--failed` → list-units failed |
| `sstat[1]` | status `$UNIT` → is-active → journal `-u` |
| `kmsg[1]` | dmesg err/warn → `journalctl -k` |

```text
!! sfail[1]
$UNIT=nginx.service
!! sstat[1]
!! kmsg[1]
```
