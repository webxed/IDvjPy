# Справочник find для IDvjPy

Тег **`find`**. Плейбук **`fchk`**: файлы по glob + счётчик.  
`-delete` есть как `find[16]`, в цепочку не входит.

Linux-тег `file` этот сид не затирает. `$PATTERN` здесь — **glob** для `-name` (`*.log`), не regexp grep.

```bash
python3 src/seed_find.py --seed
# или вместе с остальными ops:
python3 src/seed_ops.py --seed
```

```text
$SRC=.
$PATTERN='*.log'
$DAYS=7
$SIZE=100M
!! fvars[1]
```

GNU `find` (`-printf`). На большом дереве лучше `find[13]` (`head`) или `find[15]` (prune).

---

## find — команды (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `find "$SRC" -type f` | Файлы |
| 2 | `find "$SRC" -type d` | Каталоги |
| 3 | `find "$SRC" -name "$PATTERN"` | Glob |
| 4 | `find "$SRC" -iname "$PATTERN"` | Glob без регистра |
| 5 | `find "$SRC" -type f -name "$PATTERN"` | Файлы по glob |
| 6 | `find "$SRC" -mtime -$DAYS` | Моложе `$DAYS` суток |
| 7 | `find "$SRC" -mtime +$DAYS` | Старше `$DAYS` суток |
| 8 | `find "$SRC" -size +$SIZE` | Больше `$SIZE` |
| 9 | `find "$SRC" -empty` | Пустые |
| 10 | `find "$SRC" -type l` | Симлинки |
| 11 | `find "$SRC" -name "$PATTERN" -ls` | Как `ls -dils` |
| 12 | `find … -printf '%s %p\n' \| sort \| tail` | 20 самых больших |
| 13 | `find … -name "$PATTERN" \| head -n 50` | Первые 50 |
| 14 | `find … -name "$PATTERN" \| wc -l` | Счётчик |
| 15 | `find … -prune -o … -print` | Без `.git` / `.venv` / `node_modules` |
| 16 | `find … -delete` | Удалить найденные |

---

## Плейбуки

| Тег | Цепочка |
|-----|---------|
| `fchk[1]` | `type f -name` → `wc -l` |

```text
$SRC=.
$PATTERN='*.py'
!! fchk[1]
$DAYS=1
!! find[6]
```
