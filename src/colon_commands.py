"""Краткие подсказки по `:`-командам (автодополнение при вводе `:`).

Один источник правды для быстрого списка: имя команды → одна строка описания
(интерфейс TUI — английский). Полный справочник остаётся в
``help_texts.MAIN_HELP_TEXT`` (`:?`), а ``tests/test_colon_commands.py`` следит,
чтобы таблица покрывала **все** ``CommandRunner.CMD_*``: добавили команду без
подсказки — тест упал.

Порядок — по полезности (как в `:?`), а не по алфавиту: список подсказок
показывает начало, остальное доступно фильтром по буквам.
"""
from __future__ import annotations

import re

# `:имя` — только имена из таблицы; `-`/`_`/буква сразу после имени означают, что
# это другое слово (`:name--`, `:md-path`), такое не трогаем.
_COLON_TOKEN_RE = re.compile(r":([A-Za-z?!][A-Za-z0-9?!]*)(?![A-Za-z0-9_\-])")

COLON_COMMANDS: tuple[tuple[str, str], ...] = (
    ("?", "command help (:? calc — calculator reference)"),
    ("q", "quit the application"),
    ("w", "write the last block output to a file"),
    ("h", "history: :h [N], :h /text, :h compact"),
    ("c", "clear all journal blocks"),
    ("json", "JSON viewer: last block or a file"),
    ("md", "markdown viewer; #L<n> — source line"),
    ("rg", "search markdown files (Obsidian vault)"),
    ("i", "Kubernetes Ingress Analyzer"),
    ("cd", "show or change the shell cwd"),
    ("fm", "OS file manager in a new window"),
    ("term", "system terminal in a new window"),
    ("ed", "external editor: file / $OUT / $BLOCK"),
    ("env", "re-read .bashrc_term* into this process"),
    ("r", "focused/last block command into the input"),
    ("cmd", "block command with values → clipboard"),
    ("log", "full block output: Line-API viewer, / search, f — matches only (F7)"),
    ("o", "session output history: :o /text, :o clear"),
    ("diff", "unified diff of two block outputs"),
    ("name", "label a block buffer (|@label)"),
    ("kill", "stop the running background command"),
    ("watch", "rerun a command every N seconds"),
    ("llm", "ask an LLM (ask / reset / offline)"),
    ("cht", "cheat.sh cheat sheets"),
    ("g", "search journal lines"),
    ("n", "next search hit"),
    ("N", "previous search hit"),
    ("stats", "library usage summary"),
    ("mv", "move a command / rename a tag"),
    ("export", "tag or library → JSON / Markdown"),
    ("import", "import commands from a JSON file"),
    ("alias", "commands as bash functions"),
    ("kctx", "cluster journal: saved vars per cluster (kctx_vars)"),
    ("session", "show or switch instance"),
    ("new", "app window in a new terminal (session)"),
    ("send", "forward a command to another session"),
    ("send!", "forward and run it immediately"),
    ("backup", "snapshot the tags DB into backups/"),
    ("welcome", "seed catalog (same as an empty DB)"),
    ("screensaver", "overlay now — matrix rain (default) / stars; idle: screensaver_idle"),
    ("theme", "TUI theme (:theme nord / dark / light)"),
    ("playbook", "dump this session as a --demo YAML"),
    ("run", "run a command chain (runbook): tag or YAML, wait for you where told"),
    ("update", "compare VERSION with GitHub main"),
)


def command_names() -> frozenset[str]:
    """Имена всех `:`-команд (без двоеточия) — для проверок и подстановок."""
    return frozenset(name for name, _ in COLON_COMMANDS)


def linkify_colon_commands(text: str) -> str:
    """Обернуть `:команды` в кликабельные ссылки (вставка во ввод по клику).

    Трогает только имена из `COLON_COMMANDS`, остальной текст — как есть.
    Вызывать **после** экранирования разметки: готовая разметка ссылки не должна
    попасть под escape (см. `app.escape_help_markup` — там живёт только `[bold]`).
    """
    names = command_names()

    def _link(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in names:
            return match.group(0)
        return (
            f"[@click=app.insert_colon_draft('{name}')]"
            f"[underline]:{name}[/][/]"
        )

    return _COLON_TOKEN_RE.sub(_link, text)
