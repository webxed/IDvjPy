"""Контекст о приложении для `:llm` — «шпаргалка» + выжимка библиотеки тегов.

Цель: LLM знает синтаксис префиксов IDvjPy_term и сохранённые команды
(тег / tid / комментарий), поэтому по описанию задачи возвращает готовую
связку ссылок вида `!kpod[2]` / `!! kpod[1] && klog[1]`, которую пользователь
вставляет во ввод и запускает отдельным Enter.

Модуль чистый (без Textual и сети): вход — строки библиотеки из БД, выход —
текст для системного промпта. Включается ключом `app_context` провайдера
(обычный `:llm`) или командой `:llm ask <задача>` (всегда, независимо от ключа).
"""
from __future__ import annotations

import re
from collections.abc import Container, Iterable, Mapping
from typing import Any, NamedTuple

# Бюджет контекста по умолчанию (символы): больше — дороже каждый запрос.
DEFAULT_MAX_CHARS = 6000
# Резерв под список тегов, которым не хватило места на полные детали (только имена).
_INDEX_RESERVE = 1200
# Команды в деталях обрезаются: ссылке нужен tid, а не полный jsonpath.
_MAX_COMMAND_CHARS = 200
# Страховка от «всё сразу»: не больше стольких тегов с деталями.
_MAX_DETAIL_TAGS = 40
# Сколько ссылок из ответа предлагать кликабельными.
MAX_REFS = 12

_WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9_]+")
# `!tag[3]`, `!! tag[3]`, `tag[3]` — с необязательными «!» перед именем тега.
_REF_RE = re.compile(r"!*([A-Za-z_][\w-]*)\[(\d+)\]")

APP_SYNTAX = """\
IDvjPy_term is a keyboard TUI that assembles shell lines from saved "tags"
(named command lists). The user types a line in the input field:
  #tag cmd      save `cmd` under `tag`
  ?tag          show one tag with its tids (`?text` searches all commands)
  !tag[3]       paste command tid 3 of `tag` into the input (it is NOT run)
  !12           paste the command with global id 12
  !!            assemble one line from refs: `!! kpod[1] && klog[1]`
  | cmd         pipe the focused block output into `cmd`
  $OUT / $BLOCK last line / full stdout of the focused block
  :llm ...      ask an LLM; `@file` attaches a text file
Commands may contain `$VAR` placeholders (e.g. `$NS`, `$POD`); the user sets
them with `$NS=value`. `> cmd` opens an interactive TTY.\
"""

APP_RULES = """\
Turn the user's task into ready-to-paste steps built from the saved commands
listed below. Give refs as `!tag[tid]` with the exact tids shown — a tid that
is not listed does not exist. To combine several refs into one command line,
start the line with `!!` and write the refs as `tag[tid]` separated by shell
operators (`&&`, `;`, `|`). Name any `$VAR=value` to set first. Be short:
the plan, then the refs. If the library lacks a needed command, say so
instead of inventing a tid.\
"""


class AppContext(NamedTuple):
    """Готовый контекст: текст для системного промпта + метрики для шапки."""

    text: str
    tags: int  # тегов, попавших с полными деталями (tid + команда)
    chars: int


def app_context_chars(provider: Mapping[str, Any]) -> int:
    """Ключ `app_context` провайдера → бюджет символов (0 = выключено).

    Отсутствует / `false` / `0` — выключено; `true` — `DEFAULT_MAX_CHARS`;
    число — само число. Непонятное значение трактуется как «выключено»
    (без сюрпризов: контекст не уезжает в запрос случайно).
    """
    raw = provider.get("app_context")
    if raw is None or raw is False:
        return 0
    if raw is True:
        return DEFAULT_MAX_CHARS
    if isinstance(raw, str):
        text = raw.strip().lower()
        if text in {"true", "yes", "on"}:
            return DEFAULT_MAX_CHARS
        if text in {"", "false", "no", "off"}:
            return 0
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 0
    return max(0, value)


def build_app_context(
    rows: Iterable[Mapping[str, Any]],
    *,
    task: str = "",
    tag_comments: Mapping[str, str] | None = None,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> AppContext:
    """Собирает контекст о приложении из live-строк библиотеки.

    `rows` — словари с ключами tag/tid/command/comment (как `_library()`).
    `task` — текст задачи: по совпадению слов теги с нужными командами
    поднимаются выше (комментарии seed-справочников на русском, поэтому
    запросы на русском тоже попадают). Теги без места в бюджете остаются
    в хвосте списком имён — по ним модель не выдумывает tid.
    """
    groups = _group_rows(rows)
    comments = tag_comments or {}
    head_parts = [APP_SYNTAX, APP_RULES]
    if not groups:
        head_parts.append("The user's library has no saved commands yet.")
        text = "\n\n".join(head_parts) + "\n"
        return AppContext(text, 0, len(text))

    total = sum(len(commands) for commands in groups.values())
    head_parts.append(
        f"Saved library: {total} commands in {len(groups)} tags. "
        "Use only the tids listed below:"
    )
    head = "\n\n".join(head_parts) + "\n"

    tokens = _tokens(task)
    order = sorted(
        groups,
        key=lambda tag: (
            -_tag_score(tag, groups[tag], comments.get(tag, ""), tokens),
            tag,
        ),
    )

    budget = max(int(max_chars), len(head) + _INDEX_RESERVE)
    detail_budget = budget - len(head) - _INDEX_RESERVE
    used = 0
    blocks: list[str] = []
    detailed: set[str] = set()
    for tag in order:
        if len(detailed) >= _MAX_DETAIL_TAGS:
            break
        block = _render_tag(tag, groups[tag], comments.get(tag, ""))
        if used + len(block) > detail_budget:
            continue
        blocks.append(block)
        detailed.add(tag)
        used += len(block) + 1

    missing = [tag for tag in order if tag not in detailed]
    tail = _render_index(missing, groups, budget - len(head) - used)
    parts = [head, *blocks]
    if tail:
        parts.append(tail)
    text = "\n".join(parts) + "\n"
    return AppContext(text, len(detailed), len(text))


def extract_refs(
    text: str,
    known: Mapping[str, Container[int]] | None = None,
    limit: int = MAX_REFS,
) -> list[tuple[str, int]]:
    """Ссылки `!tag[tid]` из ответа модели, в порядке появления и без повторов.

    `known` — карта тег → существующие tid: отсекает выдуманные ссылки
    и случайные `word[1]` из примеров кода. Без `known` фильтра нет.
    """
    found: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for match in _REF_RE.finditer(text or ""):
        tag = match.group(1)
        tid = int(match.group(2))
        if known is not None and tid not in (known.get(tag) or ()):
            continue
        if (tag, tid) in seen:
            continue
        seen.add((tag, tid))
        found.append((tag, tid))
        if len(found) >= limit:
            break
    return found


def _group_rows(rows: Iterable[Mapping[str, Any]]) -> dict[str, list[Mapping[str, Any]]]:
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows or ():
        tag = str(row.get("tag") or "").strip()
        if not tag:
            continue
        groups.setdefault(tag, []).append(row)
    return groups


def _tokens(text: str) -> list[str]:
    """Слова задачи (>= 3 символов), без повторов, в нижнем регистре."""
    tokens: list[str] = []
    for word in _WORD_RE.findall((text or "").lower()):
        if len(word) >= 3 and word not in tokens:
            tokens.append(word)
    return tokens


def _hits(hay: str, tokens: Iterable[str]) -> int:
    """Сколько слов задачи встречается в тексте (подстрока или общий префикс)."""
    if not hay or not tokens:
        return 0
    low = hay.lower()
    words = set(_WORD_RE.findall(low))
    hits = 0
    for tok in tokens:
        if tok in words or tok in low:
            hits += 1
        elif len(tok) >= 5 and any(w.startswith(tok[:5]) for w in words):
            hits += 1
    return hits


def _tag_score(
    tag: str,
    rows: list[Mapping[str, Any]],
    comment: str,
    tokens: Iterable[str],
) -> int:
    """Релевантность тега задаче (выше — важнее). Комментарии весят больше команд."""
    if not tokens:
        return 0
    score = 3 * _hits(tag, tokens) + 3 * _hits(comment, tokens)
    for row in rows:
        score += 2 * _hits(str(row.get("command") or ""), tokens)
        score += 3 * _hits(str(row.get("comment") or ""), tokens)
    return score


def _render_tag(tag: str, rows: list[Mapping[str, Any]], comment: str) -> str:
    title = f"{tag} — {comment}" if comment else tag
    lines = [title]
    for row in sorted(rows, key=lambda item: int(item.get("tid") or 0)):
        command = str(row.get("command") or "").strip()
        if len(command) > _MAX_COMMAND_CHARS:
            command = command[: _MAX_COMMAND_CHARS - 1] + "…"
        comment = str(row.get("comment") or "").strip()
        suffix = f"  — {comment}" if comment else ""
        lines.append(f"  {row.get('tid')}: {command}{suffix}")
    return "\n".join(lines)


def _render_index(
    tags: list[str],
    groups: Mapping[str, list[Mapping[str, Any]]],
    room: int,
) -> str:
    """Хвост: имена тегов без деталей (чтобы модель не выдумывала теги)."""
    if room <= 0 or not tags:
        return ""
    prefix = "Other tags (names only; details were cut by the size budget): "
    out = prefix
    shown: list[str] = []
    for tag in tags:
        piece = f"{tag}({len(groups[tag])})"
        if len(out) + len(piece) + 1 > room:
            break
        shown.append(piece)
    if not shown:
        return ""
    out += " ".join(shown)
    if len(shown) < len(tags):
        out += " …"
    return out
