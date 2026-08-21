#!/usr/bin/env python3
"""
Seed users / permissions handbook (see SEED_USER_COMMANDS.md).

Playbooks are inspect-only: id, getent, last, sudo -l.
chmod/chown templates are in perm, not in uidchk. No userdel.

Run: python3 src/seed_user.py --seed
"""
import sys

from seed_lib import run_seed as _run_seed
from seed_lib import seed_cli

SEED_TAGS = {
    "uvars": (
        "переменные пользователей и прав",
        [
            (
                "echo user=$USER file=$FILE mode=$MODE owner=$OWNER group=$GROUP",
                "проверка $USER/$FILE/$MODE/…",
            ),
        ],
    ),
    "ident": (
        "id, getent, last, sudo",
        [
            ("id", "текущий uid/gid"),
            ("id $USER", "учётка $USER"),
            ("whoami", "имя"),
            ("groups $USER", "группы $USER"),
            ("getent passwd $USER", "passwd $USER"),
            ("getent group $GROUP", "группа $GROUP"),
            ("last -n 20", "последние логины"),
            ("lastb -n 20", "неудачные логины (часто root)"),
            ("lastlog | tail -n 20", "lastlog, хвост"),
            ("sudo -n -l", "sudo -l без пароля (может fail)"),
            ("sudo -l", "sudo -l (лучше: > sudo -l)"),
            ("w", "кто на системе"),
            ("who", "сессии"),
        ],
    ),
    "perm": (
        "chmod / chown / stat",
        [
            ("stat $FILE", "метаданные $FILE"),
            ("ls -ld $FILE", "права и владелец"),
            ("namei -l $FILE", "цепочка путей"),
            ("getfacl $FILE", "ACL (если есть)"),
            ("umask -S", "текущий umask"),
            ("chmod $MODE $FILE", "chmod $MODE (меняет файл)"),
            ("chmod -R $MODE $FILE", "рекурсивный chmod"),
            ("chown $OWNER $FILE", "владелец $OWNER"),
            ("chown $OWNER:$GROUP $FILE", "владелец и группа"),
            ("chgrp $GROUP $FILE", "группа $GROUP"),
        ],
    ),
    "uidchk": (
        "кто я: id + groups + sudo",
        [
            (
                "!ident[1] ; echo '--- groups ---' ; !ident[4] ; echo '--- sudo ---' ; !ident[10]",
                "id → groups → sudo -n -l",
            ),
        ],
    ),
}


def run_seed(db_file: str) -> int:
    return _run_seed(db_file, SEED_TAGS)


def main() -> None:
    seed_cli(
        description="Seed IDvjPy_term DB with id/getent/chmod handbook (SEED_USER_COMMANDS.md)",
        seed_help="Replace ident/perm/uidchk/… (does not touch proc/file)",
        seed_tags=SEED_TAGS,
        argv=sys.argv,
    )


if __name__ == "__main__":
    main()
