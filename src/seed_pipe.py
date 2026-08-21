#!/usr/bin/env python3
"""
Seed unix-pipeline handbook: sort, uniq, cut, tr, wc, xargs, tee, jq
(see SEED_PIPE_COMMANDS.md).

Meant for `| cmd` on a journal block and `!!` assembly. tee writes a file
and is not in playbooks. Does not touch grep/awk/sed (seed_text.py).

Run: python3 src/seed_pipe.py --seed
"""
import sys

from seed_lib import run_seed as _run_seed
from seed_lib import seed_cli

SEED_TAGS = {
    "pvars": (
        "переменные конвейера",
        [
            (
                "echo file=$FILE sep=$SEP n=$N dest=$DEST json=$JSON",
                "проверка $FILE/$SEP/$JSON/…",
            ),
        ],
    ),
    "sort": (
        "sort: порядок строк",
        [
            ("sort $FILE", "лексикографически"),
            ("sort -u $FILE", "уникальные"),
            ("sort -n $FILE", "как числа"),
            ("sort -h $FILE", "человеческие размеры (1K 2M)"),
            ("sort -r $FILE", "обратный порядок"),
            ("sort -nr $FILE", "числа, по убыванию"),
            ("sort -k $N $FILE", "поле $N (пробел)"),
            ("sort -t \"$SEP\" -k $N $FILE", "поле $N, FS=$SEP"),
            ("sort -u -t \"$SEP\" -k $N,$N $FILE", "уникальные по полю $N"),
        ],
    ),
    "uniq": (
        "uniq: соседние дубликаты",
        [
            ("uniq $FILE", "сжать подряд идущие"),
            ("uniq -c $FILE", "счётчик"),
            ("uniq -d $FILE", "только дубликаты"),
            ("uniq -u $FILE", "только уникальные"),
            ("sort $FILE | uniq -c | sort -nr", "частоты по убыванию"),
        ],
    ),
    "cut": (
        "cut: колонки",
        [
            ("cut -d \"$SEP\" -f $N $FILE", "поле $N, FS=$SEP"),
            ("cut -d \"$SEP\" -f 1,$N $FILE", "поля 1 и $N"),
            ("cut -d \"$SEP\" -f 1-3 $FILE", "поля 1–3"),
            ("cut -c1-80 $FILE", "первые 80 символов"),
            ("cut -d \"$SEP\" -f $N --complement $FILE", "все поля кроме $N"),
        ],
    ),
    "tr": (
        "tr: символы (stdin)",
        [
            ("tr -d '\\r' < $FILE", "убрать CR"),
            ("tr -s ' ' < $FILE", "сжать пробелы"),
            ("tr '[:upper:]' '[:lower:]' < $FILE", "в нижний регистр"),
            ("tr '[:lower:]' '[:upper:]' < $FILE", "в верхний регистр"),
            ("tr -d '[:space:]' < $FILE", "убрать пробелы"),
            ("tr \"$SEP\" '\\n' < $FILE", "разделитель $SEP → строки"),
        ],
    ),
    "wc": (
        "wc: счётчики",
        [
            ("wc -l $FILE", "строки"),
            ("wc -w $FILE", "слова"),
            ("wc -c $FILE", "байты"),
            ("wc -lwm $FILE", "строки, слова, символы"),
            ("wc -L $FILE", "длина самой длинной строки"),
        ],
    ),
    "xargs": (
        "xargs: аргументы из строк",
        [
            ("xargs -a $FILE -n $N echo", "по $N аргументов"),
            ("xargs -a $FILE -I{} echo {}", "подстановка {}"),
            ("xargs -a $FILE -n 1 -r echo", "по одному, пустой ввод — ничего"),
            ("xargs -a $FILE -P 4 -n 1 echo", "до 4 параллельно"),
        ],
    ),
    "tee": (
        "tee: stdout и файл",
        [
            ("tee $DEST", "писать $DEST (меняет диск)"),
            ("tee -a $DEST", "дописать $DEST"),
        ],
    ),
    "jq": (
        "jq: JSON (файл или пайп)",
        [
            ("jq . $FILE", "pretty-print"),
            ("jq -c . $FILE", "одна строка на объект"),
            ("jq -r . $FILE", "raw strings"),
            ("jq 'keys' $FILE", "ключи объекта / индексы"),
            ("jq 'length' $FILE", "длина"),
            ("jq 'type' $FILE", "тип корня"),
            ("jq $JSON $FILE", "путь $JSON (из F5 Enter)"),
            ("jq -r $JSON $FILE", "путь $JSON, raw"),
            (
                "jq -e . >/dev/null $FILE && echo ok || echo bad-json",
                "валидный JSON?",
            ),
        ],
    ),
    "ucount": (
        "частоты строк: sort | uniq -c",
        [
            (
                "!uniq[5]",
                "sort | uniq -c | sort -nr",
            ),
        ],
    ),
    "jprev": (
        "обзор JSON",
        [
            (
                "!jq[4] ; echo '--- length ---' ; !jq[5] ; echo '--- type ---' ; !jq[6]",
                "keys → length → type",
            ),
        ],
    ),
}


def run_seed(db_file: str) -> int:
    return _run_seed(db_file, SEED_TAGS)


def main() -> None:
    seed_cli(
        description="Seed IDvjPy_term DB with sort/uniq/cut/tr/wc/xargs/tee/jq (SEED_PIPE_COMMANDS.md)",
        seed_help="Replace sort/uniq/cut/… (does not touch grep/awk/sed/file)",
        seed_tags=SEED_TAGS,
        argv=sys.argv,
    )


if __name__ == "__main__":
    main()
