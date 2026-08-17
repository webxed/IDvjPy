# Справочник текста: grep, awk, sed

Теги **`grep`**, **`awk`**, **`sed`**. Плейбуки пишут в stdout.  
`sed -i` есть как `sed[13]`, в цепочки не входит.

Linux-тег `file` (`cat`/`head`/`tail`) этот сид не затирает.

```bash
python3 src/seed_text.py --seed
# или вместе с остальными ops:
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

Для `sed s/$PATTERN/$REPL/` в `$PATTERN` и `$REPL` не должно быть неэкранированных `/`. Другой разделитель: поправить команду на `s|$PATTERN|$REPL|g`.

---

## grep (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `grep -n $PATTERN $FILE` | Строки с номерами |
| 2 | `grep -ni $PATTERN $FILE` | Без регистра |
| 3 | `grep -nv $PATTERN $FILE` | Обратный фильтр |
| 4 | `grep -nc $PATTERN $FILE` | Число совпадений |
| 5 | `grep -nE $PATTERN $FILE` | ERE |
| 6 | `grep -nF $PATTERN $FILE` | Фиксированная строка |
| 7 | `grep -nC 3 $PATTERN $FILE` | Контекст ±3 |
| 8 | `grep -nA 5 $PATTERN $FILE` | 5 строк после |
| 9 | `grep -nB 5 $PATTERN $FILE` | 5 строк до |
| 10 | `grep -oE $PATTERN $FILE` | Только совпадения |
| 11 | `grep -nH $PATTERN $FILE` | С именем файла |
| 12 | `grep -l $PATTERN $FILE` | Имя файла при hit |
| 13 | `grep -Rn --exclude-dir=.git --exclude-dir=.venv $PATTERN .` | Рекурсивно |
| 14 | `zgrep -n $PATTERN $FILE` | Поиск в `.gz` |

---

## awk (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `awk '{print $1}' $FILE` | Первое поле |
| 2 | `awk -F "$SEP" '{print $1}' $FILE` | Первое поле, FS=`$SEP` |
| 3 | `awk -F "$SEP" '{print $1,$NF}' $FILE` | Первое и последнее |
| 4 | `awk '{print NR, $0}' $FILE` | Номер строки |
| 5 | `awk 'NR==1 {print}' $FILE` | Заголовок |
| 6 | `awk -v n="$N" 'NR==n {print}' $FILE` | Строка `$N` |
| 7 | `awk 'NF' $FILE` | Без пустых |
| 8 | `awk '!seen[$0]++' $FILE` | Уникальные |
| 9 | `awk '{s+=$1} END {print s}' $FILE` | Сумма поля 1 |
| 10 | `awk -v p="$PATTERN" '$0 ~ p {print NR, $0}' $FILE` | Фильтр по `$PATTERN` |
| 11 | `awk -F "$SEP" '{print NF}' $FILE` | Число полей |
| 12 | `awk 'END {print NR}' $FILE` | Число строк |

---

## sed (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `sed -n '1,20p' $FILE` | Первые 20 строк |
| 2 | `sed -n "$N"p $FILE` | Строка `$N` |
| 3 | `sed -n "/$PATTERN/p" $FILE` | Строки по regexp |
| 4 | `sed "s/$PATTERN/$REPL/" $FILE` | Первая замена в строке |
| 5 | `sed "s/$PATTERN/$REPL/g" $FILE` | Все замены |
| 6 | `sed "s/$PATTERN/$REPL/gI" $FILE` | Без регистра |
| 7 | `sed -n "s/$PATTERN/$REPL/gp" $FILE` | Только изменённые |
| 8 | `sed '/^$/d' $FILE` | Убрать пустые |
| 9 | `sed 's/[[:space:]]*$//' $FILE` | Trim справа |
| 10 | `sed 's/\r$//' $FILE` | CRLF → LF (stdout) |
| 11 | `sed '1d' $FILE` | Без первой |
| 12 | `sed '$d' $FILE` | Без последней |
| 13 | `sed -i.bak "s/$PATTERN/$REPL/g" $FILE` | Правка файла + `.bak` |

---

## Плейбуки

| Тег | Цепочка |
|-----|---------|
| `gchk[1]` | `grep -n` + `grep -c` |
| `sprev[1]` | `s///g` в stdout + строки по `$PATTERN` |

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
