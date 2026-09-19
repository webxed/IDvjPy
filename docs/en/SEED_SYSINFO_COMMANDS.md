# hostinfo / lsof / strace handbook for IDvjPy

Tags **`hinfo`**, **`lsof`**, **`strace`**.  
Playbooks: `hstat`, `lport`, `pdbg`. Live `strace -p` without `timeout` goes via `> cmd`. Attaching to someone else's PID often needs root / `CAP_SYS_PTRACE`.

```bash
python3 src/seed_sysinfo.py --seed
# or together with the other ops:
python3 src/seed_ops.py --seed
```

Does not touch linux `proc` (ps/top/kill) or `ss` from netfw.

```text
$PID=
$PORT=443
$FILE=/var/log/syslog
$CMD=true
$PROC=sshd
$TRACE=network
!! hivars[1]
```

`$TRACE` is the strace filter (`network`, `file`, `process`, `all`, …). `$CMD` is the command line to run under strace; `$PROC` is the name for `lsof -c`.

---

## hinfo (tid)

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `uname -a` | Kernel and hostname |
| 2 | `cat /etc/os-release` | Distribution |
| 3 | `hostnamectl --no-pager` | Hostname / machine-id |
| 4 | `timedatectl --no-pager` | Clock and NTP |
| 5 | `uptime` | Uptime and load |
| 6 | `free -h` | RAM / swap |
| 7 | `lscpu` | CPU |
| 8 | `nproc` | CPU count |

---

## lsof (tid)

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `lsof -nP -iTCP:$PORT -sTCP:LISTEN` | Who listens on TCP `$PORT` |
| 2 | `lsof -nP -i :$PORT` | Sockets on `$PORT` |
| 3 | `lsof -nP -p $PID` | Files of process `$PID` |
| 4 | `lsof -nP "$FILE"` | Who opened `$FILE` |
| 5 | `lsof -nP -c $PROC` | Processes named `$PROC` |
| 6 | TCP LISTEN, 40 rows | First 40 TCP listeners |
| 7 | files of `$USER`, 40 rows | Files of user `$USER` |

`-nP` means no DNS and no port names (faster in the TUI).

---

## strace (tid)

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `strace -V` | strace version |
| 2 | `strace -c -- $CMD` | Syscall summary of `$CMD` |
| 3 | `strace -f -c -- $CMD` | Summary, with children |
| 4 | `-e trace=$TRACE -c -- $CMD` | Summary of filter `$TRACE` |
| 5 | `-e trace=$TRACE -- $CMD` | Trace `$CMD` (short command) |
| 6 | `timeout 8 strace -c -p $PID` | Summary of `$PID`, 8s (needs ptrace) |
| 7 | `timeout 8 strace -f -e trace=$TRACE -p $PID` | Filter `$TRACE` on `$PID`, 8s |
| 8 | `strace -p $PID` | Follow `$PID` (better: `> strace -p $PID`) |

`pdbg` includes only tid 6 (with `timeout`). Without `-c` the trace of `$CMD` can be long — pick a short command (`true`, `ls`).

---

## Playbooks

| Tag | Chain |
|-----|---------|
| `hstat[1]` | uname → uptime → free |
| `lport[1]` | LISTEN `$PORT` → all sockets `$PORT` |
| `pdbg[1]` | `lsof -p` → `timeout strace -c -p` |

```text
!! hstat[1]
$PORT=22
!! lport[1]
$PID=1
!! pdbg[1]
```
