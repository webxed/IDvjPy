# ansible handbook for IDvjPy

Tags **`ansible`**, **`aplay`**, **`avault`**, **`agalaxy`**.  
Inspection playbooks: `achk`, `aping`. A real `ansible-playbook` without `--check` and writing a vault file are manual only.

```bash
python3 src/seed_ansible.py --seed
# or together with the other ops:
python3 src/seed_ops.py --seed
```

Does not touch linux / k8s / git. `$VAULTFILE` is an ansible-vault file, not HashiCorp Vault.

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

Interactive: `> ansible-console -i $INV`, `> ansible-vault edit $VAULTFILE`.

---

## ansible — ad-hoc and inventory (tid)

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `ansible --version` | Ansible version |
| 2 | `ansible-config dump --only-changed` | Non-default config |
| 3 | `ansible-inventory -i $INV --list` | Inventory JSON |
| 4 | `ansible-inventory -i $INV --graph` | Group graph |
| 5 | `ansible $HOST -i $INV --list-hosts` | Hosts matching pattern `$HOST` |
| 6 | `ansible $HOST -i $INV -m ping` | Ping `$HOST` |
| 7 | `ansible $HOST -i $INV -m setup` | Facts for `$HOST` |
| 8 | `setup filter=ansible_distribution*` | Distribution of `$HOST` |
| 9 | `ansible … -m command -a '$ARGS'` | Command `$ARGS` on `$HOST` |
| 10 | `ansible … -m $MODULE -a '$ARGS' --check` | Check mode for module `$MODULE` |
| 11 | `ansible … -m $MODULE -a '$ARGS'` | Module `$MODULE` (changes the host) |
| 12 | `ansible-doc $MODULE` | Docs for `$MODULE` |
| 13 | `ansible-console -i $INV` | REPL (better: `> ansible-console -i $INV`) |

Not in the playbook: tid 11 (changes the host), tid 13 (interactive).

---

## aplay — ansible-playbook (tid)

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `--syntax-check` | syntax-check `$PLAY` |
| 2 | `--list-hosts` | Playbook hosts |
| 3 | `--list-tasks` | Playbook tasks |
| 4 | `--list-tags` | Playbook tags |
| 5 | `--check --diff` | check + diff |
| 6 | `--check --diff --limit $LIMIT` | check, limit `$LIMIT` |
| 7 | `--check --diff --tags $TAGS` | check, tags `$TAGS` |
| 8 | `--limit $LIMIT` | run, limit `$LIMIT` (changes hosts) |
| 9 | `--tags $TAGS` | run, tags `$TAGS` (changes hosts) |
| 10 | `ansible-playbook -i $INV $PLAY` | run `$PLAY` (changes hosts) |

`achk` includes only tid 1 and 5.

---

## avault / agalaxy

`avault`: view and encrypt/decrypt to stdout are inspection; encrypt/decrypt of a file, create, edit change the disk / are interactive.

`agalaxy`: list/search are inspection; install/init write to `~/.ansible`.

---

## Playbooks

| Tag | Chain |
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
