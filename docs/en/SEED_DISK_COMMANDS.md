# Disk handbook: df, du, mount, fdisk, lsblk, smartctl, ncdu

Playbooks **`dsk`** (overview) and **`dustat`** (directory space) — inspection only.  
Not in the chains: `mkfs`, interactive `fdisk`, `wipefs -a`, `umount`.

`smartctl` / `fdisk -l` usually need root. The disk name comes from `lsblk` / `smartctl --scan` / `/dev/disk/by-id`.

`ncdu` — interactive TUI: `> ncdu "$SRC"`.

Does not touch the linux tag `file` and the host tags `tar` / `gz`.

```bash
python3 src/seed_disk.py --seed
# or together with the rest of ops:
python3 src/seed_ops.py --seed
```

```text
$DISK=/dev/sda
$MNT=/
$SRC=.
!! dkvars[1]
```

`$MNT` — mount point (not to be confused with the helm/vault `$MOUNT`).

---

## df (tid)

| tid | Command | Purpose |
|-----|---------|---------|
| 1 | `df -h` | Human-readable |
| 2 | `df -hT` | With FS type |
| 3 | `df -i` | Inode |
| 4 | `df -h $MNT` | `$MNT` point |
| 5 | `df -h --output=source,fstype,…` | Columns |

---

## du (tid)

| tid | Command | Purpose |
|-----|---------|---------|
| 1 | `du -sh "$SRC"` | Total |
| 2 | `du -h --max-depth=1 "$SRC"` | One level |
| 3 | `du -h --max-depth=1 "$SRC" \| sort -h` | By size |
| 4 | `du -x -sh "$SRC"` | One FS |
| 5 | `du -h --max-depth=2 … \| tail` | Depth 2 |

---

## mount (tid)

| tid | Command | Purpose |
|-----|---------|---------|
| 1 | `findmnt` | Tree |
| 2 | `findmnt -A` | All, including API FS |
| 3 | `findmnt $MNT` | `$MNT` point |
| 4 | `mount` | Mount table |
| 5 | `cat /proc/mounts` | `/proc/mounts` |
| 6 | `findmnt -T $MNT` | FS of path `$MNT` |
| 7 | `mount $DISK $MNT` | Mount |
| 8 | `umount $MNT` | Unmount |

---

## fdisk (tid)

| tid | Command | Purpose |
|-----|---------|---------|
| 1 | `fdisk -l` | All disks |
| 2 | `fdisk -l $DISK` | `$DISK` |
| 3 | `sfdisk -d $DISK` | Table dump |
| 4 | `wipefs $DISK` | Signatures (no `-a`) |

---

## lsblk (tid)

| tid | Command | Purpose |
|-----|---------|---------|
| 1 | `lsblk` | Tree |
| 2 | `lsblk -f` | FS / UUID |
| 3 | `lsblk -o NAME,SIZE,TYPE,…` | Model, serial |
| 4 | `lsblk -p` | Full paths |
| 5 | `lsblk $DISK` | Single disk |
| 6 | `ls -l /dev/disk/by-id` | Stable names |

---

## smart — smartctl (tid)

| tid | Command | Purpose |
|-----|---------|---------|
| 1 | `smartctl --scan` | Devices |
| 2 | `smartctl -i $DISK` | Identification |
| 3 | `smartctl -H $DISK` | Overall health |
| 4 | `smartctl -A $DISK` | Attributes |
| 5 | `smartctl -a $DISK` | Full report |
| 6 | `smartctl -l error $DISK` | Error log |
| 7 | `smartctl -l selftest $DISK` | Self-test |
| 8 | `smartctl -x $DISK` | Extended report |

---

## ncdu (tid)

| tid | Command | Purpose |
|-----|---------|---------|
| 1 | `ncdu "$SRC"` | Interactive (`> ncdu "$SRC"`) |
| 2 | `ncdu -x "$SRC"` | One FS |

---

## Playbooks

| Tag | Chain |
|-----|-------|
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
