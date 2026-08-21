# Справочник ansible для IDvjPy

Теги **`ansible`**, **`aplay`**, **`avault`**, **`agalaxy`**.  
Плейбуки осмотра: `achk`, `aping`. Реальный `ansible-playbook` без `--check` и запись vault-файла — только руками.

```bash
python3 src/seed_ansible.py --seed
# или вместе с остальными ops:
python3 src/seed_ops.py --seed
```

Не трогает linux / k8s / git. `$VAULTFILE` — файл ansible-vault, не HashiCorp Vault.

```text
$INV=inventory.ini
$PLAY=site.yml
$LIMIT=
$TAGS=
$HOST=all
$MODULE=ping
$ARGS=
$VAULTFILE=secrets.yml
$ROLE=
$COLLECTION=
!! ansvars[1]
```

Интерактив: `> ansible-console -i $INV`, `> ansible-vault edit $VAULTFILE`.

---

## ansible — ad-hoc и inventory (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `ansible --version` | Версия |
| 2 | `ansible-config dump --only-changed` | Недефолтный конфиг |
| 3 | `ansible-inventory -i $INV --list` | Inventory JSON → F5 |
| 4 | `ansible-inventory -i $INV --graph` | Граф групп |
| 5 | `ansible $HOST -i $INV --list-hosts` | Хосты паттерна `$HOST` |
| 6 | `ansible $HOST -i $INV -m ping` | Ping |
| 7 | `ansible $HOST -i $INV -m setup` | Факты |
| 8 | `setup filter=ansible_distribution*` | Дистрибутив |
| 9 | `ansible … -m command -a '$ARGS'` | `command` |
| 10 | `ansible … -m $MODULE -a '$ARGS' --check` | Check-mode модуля |
| 11 | `ansible … -m $MODULE -a '$ARGS'` | Модуль (меняет хост) |
| 12 | `ansible-doc $MODULE` | Документация модуля |
| 13 | `ansible-console -i $INV` | REPL (`> ansible-console …`) |

Не в плейбуке: tid 11 (меняет хост), tid 13 (интерактив).

---

## aplay — ansible-playbook (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `--syntax-check` | Синтаксис `$PLAY` |
| 2 | `--list-hosts` | Хосты плейбука |
| 3 | `--list-tasks` | Задачи |
| 4 | `--list-tags` | Теги |
| 5 | `--check --diff` | Dry-run |
| 6 | `--check --diff --limit $LIMIT` | Dry-run, limit |
| 7 | `--check --diff --tags $TAGS` | Dry-run, tags |
| 8 | `--limit $LIMIT` | Прогон (меняет хосты) |
| 9 | `--tags $TAGS` | Прогон (меняет хосты) |
| 10 | `ansible-playbook -i $INV $PLAY` | Полный прогон (меняет хосты) |

В `achk` только tid 1 и 5.

---

## avault / agalaxy

`avault`: view и encrypt/decrypt в stdout — осмотр; encrypt/decrypt файла, create, edit — меняют диск / интерактив.

`agalaxy`: list/search — осмотр; install/init — пишут в `~/.ansible`.

---

## Плейбуки

| Тег | Цепочка |
|-----|---------|
| `aping[1]` | list-hosts → ping |
| `achk[1]` | inventory `--list` → syntax-check → check `--diff` |

```text
$HOST=all
!! aping[1]
$PLAY=site.yml
!! achk[1]
!! aplay[5]
```
