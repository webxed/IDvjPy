# 面向 IDvjPy 的 sysstat 手册

标签 **`vmstat`**、**`iostat`**、**`mpstat`**。剧本 **`oload`**。  
快照是有限的：`$DELAY` × `$SAMPLES`。`htop` / `iotop` / `iftop` —— 标签 `monui`，只能用 `>`。

不改动 linux 的 `proc` 和 systemd 的 `sstat`。

```bash
python3 src/seed_sysstat.py --seed
# 或与其他 ops 一起：
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

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `vmstat` | 单次快照 |
| 2 | `vmstat -s` | 内存摘要 |
| 3 | `vmstat -d` | 磁盘 |
| 4 | `vmstat $DELAY $SAMPLES` | N 个采样 |
| 5 | `vmstat -w $DELAY $SAMPLES` | 宽列 |

---

## iostat (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `iostat -y` | 单次快照 |
| 2 | `iostat -xz $DELAY $SAMPLES` | Extended |
| 3 | `iostat -xz $DISK $DELAY $SAMPLES` | 磁盘 `$DISK` |
| 4 | `iostat -N -xz $DELAY $SAMPLES` | 带 LVM 名称 |

---

## mpstat (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `mpstat` | 单次快照 |
| 2 | `mpstat -P ALL $DELAY $SAMPLES` | 所有 CPU |
| 3 | `pidstat $DELAY $SAMPLES` | 进程 |
| 4 | `pidstat -p $PID $DELAY $SAMPLES` | PID `$PID` |
| 5 | `sar -u $DELAY $SAMPLES` | 通过 sar 查看 CPU |

---

## monui — TTY

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `> htop` | htop |
| 2 | `> iotop` | iotop |
| 3 | `> iftop -i $IFACE` | iftop |

---

## 剧本

| 标签 | 命令链 |
|-----|---------|
| `oload[1]` | `vmstat N` → `iostat -xz N` |

```text
!! oload[1]
> htop
```
