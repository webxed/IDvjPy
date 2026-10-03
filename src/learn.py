"""Small offline DevOps exercises for ``:learn``.

The module is deliberately declarative: it never runs a proposed command.  The
learner executes a real read-only command in the normal prompt, and
``:learn check`` only inspects that finished command block (its shape and exit
code — not the meaning of arbitrary output, and not a safety proof).
"""
from __future__ import annotations

import os
import shlex
from dataclasses import dataclass, field
from typing import Protocol

from i18n import t


@dataclass(frozen=True)
class Lesson:
    """One exercise: a name, a short task key and progressive hints."""

    name: str
    hints: tuple[str, ...] = field(default_factory=tuple)


LESSONS: tuple[Lesson, ...] = (
    Lesson("git-status", hints=("git", "git status -sb")),
    Lesson("listening-ports", hints=("ss", "ss -tlnp")),
    Lesson(
        "sqlite-select",
        hints=(
            "sqlite3 -readonly mytags.db 'SELECT tag, command FROM commands LIMIT 10;'",
            "sqlite3 -readonly <data-dir>/mytags.db 'SELECT tag, command FROM commands LIMIT 10;'",
        ),
    ),
)
_BY_NAME = {lesson.name: lesson for lesson in LESSONS}


class CommandEvidence(Protocol):
    """The read-only portion of a finished CommandBlock used by ``check``."""

    source_command: str
    return_code: int
    pending: bool


def _localized_or(key: str, fallback: str) -> str:
    """Локализованный текст ключа; ключа нет — буквальная подсказка-пример."""
    value = t(key)
    return fallback if value == key else value


def lesson_names() -> tuple[str, ...]:
    return tuple(lesson.name for lesson in LESSONS)


def get_lesson(name: str) -> Lesson | None:
    return _BY_NAME.get((name or "").strip().lower())


def format_list() -> str:
    lines = [t("learn.header"), ""]
    for lesson in LESSONS:
        lines.append(t("learn.lesson_row", name=lesson.name, description=t(f"learn.lesson.{lesson.name}")))
    lines.extend(("", t("learn.list_hint")))
    return "\n".join(lines)


def format_start(lesson: Lesson) -> str:
    return "\n".join((
        t("learn.started", name=lesson.name),
        t(f"learn.task.{lesson.name}"),
        "",
        t("learn.start_hint"),
    ))


def format_hint(lesson: Lesson, index: int) -> tuple[str, int]:
    """Return a progressively more concrete hint and the next index (capped)."""
    hint_index = min(max(index, 0), len(lesson.hints) - 1)
    key = f"learn.hint.{lesson.name}.{hint_index + 1}"
    return _localized_or(key, lesson.hints[hint_index]), min(hint_index + 1, len(lesson.hints))


def usage() -> str:
    names = ", ".join(lesson_names())
    return t("learn.usage", names=names)


def _tokens(text: str) -> list[str] | None:
    try:
        return shlex.split(text, comments=True)
    except ValueError:
        return None


def _is_git_status(args: list[str]) -> bool:
    if not args or args[0].lower() != "status":
        return False
    allowed = {"-s", "-b", "-sb", "--short", "--branch", "--porcelain"}
    return all(arg in allowed for arg in args[1:])


def _is_listening_ports(program: str, args: list[str]) -> bool:
    if program == "ss":
        joined = "".join(args)
        if any(not arg.startswith("-") or not set(arg[1:]) <= set("tlnp") for arg in args):
            return False
        return "t" in joined and "l" in joined and "n" in joined
    if program == "lsof":
        return len(args) == 4 and set(args) == {"-iTCP", "-sTCP:LISTEN", "-P", "-n"}
    return False


def _is_sqlite_select(args: list[str]) -> bool:
    if not args or args[0] not in {"-readonly", "--readonly"}:
        return False
    if len(args) != 3:
        return False
    sql = args[2].strip().removesuffix(";").rstrip()
    if not sql.lower().startswith("select "):
        return False
    # A single SELECT statement only; reject shell chaining and trailing SQL.
    if any(token in sql for token in (";", "&&", "||", "|", "`", "$")):
        return False
    return True


def _matches(lesson: Lesson, tokens: list[str]) -> bool:
    if not tokens:
        return False
    program = os.path.basename(tokens[0])
    args = tokens[1:]
    if lesson.name == "git-status":
        return program == "git" and _is_git_status(args)
    if lesson.name == "listening-ports":
        return program in {"ss", "lsof"} and _is_listening_ports(program, args)
    if lesson.name == "sqlite-select":
        return program == "sqlite3" and _is_sqlite_select(args)
    return False


def check(lesson: Lesson, block: CommandEvidence | None) -> str:
    """Assess one finished user command; never launch or repeat anything."""
    if block is None:
        return t("learn.no_command")
    if block.pending:
        return t("learn.pending")
    tokens = _tokens(block.source_command)
    if tokens is None or not _matches(lesson, tokens):
        return t("learn.wrong_command", name=lesson.name)
    if block.return_code != 0:
        return t("learn.failed", code=block.return_code)
    return t("learn.passed", name=lesson.name)
