# rsync handbook for IDvjPy

Tag **`rsync`**. Playbook **`rchk`**: list-only + dry-run (without `--delete`).

The basic `rsync -avz` is already in the linux tag `net[6]` — this seed does not overwrite it.

The trailing slash on `$SRC` matters: `dir/` copies the *contents*, `dir` — the directory itself.

```bash
python3 src/seed_rsync.py --seed
# or together with the other ops:
python3 src/seed_ops.py --seed
```

```text
$SRC=./
$DEST=/backup/app/
$REMOTE=user@host
$EXCL=.git
!! rvars[1]
```

---

## rsync — commands (tid)

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `rsync --list-only "$SRC"` | List source |
| 2 | `rsync -avn "$SRC" "$DEST"` | Dry-run |
| 3 | `rsync -avni "$SRC" "$DEST"` | Dry-run + itemize |
| 4 | `rsync -avzn --delete "$SRC" "$DEST"` | Dry-run with `--delete` |
| 5 | `rsync -avzn --exclude="$EXCL" …` | Dry-run with exclude |
| 6 | `rsync -avn "$SRC" "$REMOTE:$DEST"` | Dry-run to `$REMOTE` |
| 7 | `rsync -avn "$REMOTE:$SRC" "$DEST"` | Dry-run from `$REMOTE` |
| 8 | `rsync -av "$SRC" "$DEST"` | Local copy |
| 9 | `rsync -avz "$SRC" "$DEST"` | With compression |
| 10 | `rsync -avzP "$SRC" "$DEST"` | Progress + partial |
| 11 | `rsync -avz --exclude="$EXCL" …` | Copy with exclude |
| 12 | `rsync -avz "$SRC" "$REMOTE:$DEST"` | To `$REMOTE` |
| 13 | `rsync -avz "$REMOTE:$SRC" "$DEST"` | From `$REMOTE` |
| 14 | `rsync -avz --bwlimit=5000 …` | Limit ~5 MB/s |
| 15 | `rsync -avz --delete "$SRC" "$DEST"` | Copy + delete extra on dest |

`--delete` (tid 15) and even its dry-run (tid 4) are not part of `rchk`. First `!! rchk[1]`, then `!rsync[4]` if you need to see the deletions.

SSH: a key/agent is required. Interactive password — `> rsync …`.

---

## Playbooks

| Tag | Chain |
|-----|---------|
| `rchk[1]` | list-only → `-avni` dry-run |

```text
$SRC=./
$DEST=/backup/app/
!! rchk[1]
$REMOTE=user@host
!! rsync[6]
!! rsync[12]
```
