"""Краткие подсказки по `:`-командам (автодополнение при вводе `:`).

Имена и порядок команд живут здесь (`COLON_COMMAND_NAMES`, по полезности, как в
`:?`); сами описания — в локалях (`cmd.<имя>`, см. ``src/locales/en.yml``), их
отдаёт ``colon_command_hint``. ``tests/test_colon_commands.py`` следит, чтобы
таблица покрывала **все** ``CommandRunner.CMD_*`` и у каждой команды был текст:
добавили команду без подсказки — тест упал.
"""
from __future__ import annotations

import re

from i18n import t

# Имена `:`-команд в порядке полезности (как в `:?`), а не по алфавиту:
# список подсказок показывает начало, остальное доступно фильтром по буквам.
COLON_COMMAND_NAMES: tuple[str, ...] = (
    "?",
    "q",
    "w",
    "h",
    "c",
    "json",
    "md",
    "rg",
    "i",
    "cd",
    "fm",
    "term",
    "ed",
    "env",
    "r",
    "cmd",
    "log",
    "o",
    "diff",
    "name",
    "kill",
    "watch",
    "llm",
    "cht",
    "g",
    "n",
    "N",
    "stats",
    "mv",
    "export",
    "import",
    "alias",
    "kctx",
    "session",
    "new",
    "send",
    "send!",
    "backup",
    "vault",
    "welcome",
    "screensaver",
    "theme",
    "lang",
    "relang",
    "scope",
    "playbook",
    "run",
    "update",
)

# `:имя` — только имена из таблицы; `-`/`_`/буква сразу после имени означают, что
# это другое слово (`:name--`, `:md-path`), такое не трогаем.
_COLON_TOKEN_RE = re.compile(r":([A-Za-z?!][A-Za-z0-9?!]*)(?![A-Za-z0-9_\-])")


def command_names() -> frozenset[str]:
    """Имена всех `:`-команд (без двоеточия) — для проверок и подстановок."""
    return frozenset(COLON_COMMAND_NAMES)


def colon_command_hint(name: str) -> str:
    """Одна строка описания команды на текущем языке (`cmd.<имя>`)."""
    return t(f"cmd.{name}")


def colon_commands() -> tuple[tuple[str, str], ...]:
    """Пары «имя команды → подсказка» на текущем языке."""
    return tuple((name, colon_command_hint(name)) for name in COLON_COMMAND_NAMES)


def linkify_colon_commands(text: str) -> str:
    """Обернуть `:команды` в кликабельные ссылки (вставка во ввод по клику).

    Трогает только имена из `COLON_COMMAND_NAMES`, остальной текст — как есть.
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
