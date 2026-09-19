"""Перевод комментариев уже засеянной библиотеки (`:relang`).

``--seed`` пишет комментарии на языке ``settings.yml: language``. Если язык сменить
**после** посева, строки в базе останутся на старом; повторный ``--seed`` это
исправил бы, но стёр бы пользовательские теги и команды. Этот модуль переписывает
**только комментарии канонических строк сидов** — подписи тегов и подсказки команд,
совпавшие по тегу и тексту команды (а для linux-дополнений — по позиции tid), —
ничего не удаляя и не добавляя. Библиотека переезжает на другой язык, не теряя
ручных правок.

Комментарий, который правили руками (не пустой и не совпадает ни с одним известным
переводом), не трогается: ``--seed`` такого различения не делает, а тут оно есть.
Перед записью снимается снимок БД в ``backups/`` (как у сидов).
"""
from __future__ import annotations

import argparse
import sys

import database_v2 as database
from seed_lib import (
    backup_sqlite_before_seed,
    get_db_file,
    localized_comment,
    localized_tag_comment,
    resolve_seed_language,
)


def _collect() -> tuple[dict, dict, dict]:
    """Канонические сиды: команды, extra-позиции linux и подписи тегов.

    Возвращает ``(by_command, by_position, tag_comments)``:

    - ``by_command[(tag, команда)] = (позиция, встроенный комментарий)`` —
      ``localized_comment`` берёт перевод именно по позиции (tid-1);
    - ``by_position[(tag, позиция)] = встроенный комментарий`` — только
      linux-дополнения (``logs``, ``file[12]``, ``net[10..11]``), у которых нет
      канонической команды в ``SEED_COMMANDS``;
    - ``tag_comments[tag] = встроенная подпись``.
    """
    import seed_git
    import seed_k8s_chains
    import seed_linux_commands
    import seed_ops

    by_command: dict[tuple[str, str], tuple[int, str]] = {}
    by_position: dict[tuple[str, int], str] = {}
    tag_comments: dict[str, str] = {}

    def add_tag(tag: str, tag_comment: str, commands: list) -> None:
        if tag_comment:
            tag_comments[tag] = tag_comment
        for position, (command, comment) in enumerate(commands):
            by_command[(tag, command)] = (position, comment or "")

    for source in (seed_k8s_chains, seed_git):
        for tag, (tag_comment, commands) in source.SEED_TAGS.items():
            add_tag(tag, tag_comment, commands)
    for _name, mod in seed_ops.MODULES:
        for tag, (tag_comment, commands) in mod.SEED_TAGS.items():
            add_tag(tag, tag_comment, commands)
    for tag in seed_linux_commands.SEED_COMMANDS:
        add_tag(
            tag,
            seed_linux_commands.TAG_COMMENTS.get(tag, ""),
            list(seed_linux_commands._seed_items(tag)),
        )
    # linux: комментарии к пользовательским tid — позиция берётся из самого tid.
    for (tag, tid), comment in seed_linux_commands.EXTRA_COMMENTS.items():
        by_position[(tag, tid - 1)] = comment
    logs_comment = seed_linux_commands.TAG_COMMENTS.get("logs", "")
    if logs_comment:
        tag_comments["logs"] = logs_comment
    return by_command, by_position, tag_comments


def _untouched(current: str, known: set[str]) -> bool:
    """Комментарий ещё сидовый (пуст или равен известному переводу)?

    Правили руками — вернём False: чужую правку язык не трогает.
    """
    return not current or current in known


def relang_db(db_file: str, lang: str) -> tuple[int, int]:
    """Переписать комментарии сидов на язык ``lang``; вернуть (команд, тегов).

    Снимок БД снимается до записи и только для непустой базы. Строки, которых нет
    в канонических сидах (пользовательские теги/команды), и комментарии, изменённые
    вручную, остаются как есть.
    """
    from i18n import available_languages

    by_command, by_position, tag_comments = _collect()
    languages = available_languages()

    def _variants(values: set[str]) -> set[str]:
        return {text for text in (value.strip() for value in values) if text}

    def command_variants(tag: str, position: int, base: str) -> set[str]:
        values = {base} if base else set()
        values.update(
            localized_comment(tag, position, base, code) for code in languages
        )
        return _variants(values)

    def tag_variants(tag: str, base: str) -> set[str]:
        values = {base} if base else set()
        values.update(localized_tag_comment(tag, base, code) for code in languages)
        return _variants(values)

    database.init_db(db_file)
    backup_sqlite_before_seed(db_file, "relang")

    conn = database.get_db_connection(db_file)
    rows = conn.execute(
        "SELECT tid, tag, command, comment FROM commands WHERE deleted = 0"
    ).fetchall()
    conn.close()

    commands_changed = 0
    for row in rows:
        tag = str(row["tag"])
        tid = int(row["tid"])
        current = (row["comment"] or "").strip()
        hit = by_command.get((tag, row["command"]))
        if hit is not None:
            position, base = hit
        else:
            base = by_position.get((tag, tid - 1))
            if base is None:
                continue  # пользовательская команда — не наше дело
            position = tid - 1
        wanted = localized_comment(tag, position, base, lang).strip()
        if not wanted or wanted == current:
            continue
        if not _untouched(current, command_variants(tag, position, base)):
            continue  # комментарий правили руками — оставляем
        database.set_command_comment(db_file, tag, tid, wanted)
        commands_changed += 1

    tags_changed = 0
    seen: set[str] = set()
    for row in rows:
        tag = str(row["tag"])
        if tag in seen:
            continue
        seen.add(tag)
        base = tag_comments.get(tag)
        if not base:
            continue
        current = (database.get_tag_comment(db_file, tag) or "").strip()
        wanted = localized_tag_comment(tag, base, lang).strip()
        if not wanted or wanted == current:
            continue
        if not _untouched(current, tag_variants(tag, base)):
            continue
        database.set_tag_comment(db_file, tag, wanted)
        tags_changed += 1

    return commands_changed, tags_changed


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Re-translate seeded handbook comments in an existing DB (:relang)"
    )
    parser.add_argument(
        "--lang",
        default="",
        help="Target language code (default: settings.yml `language`)",
    )
    parser.add_argument(
        "--db",
        default="",
        help="SQLite file (default: settings.yml database_tags_file)",
    )
    args = parser.parse_args(argv)

    from i18n import normalize_language, resolve_language

    if args.lang:
        code = normalize_language(args.lang)
        if code == "auto":
            code = resolve_language("auto", None)
        if not code:
            print(f"Unknown language: {args.lang}", file=sys.stderr)
            sys.exit(2)
        lang = code
    else:
        lang = resolve_seed_language()

    db_file = args.db or get_db_file()
    commands_changed, tags_changed = relang_db(db_file, lang)
    print(
        f"Library comments → {lang}: {commands_changed} command(s), "
        f"{tags_changed} tag(s) updated in {db_file}"
    )


if __name__ == "__main__":
    main()
