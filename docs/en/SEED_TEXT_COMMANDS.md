# Text handbook: grep, awk, sed

Tags **`grep`**, **`awk`**, **`sed`**. Playbooks write to stdout.  
`sed -i` exists as `sed[13]`, not part of the chains.

The linux tag `file` (`cat`/`head`/`tail`) is not overwritten by this seed.

```bash
python3 src/seed_text.py --seed
# or together with the rest of ops:
python3 src/seed_ops.py --seed
```

```text
$FILE=
$PATTERN=
$REPL=
$SEP=,
$N=1
!! tvars[1]
```

For `sed s/$PATTERN/$REPL/` there must be no unescaped `/` in `$PATTERN` and `$REPL`. Another delimiter: change the command to `s|$PATTERN|$REPL|g`.

---

## grep (tid)

| tid | Command | Purpose |
|-----|---------|---------|
| 1 | `grep -n $PATTERN $FILE` | Lines with numbers |
| 2 | `grep -ni $PATTERN $FILE` | Case-insensitive |
| 3 | `grep -nv $PATTERN $FILE` | Inverted filter |
| 4 | `grep -nc $PATTERN $FILE` | Match count |
| 5 | `grep -nE $PATTERN $FILE` | ERE |
| 6 | `grep -nF $PATTERN $FILE` | Fixed string |
| 7 | `grep -nC 3 $PATTERN $FILE` | Context ±3 |
| 8 | `grep -nA 5 $PATTERN $FILE` | 5 lines after |
| 9 | `grep -nB 5 $PATTERN $FILE` | 5 lines before |
| 10 | `grep -oE $PATTERN $FILE` | Matches only |
| 11 | `grep -nH $PATTERN $FILE` | With filename |
| 12 | `grep -l $PATTERN $FILE` | Filename on a hit |
| 13 | `grep -Rn --exclude-dir=.git --exclude-dir=.venv $PATTERN .` | Recursive |
| 14 | `zgrep -n $PATTERN $FILE` | Search in `.gz` |

---

## awk (tid)

| tid | Command | Purpose |
|-----|---------|---------|
| 1 | `awk '{print $1}' $FILE` | First field |
| 2 | `awk -F "$SEP" '{print $1}' $FILE` | First field, FS=`$SEP` |
| 3 | `awk -F "$SEP" '{print $1,$NF}' $FILE` | First and last |
| 4 | `awk '{print NR, $0}' $FILE` | Line number |
| 5 | `awk 'NR==1 {print}' $FILE` | Header |
| 6 | `awk -v n="$N" 'NR==n {print}' $FILE` | Line `$N` |
| 7 | `awk 'NF' $FILE` | Without empty lines |
| 8 | `awk '!seen[$0]++' $FILE` | Unique |
| 9 | `awk '{s+=$1} END {print s}' $FILE` | Sum of field 1 |
| 10 | `awk -v p="$PATTERN" '$0 ~ p {print NR, $0}' $FILE` | Filter by `$PATTERN` |
| 11 | `awk -F "$SEP" '{print NF}' $FILE` | Field count |
| 12 | `awk 'END {print NR}' $FILE` | Line count |

---

## sed (tid)

| tid | Command | Purpose |
|-----|---------|---------|
| 1 | `sed -n '1,20p' $FILE` | First 20 lines |
| 2 | `sed -n "$N"p $FILE` | Line `$N` |
| 3 | `sed -n "/$PATTERN/p" $FILE` | Lines by regexp |
| 4 | `sed "s/$PATTERN/$REPL/" $FILE` | First replacement per line |
| 5 | `sed "s/$PATTERN/$REPL/g" $FILE` | All replacements |
| 6 | `sed "s/$PATTERN/$REPL/gI" $FILE` | Case-insensitive |
| 7 | `sed -n "s/$PATTERN/$REPL/gp" $FILE` | Changed lines only |
| 8 | `sed '/^$/d' $FILE` | Drop empty lines |
| 9 | `sed 's/[[:space:]]*$//' $FILE` | Trim trailing |
| 10 | `sed 's/\r$//' $FILE` | CRLF → LF (stdout) |
| 11 | `sed '1d' $FILE` | Without first |
| 12 | `sed '$d' $FILE` | Without last |
| 13 | `sed -i.bak "s/$PATTERN/$REPL/g" $FILE` | Edit file + `.bak` |

---

## Playbooks

| Tag | Chain |
|-----|-------|
| `gchk[1]` | `grep -n` + `grep -c` |
| `sprev[1]` | `s///g` to stdout + lines by `$PATTERN` |

```text
$FILE=app.py
$PATTERN=TODO
!! gchk[1]
$SEP=,
!! awk[2]
$PATTERN=foo
$REPL=bar
!! sprev[1]
```
