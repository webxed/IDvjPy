# Host handbook: tar / gzip / zip

Tags **`tar`**, **`gz`**, **`zip`**. Playbooks **`tstat`** / **`zstat`** inspect an archive, without unpacking into `/`.

Disks and space: [`SEED_DISK_COMMANDS.md`](SEED_DISK_COMMANDS.md) (`python3 src/seed_disk.py --seed`).

```bash
python3 src/seed_host.py --seed
```

Does not touch the linux tag `file` or the disk tags (`df` / `smart` / …).

```text
$SRC=.
$DEST=backup.tar.gz
$ARCHIVE=backup.tar.gz
$PATTERN=error
!! avars[1]
```

---

## tar (tid)

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `tar -tf $ARCHIVE` | List files |
| 2 | `tar -tzf $ARCHIVE` | List `.tar.gz` |
| 3 | `tar -tvf $ARCHIVE \| head` | List with permissions |
| 4 | `tar -czvf $DEST $SRC` | Pack |
| 5 | `tar -czvf $DEST --exclude='.git' $SRC` | Without `.git` |
| 6 | `tar -xzvf $ARCHIVE` | Extract to cwd |
| 7 | `tar -xzvf $ARCHIVE -C $DEST` | Extract to `$DEST` |
| 8 | `tar -df $ARCHIVE $SRC` | Compare with tree |

`6`–`7` overwrite files — not in the playbook.

---

## gz — gzip (tid)

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `gzip -l $ARCHIVE` | Size / ratio |
| 2 | `gzip -dk $ARCHIVE` | Decompress, keep `.gz` |
| 3 | `gunzip -c $ARCHIVE \| head` | First lines |
| 4 | `zcat $ARCHIVE \| head` | Same |
| 5 | `gzip -k $SRC` | Compress, keep source |
| 6 | `zgrep -n $PATTERN $ARCHIVE` | grep inside `.gz` |

---

## zip (tid)

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `zipinfo $ARCHIVE` | List and permissions |
| 2 | `unzip -l $ARCHIVE` | List files |
| 3 | `unzip -v $ARCHIVE` | Detailed listing |
| 4 | `zip -r $DEST $SRC` | Pack |
| 5 | `unzip $ARCHIVE` | Extract to cwd |
| 6 | `unzip $ARCHIVE -d $DEST` | Extract to `$DEST` |
| 7 | `zipgrep $PATTERN $ARCHIVE` | grep inside `.zip` |

`5`–`6` overwrite files — not in the playbook.

---

## Playbooks

| Tag | Chain |
|-----|---------|
| `tstat[1]` | `tar -tzf` + `gzip -l` |
| `zstat[1]` | `zipinfo` + `unzip -l` |

```text
$ARCHIVE=backup.tar.gz
!! tstat[1]
$ARCHIVE=backup.zip
!! zstat[1]
```
