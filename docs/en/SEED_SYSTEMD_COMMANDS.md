# systemd handbook for IDvjPy

Tags **`sctl`** (systemctl), **`jctl`** (journalctl), **`dmesg`**.  
Inspection playbooks: `sfail`, `sstat`, `kmsg`. `start` / `stop` / `restart` / `reload` — manual only.

`--no-pager` wherever `less` would otherwise open. Follow (`-f` / `-w`) is better via `> cmd`. Some commands need root.

```bash
python3 src/seed_systemd.py --seed
# or together with the other ops:
python3 src/seed_ops.py --seed
```

Does not touch the linux tags `proc` / `file` / `logs`. Do not confuse `sctl` with the kernel `sysctl`.

```text
$UNIT=nginx.service
$SINCE=1 hour ago
$BOOT=0
!! sysvars[1]
```

`$BOOT`: `0` — current boot, `-1` — previous boot.

---

## sctl — systemctl (tid)

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `systemctl --no-pager --failed` | Failed units |
| 2 | `list-units --type=service --state=failed` | Failed services |
| 3 | `systemctl --no-pager status $UNIT` | `$UNIT` status |
| 4 | `systemctl show $UNIT --no-pager` | `$UNIT` properties |
| 5 | `systemctl cat $UNIT --no-pager` | `$UNIT` unit file |
| 6 | `systemctl is-active $UNIT` | active/inactive `$UNIT` |
| 7 | `systemctl is-enabled $UNIT` | enabled/disabled `$UNIT` |
| 8 | `list-units --type=service --state=running` | Running services |
| 9 | `systemctl list-timers --all --no-pager` | Timers |
| 10 | `systemctl daemon-reload` | Reload unit files |
| 11 | `systemctl reload $UNIT` | Reload `$UNIT` (changes service) |
| 12 | `systemctl restart $UNIT` | Restart `$UNIT` (changes service) |
| 13 | `systemctl start $UNIT` | Start `$UNIT` (changes service) |
| 14 | `systemctl stop $UNIT` | Stop `$UNIT` (changes service) |
| 15 | `systemctl reset-failed $UNIT` | Reset failed `$UNIT` |

Playbooks do not include tid 10–15.

---

## jctl — journalctl (tid)

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `journalctl --no-pager -n 80` | Last 80 lines |
| 2 | `-p err -n 80` | Errors |
| 3 | `-u $UNIT -n 100` | Journal of `$UNIT` |
| 4 | `-u $UNIT -p err` | Errors of `$UNIT` |
| 5 | `-u $UNIT --since "$SINCE"` | Journal of `$UNIT` since `$SINCE` |
| 6 | `--list-boots` | List boots |
| 7 | `-b $BOOT -n 80` | Journal of boot `$BOOT` |
| 8 | `-k -n 80` | Kernel (like dmesg) |
| 9 | `--disk-usage` | Journal disk usage |
| 10 | `-u $UNIT -o json-pretty -n 20` | JSON `$UNIT` → F5 |
| 11 | `journalctl -f -u $UNIT` | Follow `$UNIT` (better: `> journalctl -f -u $UNIT`) |

---

## dmesg (tid)

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `dmesg --color=never \| tail -n 80` | Last 80 lines |
| 2 | `dmesg -T --color=never \| tail -n 80` | Human-readable time |
| 3 | `dmesg -T --level=err,warn` | err+warn |
| 4 | `dmesg -T --level=err` | Only err |
| 5 | `dmesg -w` | Follow (better: `> dmesg -w`) |

---

## Playbooks

| Tag | Chain |
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
