# sysstat handbook for IDvjPy

Tags **`vmstat`**, **`iostat`**, **`mpstat`**. Playbook **`oload`**.  
Snapshots are finite: `$DELAY` × `$SAMPLES`. `htop` / `iotop` / `iftop` — tag `monui`, `>` only.

Does not touch the linux `proc` and systemd `sstat` tags.

```bash
python3 src/seed_sysstat.py --seed
# or together with the other ops:
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

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `vmstat` | One snapshot |
| 2 | `vmstat -s` | Memory summary |
| 3 | `vmstat -d` | Disk |
| 4 | `vmstat $DELAY $SAMPLES` | Every `$DELAY` s, `$SAMPLES` times |
| 5 | `vmstat -w $DELAY $SAMPLES` | Wide columns |

---

## iostat (tid)

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `iostat -y` | One snapshot (no avg-since-boot) |
| 2 | `iostat -xz $DELAY $SAMPLES` | Extended, `$SAMPLES` times |
| 3 | `iostat -xz $DISK $DELAY $SAMPLES` | Disk `$DISK` |
| 4 | `iostat -N -xz $DELAY $SAMPLES` | With LVM names |

---

## mpstat (tid)

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `mpstat` | One snapshot |
| 2 | `mpstat -P ALL $DELAY $SAMPLES` | All CPUs |
| 3 | `pidstat $DELAY $SAMPLES` | Processes |
| 4 | `pidstat -p $PID $DELAY $SAMPLES` | PID `$PID` |
| 5 | `sar -u $DELAY $SAMPLES` | CPU via sar |

---

## monui — TTY

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `> htop` | htop |
| 2 | `> iotop` | iotop |
| 3 | `> iftop -i $IFACE` | iftop |

---

## Playbooks

| Tag | Chain |
|-----|---------|
| `oload[1]` | `vmstat N` → `iostat -xz N` |

```text
!! oload[1]
> htop
```
