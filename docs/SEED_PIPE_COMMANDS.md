# Справочник конвейера для IDvjPy

Теги **`sort`**, **`uniq`**, **`cut`**, **`tr`**, **`wc`**, **`xargs`**, **`jq`**.  
`tee` пишет на диск — не в плейбуке. Удобно как `| sort -u` с блока журнала или `!! sort[2]`.

Не трогает `grep` / `awk` / `sed` (`seed_text.py`).

```bash
python3 src/seed_pipe.py --seed
# или вместе с остальными ops:
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

`$JSON` — jq-path из JSON viewer (F5, Enter). Для пайпа оставьте `$FILE` пустым и используйте `| jq .`.

---

## sort / uniq / cut (tid)

**sort:** 1 обычный · 2 `-u` · 3 `-n` · 4 `-h` · 5 `-r` · 6 `-nr` · 7 `-k $N` · 8 `-t $SEP -k $N` · 9 уникальные по полю

**uniq:** 1 сжать · 2 `-c` · 3 `-d` · 4 `-u` · 5 `sort | uniq -c | sort -nr`

`uniq` смотрит только **соседние** строки — перед `-c` почти всегда `sort`.

**cut:** 1 поле `$N` · 2 поля 1 и `$N` · 3 поля 1–3 · 4 символы 1–80 · 5 все кроме `$N`

---

## tr / wc / xargs / jq

**tr** читает stdin (`< $FILE`). В пайпе: `| tr -d '\r'`.

**wc:** `-l` / `-w` / `-c` / `-lwm` / `-L`.

**xargs:** `-a $FILE` (GNU). `-P` запускает команды — в плейбуке нет.

**jq:** `.` · `-c` · `-r` · `keys` · `length` · `type` · `$JSON` · raw `$JSON` · проверка JSON.

**tee:** `tee $DEST` / `tee -a $DEST` — меняют файл.

---

## Плейбуки

| Тег | Цепочка |
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
