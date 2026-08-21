#!/usr/bin/env python3
"""
Seed ansible handbook tags (see SEED_ANSIBLE_COMMANDS.md).

Playbooks are inspect-only: inventory, syntax-check, check --diff.
Real playbook runs and vault encrypt/decrypt of files are in the tags,
but not in achk / aping.

Run: python3 src/seed_ansible.py --seed
"""
import sys

from seed_lib import run_seed as _run_seed
from seed_lib import seed_cli

SEED_TAGS = {
    "ansvars": (
        "переменные ansible",
        [
            (
                "echo inv=$INV play=$PLAY limit=$LIMIT tags=$TAGS host=$HOST "
                "module=$MODULE args=$ARGS vaultfile=$VAULTFILE "
                "role=$ROLE collection=$COLLECTION",
                "проверка $INV/$PLAY/…",
            ),
        ],
    ),
    "ansible": (
        "ansible: inventory, ad-hoc, docs",
        [
            ("ansible --version", "версия ansible"),
            ("ansible-config dump --only-changed", "недефолтный конфиг"),
            ("ansible-inventory -i $INV --list", "inventory JSON"),
            ("ansible-inventory -i $INV --graph", "граф групп"),
            ("ansible $HOST -i $INV --list-hosts", "хосты по паттерну $HOST"),
            ("ansible $HOST -i $INV -m ping", "ping $HOST"),
            ("ansible $HOST -i $INV -m setup", "факты $HOST"),
            (
                "ansible $HOST -i $INV -m setup -a 'filter=ansible_distribution*'",
                "дистрибутив $HOST",
            ),
            ("ansible $HOST -i $INV -m command -a '$ARGS'", "command $ARGS на $HOST"),
            (
                "ansible $HOST -i $INV -m $MODULE -a '$ARGS' --check",
                "check-mode модуля $MODULE",
            ),
            (
                "ansible $HOST -i $INV -m $MODULE -a '$ARGS'",
                "модуль $MODULE (меняет хост)",
            ),
            ("ansible-doc $MODULE", "документация $MODULE"),
            (
                "ansible-console -i $INV",
                "REPL (лучше: > ansible-console -i $INV)",
            ),
        ],
    ),
    "aplay": (
        "ansible-playbook: syntax, check, run",
        [
            ("ansible-playbook -i $INV $PLAY --syntax-check", "syntax-check $PLAY"),
            ("ansible-playbook -i $INV $PLAY --list-hosts", "хосты плейбука"),
            ("ansible-playbook -i $INV $PLAY --list-tasks", "задачи плейбука"),
            ("ansible-playbook -i $INV $PLAY --list-tags", "теги плейбука"),
            (
                "ansible-playbook -i $INV $PLAY --check --diff",
                "check + diff",
            ),
            (
                "ansible-playbook -i $INV $PLAY --check --diff --limit $LIMIT",
                "check, limit $LIMIT",
            ),
            (
                "ansible-playbook -i $INV $PLAY --check --diff --tags $TAGS",
                "check, tags $TAGS",
            ),
            (
                "ansible-playbook -i $INV $PLAY --limit $LIMIT",
                "прогон, limit $LIMIT (меняет хосты)",
            ),
            (
                "ansible-playbook -i $INV $PLAY --tags $TAGS",
                "прогон, tags $TAGS (меняет хосты)",
            ),
            (
                "ansible-playbook -i $INV $PLAY",
                "прогон $PLAY (меняет хосты)",
            ),
        ],
    ),
    "avault": (
        "ansible-vault",
        [
            ("ansible-vault view $VAULTFILE", "показать $VAULTFILE"),
            (
                "ansible-vault encrypt $VAULTFILE --output=-",
                "encrypt в stdout",
            ),
            (
                "ansible-vault decrypt $VAULTFILE --output=-",
                "decrypt в stdout",
            ),
            (
                "ansible-vault encrypt $VAULTFILE",
                "encrypt файл (меняет $VAULTFILE)",
            ),
            (
                "ansible-vault decrypt $VAULTFILE",
                "decrypt файл (меняет $VAULTFILE)",
            ),
            (
                "ansible-vault create $VAULTFILE",
                "создать $VAULTFILE (лучше: > ansible-vault create $VAULTFILE)",
            ),
            (
                "ansible-vault edit $VAULTFILE",
                "редактировать (лучше: > ansible-vault edit $VAULTFILE)",
            ),
        ],
    ),
    "agalaxy": (
        "ansible-galaxy: roles, collections",
        [
            ("ansible-galaxy collection list", "установленные коллекции"),
            ("ansible-galaxy role list", "установленные роли"),
            ("ansible-galaxy collection search $COLLECTION", "поиск коллекции"),
            ("ansible-galaxy role search $ROLE", "поиск роли"),
            (
                "ansible-galaxy collection install $COLLECTION",
                "поставить коллекцию",
            ),
            ("ansible-galaxy role install $ROLE", "поставить роль"),
            ("ansible-galaxy init $ROLE", "скелет роли $ROLE"),
        ],
    ),
    "aping": (
        "ping хостов inventory",
        [
            (
                "!ansible[5] ; echo '--- ping ---' ; !ansible[6]",
                "list-hosts → ping",
            ),
        ],
    ),
    "achk": (
        "обзор ansible: inventory → syntax → check",
        [
            (
                "!ansible[3] ; echo '--- syntax ---' ; !aplay[1] ; echo '--- check ---' ; !aplay[5]",
                "inventory --list → syntax-check → check --diff",
            ),
        ],
    ),
}


def run_seed(db_file: str) -> int:
    return _run_seed(db_file, SEED_TAGS)


def main() -> None:
    seed_cli(
        description="Seed IDvjPy_term DB with ansible handbook (SEED_ANSIBLE_COMMANDS.md)",
        seed_help="Replace ansible/aplay/avault/… (does not touch linux/k8s/git)",
        seed_tags=SEED_TAGS,
        argv=sys.argv,
    )


if __name__ == "__main__":
    main()
