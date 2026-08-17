#!/usr/bin/env python3
"""
Seed ssh / scp handbook tags (see SEED_SSH_COMMANDS.md).

Playbooks are non-interactive (config dump, BatchMode, keyscan).
Interactive login needs `> ssh …`. Does not touch linux `net`.

Run: python3 src/seed_ssh.py --seed
"""
import sys

from seed_lib import run_seed as _run_seed
from seed_lib import seed_cli

SEED_TAGS = {
    "svars": (
        "переменные ssh/scp",
        [
            (
                "echo remote=$REMOTE host=$HOST port=$PORT src=$SRC dest=$DEST "
                "key=$KEY cert=$CERT comment=$COMMENT cmd=$CMD",
                "проверка $REMOTE/$KEY/$CERT/…",
            ),
        ],
    ),
    "ssh": (
        "ssh: конфиг, ключи, login",
        [
            ("ssh -G $HOST", "эффективный ssh_config для $HOST"),
            (
                "ssh -o BatchMode=yes -o ConnectTimeout=5 $REMOTE true",
                "доступен ли хост по ключу",
            ),
            ("ssh-keyscan -T 5 $HOST", "host key (для known_hosts)"),
            ("ls -la ~/.ssh", "ключи и конфиг"),
            ("ssh-add -l", "ключи в агенте"),
            ("ssh-keygen -lf $KEY", "fingerprint $KEY"),
            (
                "ssh -p $PORT -o BatchMode=yes -o ConnectTimeout=5 $REMOTE true",
                "проверка на порту $PORT",
            ),
            ("ssh $REMOTE $CMD", "удалённая команда $CMD (без TTY)"),
            ("ssh -v -o BatchMode=yes -o ConnectTimeout=5 $REMOTE true", "debug подключения"),
            ("ssh -O check $REMOTE", "есть ли ControlMaster"),
            ("ssh $REMOTE", "интерактивный login (лучше: > ssh $REMOTE)"),
            ("ssh -t $REMOTE", "login с TTY (лучше: > ssh -t $REMOTE)"),
            ("ssh-copy-id -i $KEY $REMOTE", "поставить pubkey (меняет authorized_keys)"),
            ("mkdir -p ~/.ssh && chmod 700 ~/.ssh", "каталог ~/.ssh"),
            (
                "test ! -e \"$KEY\" && ssh-keygen -t ed25519 -N \"\" -C \"$COMMENT\" -f \"$KEY\" "
                "|| echo \"exists $KEY\"",
                "ed25519, если $KEY ещё нет (пустая passphrase)",
            ),
            (
                "ssh-keygen -t ed25519 -f \"$KEY\" -C \"$COMMENT\"",
                "ed25519 с запросом passphrase (лучше: > ssh-keygen …)",
            ),
            (
                "test ! -e \"$KEY\" && ssh-keygen -t rsa -b 4096 -N \"\" -C \"$COMMENT\" -f \"$KEY\" "
                "|| echo \"exists $KEY\"",
                "RSA 4096, если $KEY ещё нет",
            ),
            ("ssh-keygen -y -f \"$KEY\"", "печатать public key из private $KEY"),
            ("ssh-add \"$KEY\"", "добавить $KEY в агент"),
            ("ssh -V", "версия OpenSSH-клиента"),
            ("ssh -Q key", "типы ключей"),
            ("ssh -Q kex", "обмен ключами"),
            ("ssh -Q cipher", "шифры"),
            ("ssh -Q mac", "MAC"),
            ("ls -l /etc/ssh", "конфиг и host keys"),
            (
                "ls -l /etc/ssh/*cert* ~/.ssh/*-cert.pub 2>/dev/null",
                "файлы OpenSSH-сертификатов",
            ),
            (
                "sshd -T 2>/dev/null | grep -iE "
                "'^(hostkey |hostcertificate |trustedusercakeys |"
                "pubkeyauthentication |passwordauthentication |authenticationmethods )'",
                "sshd: ключи, cert, методы auth (часто нужен root)",
            ),
            ("ssh-keygen -L -f \"$CERT\"", "полный разбор сертификата $CERT"),
            (
                "ssh-keygen -L -f \"$CERT\" | grep -E "
                "'Type:|Key ID:|Serial:|Valid:|Signing CA:|Principals:'",
                "тип, CA, Valid from/to, principals",
            ),
            (
                "to=$(ssh-keygen -L -f \"$CERT\" | sed -n "
                "'s/^[[:space:]]*Valid: from .* to //p' | head -n 1); "
                "echo \"cert=$CERT\"; echo \"valid_to=$to\"; "
                "exp=$(date -d \"$to\" +%s); now=$(date +%s); "
                "echo \"now=$(date -Iseconds)\"; "
                "echo \"days_left=$(( (exp - now) / 86400 ))\"",
                "сколько суток осталось (GNU date; $CERT — *-cert.pub)",
            ),
        ],
    ),
    "scp": (
        "scp: копия по ssh",
        [
            (
                "scp -o ConnectTimeout=5 \"$SRC\" \"$REMOTE:$DEST\"",
                "локальное → $REMOTE",
            ),
            (
                "scp -o ConnectTimeout=5 \"$REMOTE:$SRC\" \"$DEST\"",
                "$REMOTE → локальное",
            ),
            (
                "scp -P $PORT -o ConnectTimeout=5 \"$SRC\" \"$REMOTE:$DEST\"",
                "на порт $PORT",
            ),
            (
                "scp -r -o ConnectTimeout=5 \"$SRC\" \"$REMOTE:$DEST\"",
                "рекурсивно на $REMOTE",
            ),
            (
                "scp -p -o ConnectTimeout=5 \"$SRC\" \"$REMOTE:$DEST\"",
                "сохранить mtime/mode",
            ),
            (
                "scp -v -o ConnectTimeout=5 \"$SRC\" \"$REMOTE:$DEST\"",
                "verbose",
            ),
        ],
    ),
    "schk": (
        "осмотр ssh (без login)",
        [
            (
                "!ssh[1] ; echo '--- batch ---' ; !ssh[2] ; echo '--- keyscan ---' ; !ssh[3]",
                "ssh -G → BatchMode true → keyscan",
            ),
        ],
    ),
    "ossh": (
        "OpenSSH: версия и алгоритмы",
        [
            (
                "!ssh[20] ; echo '--- keys ---' ; !ssh[21] ; echo '--- cert files ---' ; !ssh[26]",
                "ssh -V → ssh -Q key → ls *cert*",
            ),
        ],
    ),
    "ocert": (
        "срок OpenSSH-сертификата",
        [
            (
                "!ssh[29] ; echo '--- days_left ---' ; !ssh[30]",
                "сводка -L → days_left",
            ),
        ],
    ),
}


def run_seed(db_file: str) -> int:
    return _run_seed(db_file, SEED_TAGS)


def main() -> None:
    seed_cli(
        description="Seed IDvjPy_term DB with ssh/scp handbook (SEED_SSH_COMMANDS.md)",
        seed_help="Replace ssh/scp/svars/schk/ossh/ocert (does not touch net/rsync)",
        seed_tags=SEED_TAGS,
        argv=sys.argv,
    )


if __name__ == "__main__":
    main()
