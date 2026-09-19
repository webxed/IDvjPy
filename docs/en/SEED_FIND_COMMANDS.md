# find handbook for IDvjPy

Tag **`find`**. Playbook **`fchk`**: files by glob + counter.  
`-delete` exists as `find[16]`, not part of the chain.

The Linux `file` tag is not overwritten by this seed. `$PATTERN` here is a **glob** for `-name` (`*.log`), not a grep regexp.

```bash
python3 src/seed_find.py --seed
# or together with the other ops:
python3 src/seed_ops.py --seed
```

```text
$SRC=.
$PATTERN='*.log'
$DAYS=7
$SIZE=100M
!! fvars[1]
```

GNU `find` (`-printf`). On a large tree prefer `find[13]` (`head`) or `find[15]` (`prune`).

---

## find — commands (tid)

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `find "$SRC" -type f` | Files |
| 2 | `find "$SRC" -type d` | Directories |
| 3 | `find "$SRC" -name "$PATTERN"` | Glob |
| 4 | `find "$SRC" -iname "$PATTERN"` | Case-insensitive glob |
| 5 | `find "$SRC" -type f -name "$PATTERN"` | Files by glob |
| 6 | `find "$SRC" -mtime -$DAYS` | Modified less than `$DAYS` days ago |
| 7 | `find "$SRC" -mtime +$DAYS` | Older than `$DAYS` days |
| 8 | `find "$SRC" -size +$SIZE` | Larger than `$SIZE` (e.g. 100M) |
| 9 | `find "$SRC" -empty` | Empty files and directories |
| 10 | `find "$SRC" -type l` | Symlinks |
| 11 | `find "$SRC" -name "$PATTERN" -ls` | Like `ls -dils` |
| 12 | `find … -printf '%s %p\n' \| sort \| tail` | 20 largest files |
| 13 | `find … -name "$PATTERN" \| head -n 50` | First 50 paths |
| 14 | `find … -name "$PATTERN" \| wc -l` | How many files |
| 15 | `find … -prune -o … -print` | Search without `.git`/`.venv`/`node_modules` |
| 16 | `find … -delete` | Delete found (not in playbook) |

---

## Playbooks

| Tag | Chain |
|-----|---------|
| `fchk[1]` | `type f -name` → `wc -l` |

```text
$SRC=.
$PATTERN='*.py'
!! fchk[1]
$DAYS=1
!! find[6]
```
