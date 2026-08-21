# Справочник хоста: tar / gzip / zip

Теги **`tar`**, **`gz`**, **`zip`**. Плейбуки **`tstat`** / **`zstat`** осматривают архив, без распаковки в `/`.

Диски и место: [`SEED_DISK_COMMANDS.md`](SEED_DISK_COMMANDS.md) (`python3 src/seed_disk.py --seed`).

```bash
python3 src/seed_host.py --seed
```

Не трогает linux-тег `file` и disk-теги (`df` / `smart` / …).

```text
$SRC=.
$DEST=backup.tar.gz
$ARCHIVE=backup.tar.gz
$PATTERN=error
!! avars[1]
```

---

## tar (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `tar -tf $ARCHIVE` | Список файлов |
| 2 | `tar -tzf $ARCHIVE` | Список `.tar.gz` |
| 3 | `tar -tvf $ARCHIVE \| head` | Список с правами |
| 4 | `tar -czvf $DEST $SRC` | Упаковать |
| 5 | `tar -czvf $DEST --exclude='.git' $SRC` | Без `.git` |
| 6 | `tar -xzvf $ARCHIVE` | Распаковать в cwd |
| 7 | `tar -xzvf $ARCHIVE -C $DEST` | Распаковать в `$DEST` |
| 8 | `tar -df $ARCHIVE $SRC` | Сравнить с деревом |

`6`–`7` перезаписывают файлы — не в плейбуке.

---

## gz — gzip (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `gzip -l $ARCHIVE` | Размер / коэффициент |
| 2 | `gzip -dk $ARCHIVE` | Распаковать, оставить `.gz` |
| 3 | `gunzip -c $ARCHIVE \| head` | Первые строки |
| 4 | `zcat $ARCHIVE \| head` | То же |
| 5 | `gzip -k $SRC` | Сжать, оставить исходник |
| 6 | `zgrep -n $PATTERN $ARCHIVE` | grep внутри `.gz` |

---

## zip (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `zipinfo $ARCHIVE` | Список и права |
| 2 | `unzip -l $ARCHIVE` | Список файлов |
| 3 | `unzip -v $ARCHIVE` | Подробный список |
| 4 | `zip -r $DEST $SRC` | Упаковать |
| 5 | `unzip $ARCHIVE` | Распаковать в cwd |
| 6 | `unzip $ARCHIVE -d $DEST` | Распаковать в `$DEST` |
| 7 | `zipgrep $PATTERN $ARCHIVE` | grep внутри `.zip` |

`5`–`6` перезаписывают файлы — не в плейбуке.

---

## Плейбуки

| Тег | Цепочка |
|-----|---------|
| `tstat[1]` | `tar -tzf` + `gzip -l` |
| `zstat[1]` | `zipinfo` + `unzip -l` |

```text
$ARCHIVE=backup.tar.gz
!! tstat[1]
$ARCHIVE=backup.zip
!! zstat[1]
```
