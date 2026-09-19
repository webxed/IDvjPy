# IDvjPy 磁盘手册：df、du、mount、fdisk、lsblk、smartctl、ncdu

playbook **`dsk`**（概览）和 **`dustat`**（目录占用）— 仅检查。  
不在命令链中：`mkfs`、交互式的 `fdisk`、`wipefs -a`、`umount`。

`smartctl` / `fdisk -l` 通常需要 root。磁盘名来自 `lsblk` / `smartctl --scan` / `/dev/disk/by-id`。

`ncdu` — 交互式 TUI：`> ncdu "$SRC"`。

不触碰 Linux 标签 `file` 和 host 标签 `tar` / `gz`。

```bash
python3 src/seed_disk.py --seed
# 或连同其他 ops：
python3 src/seed_ops.py --seed
```

```text
$DISK=/dev/sda
$MNT=/
$SRC=.
!! dkvars[1]
```

`$MNT` — 挂载点（不要与 helm/vault 的 `$MOUNT` 混淆）。

---

## df (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `df -h` | 人类可读 |
| 2 | `df -hT` | 带 FS 类型 |
| 3 | `df -i` | inode |
| 4 | `df -h $MNT` | `$MNT` 挂载点 |
| 5 | `df -h --output=source,fstype,…` | source/fstype/… 列 |

---

## du (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `du -sh "$SRC"` | `$SRC` 总计 |
| 2 | `du -h --max-depth=1 "$SRC"` | 一层深度 |
| 3 | `du -h --max-depth=1 "$SRC" \| sort -h` | 同上，按大小排序 |
| 4 | `du -x -sh "$SRC"` | 不跨文件系统 |
| 5 | `du -h --max-depth=2 … \| tail` | 深度 2，最大在前 |

---

## mount (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `findmnt` | 挂载树 |
| 2 | `findmnt -A` | 全部包括 API FS |
| 3 | `findmnt $MNT` | `$MNT` 挂载点 |
| 4 | `mount` | 挂载表 |
| 5 | `cat /proc/mounts` | `/proc/mounts` |
| 6 | `findmnt -T $MNT` | 包含路径 `$MNT` 的 FS |
| 7 | `mount $DISK $MNT` | 挂载（会改动系统） |
| 8 | `umount $MNT` | 卸载（会改动系统） |

---

## fdisk (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `fdisk -l` | 所有磁盘 |
| 2 | `fdisk -l $DISK` | `$DISK` 分区 |
| 3 | `sfdisk -d $DISK` | `$DISK` 表转储 |
| 4 | `wipefs $DISK` | `$DISK` 上的签名（无 `-a`） |

---

## lsblk (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `lsblk` | 设备树 |
| 2 | `lsblk -f` | FS 和 UUID |
| 3 | `lsblk -o NAME,SIZE,TYPE,…` | 大小、FS、型号 |
| 4 | `lsblk -p` | 完整 `/dev/…` 路径 |
| 5 | `lsblk $DISK` | 仅 `$DISK` |
| 6 | `ls -l /dev/disk/by-id` | 稳定名称 |

---

## smart — smartctl (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `smartctl --scan` | SMART 设备 |
| 2 | `smartctl -i $DISK` | 识别 `$DISK` |
| 3 | `smartctl -H $DISK` | 总体健康 |
| 4 | `smartctl -A $DISK` | SMART 属性 |
| 5 | `smartctl -a $DISK` | 完整报告 |
| 6 | `smartctl -l error $DISK` | 错误日志 |
| 7 | `smartctl -l selftest $DISK` | 自检历史 |
| 8 | `smartctl -x $DISK` | 扩展报告 |

---

## ncdu (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `ncdu "$SRC"` | 交互式（更好: `> ncdu "$SRC"`） |
| 2 | `ncdu -x "$SRC"` | 单一文件系统（`> ncdu -x …`） |

---

## playbook

| 标签 | 命令链 |
|-----|---------|
| `dsk[1]` | lsblk → df -h → smartctl --scan → `-H $DISK` |
| `dustat[1]` | `du --max-depth=1` → `sort -h` |

```text
!! dsk[1]
$SRC=/var
!! dustat[1]
$DISK=/dev/disk/by-id/ata-…
!! smart[3]
> ncdu /var
```
