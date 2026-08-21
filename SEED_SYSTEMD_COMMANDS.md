# Справочник systemd для IDvjPy

Теги **`sctl`** (systemctl), **`jctl`** (journalctl), **`dmesg`**.  
Плейбуки осмотра: `sfail`, `sstat`, `kmsg`. `start` / `stop` / `restart` / `reload` — только руками.

`--no-pager` везде, где иначе откроется `less`. Follow (`-f` / `-w`) лучше через `> cmd`. Часть команд нужна root.

```bash
python3 src/seed_systemd.py --seed
# или вместе с остальными ops:
python3 src/seed_ops.py --seed
```

Не трогает linux-теги `proc` / `file` / `logs`. Не путать `sctl` с ядровым `sysctl`.

```text
$UNIT=nginx.service
$SINCE=1 hour ago
$BOOT=0
!! sysvars[1]
```

`$BOOT`: `0` — текущая загрузка, `-1` — предыдущая.

---

## sctl — systemctl (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `systemctl --no-pager --failed` | Упавшие units |
| 2 | `list-units --type=service --state=failed` | Failed services |
| 3 | `systemctl --no-pager status $UNIT` | Статус `$UNIT` |
| 4 | `systemctl show $UNIT --no-pager` | Свойства |
| 5 | `systemctl cat $UNIT --no-pager` | Unit-файл |
| 6 | `systemctl is-active $UNIT` | active / inactive |
| 7 | `systemctl is-enabled $UNIT` | enabled / disabled |
| 8 | `list-units --type=service --state=running` | Запущенные services |
| 9 | `systemctl list-timers --all --no-pager` | Таймеры |
| 10 | `systemctl daemon-reload` | Перечитать unit-файлы |
| 11 | `systemctl reload $UNIT` | Reload (меняет сервис) |
| 12 | `systemctl restart $UNIT` | Restart (меняет сервис) |
| 13 | `systemctl start $UNIT` | Start |
| 14 | `systemctl stop $UNIT` | Stop |
| 15 | `systemctl reset-failed $UNIT` | Сбросить failed |

В плейбуках нет tid 10–15.

---

## jctl — journalctl (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `journalctl --no-pager -n 80` | Хвост журнала |
| 2 | `-p err -n 80` | Ошибки |
| 3 | `-u $UNIT -n 100` | Журнал `$UNIT` |
| 4 | `-u $UNIT -p err` | Ошибки `$UNIT` |
| 5 | `-u $UNIT --since "$SINCE"` | С `$SINCE` |
| 6 | `--list-boots` | Загрузки |
| 7 | `-b $BOOT -n 80` | Журнал загрузки `$BOOT` |
| 8 | `-k -n 80` | Ядро |
| 9 | `--disk-usage` | Место журнала |
| 10 | `-u $UNIT -o json-pretty -n 20` | JSON → F5 |
| 11 | `journalctl -f -u $UNIT` | Follow (`> journalctl -f …`) |

---

## dmesg (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `dmesg --color=never \| tail -n 80` | Хвост буфера |
| 2 | `dmesg -T --color=never \| tail -n 80` | С временем |
| 3 | `dmesg -T --level=err,warn` | err + warn |
| 4 | `dmesg -T --level=err` | Только err |
| 5 | `dmesg -w` | Follow (`> dmesg -w`) |

---

## Плейбуки

| Тег | Цепочка |
|-----|---------|
| `sfail[1]` | `--failed` → list-units failed |
| `sstat[1]` | status `$UNIT` → is-active → journal `-u` |
| `kmsg[1]` | dmesg err/warn → `journalctl -k` |

```text
!! sfail[1]
$UNIT=nginx.service
!! sstat[1]
!! kmsg[1]
```
