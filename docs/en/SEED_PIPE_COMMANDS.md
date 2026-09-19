# Pipeline handbook for IDvjPy

Tags **`sort`**, **`uniq`**, **`cut`**, **`tr`**, **`wc`**, **`xargs`**, **`jq`**.  
`tee` writes to disk — not in the playbook. Handy as `| sort -u` from a journal block or `!! sort[2]`.

Does not touch `grep` / `awk` / `sed` (`seed_text.py`).

```bash
python3 src/seed_pipe.py --seed
# or together with the other ops:
python3 src/seed_ops.py --seed
```

```text
$FILE=data.txt
$SEP=,
$N=1
$DEST=/tmp/out.txt
$JSON=.
!! pvars[1]
```

`$JSON` — a jq path from the JSON viewer (F5, Enter). For a pipe, leave `$FILE` empty and use `| jq .`.

---

## sort / uniq / cut (tid)

**sort:** 1 lexicographic · 2 `-u` · 3 `-n` · 4 `-h` · 5 `-r` · 6 `-nr` · 7 `-k $N` · 8 `-t $SEP -k $N` · 9 unique by field

**uniq:** 1 squeeze consecutive · 2 counter · 3 duplicates only · 4 unique only · 5 `sort | uniq -c | sort -nr`

`uniq` looks only at **adjacent** lines — before `-c` almost always `sort`.

**cut:** 1 field `$N` · 2 fields 1 and `$N` · 3 fields 1–3 · 4 first 80 characters · 5 all fields except `$N`

---

## tr / wc / xargs / jq

**tr** reads stdin (`< $FILE`). In a pipe: `| tr -d '\r'`.

**wc:** `-l` / `-w` / `-c` / `-lwm` / `-L`.

**xargs:** `-a $FILE` (GNU). `-P` runs commands — not in the playbook.

**jq:** `.` · `-c` · `-r` · `keys` · `length` · `type` · `$JSON` · raw `$JSON` · valid JSON?

**tee:** `tee $DEST` / `tee -a $DEST` — change the file.

---

## Playbooks

| Tag | Chain |
|-----|---------|
| `ucount[1]` | `sort \| uniq -c \| sort -nr` |
| `jprev[1]` | jq keys → length → type |

```text
$FILE=access.log
!! ucount[1]
$FILE=demo.json
!! jprev[1]
| jq -r .cc
```
