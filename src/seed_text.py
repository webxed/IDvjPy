#!/usr/bin/env python3
"""
Seed text-filter handbook: grep, awk, sed (see SEED_TEXT_COMMANDS.md).

Playbooks print to stdout. sed -i is not in playbooks.

Run: python3 src/seed_text.py --seed
"""
import sys

from seed_lib import run_seed as _run_seed
from seed_lib import seed_cli

SEED_TAGS = {
    "tvars": (
        "переменные grep/awk/sed",
        [
            (
                "echo file=$FILE pattern=$PATTERN repl=$REPL sep=$SEP n=$N",
                "проверка $FILE/$PATTERN/…",
            ),
        ],
    ),
    "grep": (
        "grep: поиск в файле и дереве",
        [
            ("grep -n $PATTERN $FILE", "строки с номерами"),
            ("grep -ni $PATTERN $FILE", "без учёта регистра"),
            ("grep -nv $PATTERN $FILE", "обратный фильтр"),
            ("grep -nc $PATTERN $FILE", "число совпадений"),
            ("grep -nE $PATTERN $FILE", "расширенный regexp"),
            ("grep -nF $PATTERN $FILE", "фиксированная строка"),
            ("grep -nC 3 $PATTERN $FILE", "контекст ±3"),
            ("grep -nA 5 $PATTERN $FILE", "5 строк после"),
            ("grep -nB 5 $PATTERN $FILE", "5 строк до"),
            ("grep -oE $PATTERN $FILE", "только совпадения"),
            ("grep -nH $PATTERN $FILE", "с именем файла"),
            ("grep -l $PATTERN $FILE", "только имя, если есть hit"),
            ("grep -Rn --exclude-dir=.git --exclude-dir=.venv $PATTERN .", "рекурсивно от cwd"),
            ("zgrep -n $PATTERN $FILE", "поиск в .gz"),
        ],
    ),
    "awk": (
        "awk: поля, суммы, уникальные",
        [
            ("awk '{print $1}' $FILE", "первое поле (FS=пробел)"),
            ("awk -F \"$SEP\" '{print $1}' $FILE", "первое поле, FS=$SEP"),
            ("awk -F \"$SEP\" '{print $1,$NF}' $FILE", "первое и последнее поле"),
            ("awk '{print NR, $0}' $FILE", "номер строки"),
            ("awk 'NR==1 {print}' $FILE", "первая строка (заголовок)"),
            ("awk -v n=\"$N\" 'NR==n {print}' $FILE", "строка $N"),
            ("awk 'NF' $FILE", "убрать пустые строки"),
            ("awk '!seen[$0]++' $FILE", "уникальные строки, порядок как в файле"),
            ("awk '{s+=$1} END {print s}' $FILE", "сумма первого поля"),
            (
                "awk -v p=\"$PATTERN\" '$0 ~ p {print NR, $0}' $FILE",
                "строки, совпавшие с $PATTERN",
            ),
            ("awk -F \"$SEP\" '{print NF}' $FILE", "число полей в каждой строке"),
            ("awk 'END {print NR}' $FILE", "число строк"),
        ],
    ),
    "sed": (
        "sed: печать и замена в stdout",
        [
            ("sed -n '1,20p' $FILE", "первые 20 строк"),
            ("sed -n \"$N\"p $FILE", "строка $N"),
            ("sed -n \"/$PATTERN/p\" $FILE", "строки по regexp $PATTERN"),
            ("sed \"s/$PATTERN/$REPL/\" $FILE", "первая замена в строке"),
            ("sed \"s/$PATTERN/$REPL/g\" $FILE", "все замены в строке"),
            ("sed \"s/$PATTERN/$REPL/gI\" $FILE", "замены без учёта регистра"),
            ("sed -n \"s/$PATTERN/$REPL/gp\" $FILE", "печатать только изменённые"),
            ("sed '/^$/d' $FILE", "убрать пустые строки"),
            ("sed 's/[[:space:]]*$//' $FILE", "обрезать пробелы справа"),
            ("sed 's/\\r$//' $FILE", "убрать CR (CRLF→LF) в stdout"),
            ("sed '1d' $FILE", "без первой строки"),
            ("sed '$d' $FILE", "без последней строки"),
            (
                "sed -i.bak \"s/$PATTERN/$REPL/g\" $FILE",
                "правка файла + .bak (не в плейбуке)",
            ),
        ],
    ),
    "gchk": (
        "поиск: строки + счётчик",
        [
            (
                "!grep[1] ; echo '--- count ---' ; !grep[4]",
                "grep -n → grep -c",
            ),
        ],
    ),
    "sprev": (
        "замена в stdout (без -i)",
        [
            (
                "!sed[5] ; echo '--- matched ---' ; !sed[3]",
                "s///g → строки по $PATTERN",
            ),
        ],
    ),
}


def run_seed(db_file: str) -> int:
    return _run_seed(db_file, SEED_TAGS)


def main() -> None:
    seed_cli(
        description="Seed IDvjPy_term DB with grep/awk/sed handbook (SEED_TEXT_COMMANDS.md)",
        seed_help="Replace grep/awk/sed/tvars/… (does not touch file/proc)",
        seed_tags=SEED_TAGS,
        argv=sys.argv,
    )


if __name__ == "__main__":
    main()
