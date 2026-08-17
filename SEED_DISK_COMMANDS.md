# Справочник дисков: df, du, mount, fdisk, lsblk, smartctl, ncdu

Плейбуки **`dsk`** (обзор) и **`dustat`** (место в каталоге) — только осмотр.  
Нет в цепочках: `mkfs`, `fdisk` в интерактиве, `wipefs -a`, `umount`.

`smartctl` / `fdisk -l` обычно нужен root. Имя диска — из `lsblk` / `smartctl --scan` / `/dev/disk/by-id`.

`ncdu` — интерактивный TUI: `> ncdu "$SRC"`.

Не трогает linux-тег `file` и host-теги `tar` / `gz`.

```bash
python3 src/seed_disk.py --seed
# или вместе с остальными ops:
python3 src/seed_ops.py --seed
```

```text
$DISK=/dev/sda
$MNT=/
$SRC=.
!! dkvars[1]
```

`$MNT` — точка монтирования (не путать с helm/vault `$MOUNT`).

---

## df (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `df -h` | Человекочитаемо |
| 2 | `df -hT` | С типом FS |
| 3 | `df -i` | Inode |
| 4 | `df -h $MNT` | Точка `$MNT` |
| 5 | `df -h --output=source,fstype,…` | Колонки |

---

## du (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `du -sh "$SRC"` | Итог |
| 2 | `du -h --max-depth=1 "$SRC"` | Один уровень |
| 3 | `du -h --max-depth=1 "$SRC" \| sort -h` | По размеру |
| 4 | `du -x -sh "$SRC"` | Одна FS |
| 5 | `du -h --max-depth=2 … \| tail` | Глубина 2 |

---

## mount (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `findmnt` | Дерево |
| 2 | `findmnt -A` | Все, включая API FS |
| 3 | `findmnt $MNT` | Точка `$MNT` |
| 4 | `mount` | Таблица mount |
| 5 | `cat /proc/mounts` | `/proc/mounts` |
| 6 | `findmnt -T $MNT` | FS пути `$MNT` |
| 7 | `mount $DISK $MNT` | Смонтировать |
| 8 | `umount $MNT` | Размонтировать |

---

## fdisk (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `fdisk -l` | Все диски |
| 2 | `fdisk -l $DISK` | `$DISK` |
| 3 | `sfdisk -d $DISK` | Дамп таблицы |
| 4 | `wipefs $DISK` | Сигнатуры (без `-a`) |

---

## lsblk (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `lsblk` | Дерево |
| 2 | `lsblk -f` | FS / UUID |
| 3 | `lsblk -o NAME,SIZE,TYPE,…` | Модель, серийник |
| 4 | `lsblk -p` | Полные пути |
| 5 | `lsblk $DISK` | Один диск |
| 6 | `ls -l /dev/disk/by-id` | Стабильные имена |

---

## smart — smartctl (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `smartctl --scan` | Устройства |
| 2 | `smartctl -i $DISK` | Идентификация |
| 3 | `smartctl -H $DISK` | Overall health |
| 4 | `smartctl -A $DISK` | Атрибуты |
| 5 | `smartctl -a $DISK` | Полный отчёт |
| 6 | `smartctl -l error $DISK` | Лог ошибок |
| 7 | `smartctl -l selftest $DISK` | Self-test |
| 8 | `smartctl -x $DISK` | Расширенный отчёт |

---

## ncdu (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `ncdu "$SRC"` | Интерактив (`> ncdu "$SRC"`) |
| 2 | `ncdu -x "$SRC"` | Одна FS |

---

## Плейбуки

| Тег | Цепочка |
|-----|---------|
| `dsk[1]` | lsblk → df -h → smartctl --scan → `-H $DISK` |
| `dustat[1]` | `du --max-depth=1` → `sort -h` |

```text
!! dsk[1]
$SRC=/var
!! dustat[1]
$DISK=/dev/disk/by-id/ata-…
!! smart[3]
> ncdu /var
```
