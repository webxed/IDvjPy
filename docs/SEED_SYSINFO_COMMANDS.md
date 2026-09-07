# Справочник hostinfo / lsof / strace для IDvjPy

Теги **`hinfo`**, **`lsof`**, **`strace`**.  
Плейбуки: `hstat`, `lport`, `pdbg`. Live `strace -p` без `timeout` — через `> cmd`. Attach к чужому PID часто нужен root / `CAP_SYS_PTRACE`.

```bash
python3 src/seed_sysinfo.py --seed
# или вместе с остальными ops:
python3 src/seed_ops.py --seed
```

Не трогает linux `proc` (ps/top/kill) и `ss` из netfw.

```text
$PID=
$PORT=443
$FILE=/var/log/syslog
$CMD=true
$PROC=sshd
$TRACE=network
!! hivars[1]
```

`$TRACE` — фильтр strace (`network`, `file`, `process`, `all`, …). `$CMD` — командная строка для запуска под strace; `$PROC` — имя для `lsof -c`.

---

## hinfo (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `uname -a` | Ядро |
| 2 | `cat /etc/os-release` | Дистрибутив |
| 3 | `hostnamectl --no-pager` | Hostname |
| 4 | `timedatectl --no-pager` | Часы / NTP |
| 5 | `uptime` | Load |
| 6 | `free -h` | RAM / swap |
| 7 | `lscpu` | CPU |
| 8 | `nproc` | Число CPU |

---

## lsof (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `lsof -nP -iTCP:$PORT -sTCP:LISTEN` | Кто слушает `$PORT` |
| 2 | `lsof -nP -i :$PORT` | Все сокеты `$PORT` |
| 3 | `lsof -nP -p $PID` | Файлы `$PID` |
| 4 | `lsof -nP "$FILE"` | Кто открыл файл |
| 5 | `lsof -nP -c $PROC` | По имени процесса |
| 6 | TCP LISTEN, 40 строк | Обзор слушателей |
| 7 | файлы `$USER`, 40 строк | По пользователю |

`-nP` — без DNS и без имён портов (быстрее в TUI).

---

## strace (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `strace -V` | Версия |
| 2 | `strace -c -- $CMD` | Сводка сисвызовов |
| 3 | `strace -f -c -- $CMD` | Со детьми |
| 4 | `-e trace=$TRACE -c -- $CMD` | Сводка фильтра |
| 5 | `-e trace=$TRACE -- $CMD` | Полная трасса короткой `$CMD` |
| 6 | `timeout 8 strace -c -p $PID` | Сводка живого PID, 8 с |
| 7 | `timeout 8 strace -f -e trace=$TRACE -p $PID` | Фильтр на PID, 8 с |
| 8 | `strace -p $PID` | Follow (`> strace -p $PID`) |

В `pdbg` только tid 6 (с `timeout`). Без `-c` трасса `$CMD` может быть длинной — берите короткую команду (`true`, `ls`).

---

## Плейбуки

| Тег | Цепочка |
|-----|---------|
| `hstat[1]` | uname → uptime → free |
| `lport[1]` | LISTEN `$PORT` → все сокеты `$PORT` |
| `pdbg[1]` | `lsof -p` → `timeout strace -c -p` |

```text
!! hstat[1]
$PORT=22
!! lport[1]
$PID=1
!! pdbg[1]
```
