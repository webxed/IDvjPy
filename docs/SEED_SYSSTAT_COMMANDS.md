# Справочник sysstat для IDvjPy

Теги **`vmstat`**, **`iostat`**, **`mpstat`**. Плейбук **`oload`**.  
Снимки конечные: `$DELAY` × `$SAMPLES`. `htop` / `iotop` / `iftop` — тег `monui`, только `>`.

Не трогает linux `proc` и systemd `sstat`.

```bash
python3 src/seed_sysstat.py --seed
# или вместе с остальными ops:
python3 src/seed_ops.py --seed
```

```text
$DELAY=1
$SAMPLES=3
$DISK=sda
$PID=
$IFACE=eth0
!! stvars[1]
!! oload[1]
```

---

## vmstat (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `vmstat` | Один снимок |
| 2 | `vmstat -s` | Сводка памяти |
| 3 | `vmstat -d` | Диск |
| 4 | `vmstat $DELAY $SAMPLES` | N сэмплов |
| 5 | `vmstat -w $DELAY $SAMPLES` | Широкие колонки |

---

## iostat (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `iostat -y` | Один снимок |
| 2 | `iostat -xz $DELAY $SAMPLES` | Extended |
| 3 | `iostat -xz $DISK $DELAY $SAMPLES` | Диск `$DISK` |
| 4 | `iostat -N -xz $DELAY $SAMPLES` | С LVM-именами |

---

## mpstat (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `mpstat` | Один снимок |
| 2 | `mpstat -P ALL $DELAY $SAMPLES` | Все CPU |
| 3 | `pidstat $DELAY $SAMPLES` | Процессы |
| 4 | `pidstat -p $PID $DELAY $SAMPLES` | PID `$PID` |
| 5 | `sar -u $DELAY $SAMPLES` | CPU через sar |

---

## monui — TTY

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `> htop` | htop |
| 2 | `> iotop` | iotop |
| 3 | `> iftop -i $IFACE` | iftop |

---

## Плейбуки

| Тег | Цепочка |
|-----|---------|
| `oload[1]` | `vmstat N` → `iostat -xz N` |

```text
!! oload[1]
> htop
```
