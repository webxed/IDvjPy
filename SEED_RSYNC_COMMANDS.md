# Справочник rsync для IDvjPy

Тег **`rsync`**. Плейбук **`rchk`**: list-only + dry-run (без `--delete`).

Базовый `rsync -avz` уже есть в linux-теге `net[6]` — этот сид его не затирает.

Слеш в конце `$SRC` важен: `dir/` копирует *содержимое*, `dir` — сам каталог.

```bash
python3 src/seed_rsync.py --seed
# или вместе с остальными ops:
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

## rsync — команды (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `rsync --list-only "$SRC"` | Список источника |
| 2 | `rsync -avn "$SRC" "$DEST"` | Dry-run |
| 3 | `rsync -avni "$SRC" "$DEST"` | Dry-run + itemize |
| 4 | `rsync -avzn --delete "$SRC" "$DEST"` | Dry-run с `--delete` |
| 5 | `rsync -avzn --exclude="$EXCL" …` | Dry-run с exclude |
| 6 | `rsync -avn "$SRC" "$REMOTE:$DEST"` | Dry-run на `$REMOTE` |
| 7 | `rsync -avn "$REMOTE:$SRC" "$DEST"` | Dry-run с `$REMOTE` |
| 8 | `rsync -av "$SRC" "$DEST"` | Локальная копия |
| 9 | `rsync -avz "$SRC" "$DEST"` | Со сжатием |
| 10 | `rsync -avzP "$SRC" "$DEST"` | Progress + partial |
| 11 | `rsync -avz --exclude="$EXCL" …` | Копия с exclude |
| 12 | `rsync -avz "$SRC" "$REMOTE:$DEST"` | На `$REMOTE` |
| 13 | `rsync -avz "$REMOTE:$SRC" "$DEST"` | С `$REMOTE` |
| 14 | `rsync -avz --bwlimit=5000 …` | Лимит ~5 MB/s |
| 15 | `rsync -avz --delete "$SRC" "$DEST"` | Копия + удалить лишнее на dest |

`--delete` (tid 15) и даже его dry-run (tid 4) не входят в `rchk`. Сначала `!! rchk[1]`, потом `!rsync[4]` если нужно увидеть удаления.

SSH: нужен ключ/агент. Интерактивный пароль — `> rsync …`.

---

## Плейбуки

| Тег | Цепочка |
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
