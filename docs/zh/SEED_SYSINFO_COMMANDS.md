# IDvjPy hostinfo / lsof / strace 手册

**`hinfo`**、**`lsof`**、**`strace`** 标签。  
playbook：`hstat`、`lport`、`pdbg`。不带 `timeout` 的实时 `strace -p` — 通过 `> cmd`。附加到其他 PID 通常需要 root / `CAP_SYS_PTRACE`。

```bash
python3 src/seed_sysinfo.py --seed
# 或连同其他 ops：
python3 src/seed_ops.py --seed
```

不触碰 linux `proc`（ps/top/kill）和 netfw 的 `ss`。

```text
$PID=
$PORT=443
$FILE=/var/log/syslog
$CMD=true
$PROC=sshd
$TRACE=network
!! hivars[1]
```

`$TRACE` — strace 的过滤器（`network`、`file`、`process`、`all`、…）。`$CMD` — 在 strace 下运行的命令行；`$PROC` — 用于 `lsof -c` 的名称。

---

## hinfo (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `uname -a` | 内核和主机名 |
| 2 | `cat /etc/os-release` | 发行版 |
| 3 | `hostnamectl --no-pager` | hostname / machine-id |
| 4 | `timedatectl --no-pager` | 时钟和 NTP |
| 5 | `uptime` | 运行时间和负载 |
| 6 | `free -h` | RAM / swap |
| 7 | `lscpu` | CPU |
| 8 | `nproc` | CPU 核数 |

---

## lsof (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `lsof -nP -iTCP:$PORT -sTCP:LISTEN` | 谁监听 TCP `$PORT` |
| 2 | `lsof -nP -i :$PORT` | `$PORT` 上的套接字 |
| 3 | `lsof -nP -p $PID` | 进程 `$PID` 的文件 |
| 4 | `lsof -nP "$FILE"` | 谁打开了 `$FILE` |
| 5 | `lsof -nP -c $PROC` | 名为 `$PROC` 的进程 |
| 6 | TCP LISTEN，40 行 | 前 40 个 TCP 监听 |
| 7 | `$USER` 的文件，40 行 | 用户 `$USER` 的文件 |

`-nP` — 不做 DNS 解析，也不解析端口名（在 TUI 中更快）。

---

## strace (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `strace -V` | strace 版本 |
| 2 | `strace -c -- $CMD` | `$CMD` 的系统调用摘要 |
| 3 | `strace -f -c -- $CMD` | 摘要，含子进程 |
| 4 | `-e trace=$TRACE -c -- $CMD` | 过滤器 `$TRACE` 的摘要 |
| 5 | `-e trace=$TRACE -- $CMD` | 跟踪 `$CMD`（短命令） |
| 6 | `timeout 8 strace -c -p $PID` | `$PID` 的摘要，8 秒（需要 ptrace） |
| 7 | `timeout 8 strace -f -e trace=$TRACE -p $PID` | 对 `$PID` 应用过滤器 `$TRACE`，8 秒 |
| 8 | `strace -p $PID` | 跟随 `$PID`（更好: `> strace -p $PID`） |

`pdbg` 中只有 tid 6（带 `timeout`）。不带 `-c` 时 `$CMD` 的跟踪可能很长 — 请选择短命令（`true`、`ls`）。

---

## playbook

| 标签 | 命令链 |
|-----|---------|
| `hstat[1]` | uname → uptime → free |
| `lport[1]` | LISTEN `$PORT` → `$PORT` 上的所有套接字 |
| `pdbg[1]` | `lsof -p` → `timeout strace -c -p` |

```text
!! hstat[1]
$PORT=22
!! lport[1]
$PID=1
!! pdbg[1]
```
