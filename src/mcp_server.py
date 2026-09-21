"""MCP-сервер (stdio) поверх библиотеки тегов и истории — **только чтение**.

Корневой `mcp_server.py` — лаунчер (как `app.py` и `backup_db.py`), сам сервер здесь.

Зачем: внешний AI-клиент (Claude Code, Cursor, …) спрашивает «есть ли у меня
команда для X» — и получает ответ из живой библиотеки, а не из пересказа.
Транспорт — stdio: процесс запускает сам клиент, портов приложение не слушает
(то же решение, что у Atuin в `atuin mcp`).

Инварианты (сторожат `tests/test_mcp_server.py`):

* **только чтение** — база не создаётся и не меняется: ни одной write-функции
  `database_v2` (`init_db`, `add_command`, `delete_*`, `set_*`, `bump_*`, `move_*`);
* **секреты не читаются** — `secrets_<instance>.json` сервер не открывает. Утечки
  нет по конструкции: значений `$$`-секретов в библиотеке нет (они живут только в
  сессии и чистятся при выходе), а история сессии их не пишет;
* **сети нет** — читаются только stdin и локальные файлы данных;
* в stdout уходят **только** сообщения JSON-RPC (одно на строку — транспорт MCP
  не допускает переводов строки внутри сообщения), служебное — в stderr: иначе
  клиент не разберёт поток.

Приватность: всё, что вернули инструменты, уходит в подключённый AI-клиент.
Поэтому секреты в теги руками не пишем (для них есть `$$`).

Описания инструментов — по-английски: их читает модель, а не человек-переводчик,
и сервер не тянет локали (и Textual — тоже: стартует быстро и без TUI).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

import data_dirs
import database_v2 as database
import history_import
import history_store

SERVER_NAME = "idvjpy"
SERVER_TITLE = "IDvjPy_term tag library"
# Версии протокола, которые мы понимаем (сначала свежая). Клиент присылает свою —
# отвечаем ею, если она в списке, иначе своей свежей: так делает большинство
# минимальных серверов, и старый клиент не отваливается.
PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")

SETTINGS_FILE = "settings.yml"
DEFAULT_DB = "mytags.db"
DEFAULT_INSTANCE = "default"
DEFAULT_LIMIT = 40
MAX_LIMIT = 500
# Сколько строк каждой истории оболочки читать при `source=shells` из `:h import`.
SHELL_HISTORY_LIMIT = 2000
HISTORY_SOURCES = ("session", "shells", "all")

INSTRUCTIONS = (
    "Read-only access to the IDvjPy_term tag library (commands saved under tags) "
    "and to the session history. Nothing can be modified: the server never writes "
    "to the database and never runs commands. Values of $$ secrets are not stored "
    "in the library and are never returned; do not ask for them."
)


class ToolError(Exception):
    """Ошибка уровня инструмента: клиенту уходит текст с `isError: true`."""


@dataclass(frozen=True)
class Config:
    """Что читает сервер: каталог данных, файл библиотеки, история сессии."""

    data_dir: str
    db_file: str
    history_file: str
    instance: str
    shell_history: bool = False


# --- конфигурация ------------------------------------------------------------


def settings_db_file(data_dir: str) -> str:
    """`database_tags_file` из settings.yml каталога данных (нет/битый — `mytags.db`)."""
    try:
        with open(os.path.join(data_dir, SETTINGS_FILE), encoding="utf-8") as handle:
            settings = yaml.safe_load(handle)
    except (OSError, yaml.YAMLError):
        return DEFAULT_DB
    if not isinstance(settings, dict):
        return DEFAULT_DB
    return str(settings.get("database_tags_file") or DEFAULT_DB)


def build_config(
    *,
    data_dir: str | None = None,
    db_file: str | None = None,
    instance: str | None = None,
    shell_history: bool = False,
) -> Config:
    """Разложить аргументы в пути так же, как это делает само приложение.

    Каталог данных — `--data-dir` → `$IDVJPY_DATA_DIR` → каталог запуска с
    `settings.yml` → системный (`src/data_dirs.py`). Каталог **не создаётся**:
    сервер только читает.
    """
    directory = data_dirs.resolve_data_dir(data_dir)
    name = (instance or DEFAULT_INSTANCE).strip() or DEFAULT_INSTANCE
    raw_db = (db_file or "").strip() or settings_db_file(directory)
    path = raw_db if os.path.isabs(raw_db) else os.path.join(directory, raw_db)
    return Config(
        data_dir=directory,
        db_file=os.path.abspath(path),
        history_file=os.path.join(directory, f"history_{name}.txt"),
        instance=name,
        shell_history=shell_history,
    )


def server_version() -> str:
    """Версия приложения без импорта TUI: `VERSION` из `src/app.py` (иначе `dev`).

    Импортировать `app.py` ради строки нельзя — серверу не нужен Textual (и его
    старт). Тест сверяет результат с `CommandRunner.VERSION`, чтобы расхождение
    после `bump_version.py` не прошло незамеченным.
    """
    app_file = Path(__file__).resolve().parent / "app.py"
    try:
        match = re.search(r'^    VERSION = "(v[0-9.]+)"', app_file.read_text(encoding="utf-8"), re.M)
    except OSError:
        return "dev"
    return match.group(1) if match else "dev"


# --- аргументы инструментов --------------------------------------------------


def _text(args: dict[str, Any], key: str) -> str:
    value = args.get(key)
    return value.strip() if isinstance(value, str) else ""


def _required_text(args: dict[str, Any], key: str) -> str:
    value = _text(args, key)
    if not value:
        raise ToolError(f"argument '{key}' is required and must be a non-empty string")
    return value


def _flag(args: dict[str, Any], key: str) -> bool:
    value = args.get(key)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return False


def _limit(args: dict[str, Any], *, default: int = DEFAULT_LIMIT) -> int:
    value = args.get("limit")
    if value is None or value == "":
        return default
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ToolError(f"argument 'limit' must be an integer, got {value!r}") from None
    if number <= 0:
        raise ToolError("argument 'limit' must be positive")
    return min(number, MAX_LIMIT)


def _require_db(cfg: Config) -> None:
    """База должна существовать: сервер её не создаёт (только чтение)."""
    if not os.path.isfile(cfg.db_file):
        raise ToolError(
            f"library database not found: {cfg.db_file}. "
            "Start the TUI once (it creates the file) or pass --db / --data-dir."
        )


def _cell(row: Any, key: str) -> str:
    """Значение колонки строкой; колонки может не быть в выборке."""
    try:
        value = row[key]
    except (IndexError, KeyError):
        return ""
    return "" if value is None else str(value)


def _command_line(row: Any, *, tag: str | None = None) -> str:
    name = tag if tag is not None else _cell(row, "tag")
    line = f"{name}[{_cell(row, 'tid')}]  {_cell(row, 'command')}"
    comment = _cell(row, "comment").strip()
    if comment:
        line += f"  # {comment}"
    return line


def _cut(lines: list[str], limit: int) -> list[str]:
    """Обрезать список и сказать, сколько осталось (модель это учитывает)."""
    if len(lines) <= limit:
        return lines
    return [*lines[:limit], f"... {len(lines) - limit} more (raise 'limit')"]


# --- инструменты -------------------------------------------------------------


def tool_search_commands(cfg: Config, args: dict[str, Any]) -> str:
    """Подстрочный поиск по командам и комментариям библиотеки (как `?text`)."""
    query = _required_text(args, "query")
    tag = _text(args, "tag")
    limit = _limit(args)
    _require_db(cfg)
    rows, _total = database.search_commands_by_content(cfg.db_file, query, limit=MAX_LIMIT)
    if tag:
        wanted = tag.lower()
        rows = [row for row in rows if _cell(row, "tag").lower() == wanted]
    found = len(rows)
    where = f' for "{query}"' + (f" in tag '{tag}'" if tag else "")
    if not found:
        hint = "" if database.has_live_commands(cfg.db_file) else " (the library has no live commands at all)"
        return f"no match{where}{hint}"
    lines = _cut([_command_line(row) for row in rows], limit)
    return f"{found} match(es){where}:\n" + "\n".join(lines)


def tool_list_tags(cfg: Config, args: dict[str, Any]) -> str:
    """Теги с числом живых команд и комментариями (как `?`)."""
    include_hidden = _flag(args, "include_hidden")
    _require_db(cfg)
    rows = database.get_all_commands_with_ids(cfg.db_file)
    comments = {str(tag): str(comment or "") for tag, comment in database.get_all_tags_with_comments(cfg.db_file)}
    counts = Counter(_cell(row, "tag") for row in rows)
    hidden = database.get_hidden_tags(cfg.db_file)
    lines = [f"{len(counts)} tag(s), {len(rows)} live command(s), {len(hidden)} hidden"]
    for tag in sorted(counts):
        comment = comments.get(tag, "").strip()
        lines.append(f"  {tag}  ({counts[tag]})" + (f"  # {comment}" if comment else ""))
    if include_hidden and hidden:
        lines.append("hidden tags (only soft-deleted rows): " + ", ".join(hidden))
    elif hidden:
        lines.append(f"{len(hidden)} hidden tag(s) not listed (include_hidden=true)")
    return "\n".join(lines)


def tool_get_tag(cfg: Config, args: dict[str, Any]) -> str:
    """Все живые команды тега с tid и комментариями (как `?tag`)."""
    tag = _required_text(args, "tag")
    limit = _limit(args)
    _require_db(cfg)
    rows = database.get_commands_by_tag(cfg.db_file, tag)
    if not rows:
        if tag in database.get_hidden_tags(cfg.db_file):
            raise ToolError(
                f"tag '{tag}' has only soft-deleted rows "
                "(restore them in the TUI with `#%s!`)" % tag
            )
        raise ToolError(f"tag '{tag}' not found")
    comment = database.get_tag_comment(cfg.db_file, tag).strip()
    header = f"{tag}: {len(rows)} live command(s)" + (f"  # {comment}" if comment else "")
    return header + "\n" + "\n".join(_cut([_command_line(row, tag=tag) for row in rows], limit))


def tool_search_history(cfg: Config, args: dict[str, Any]) -> str:
    """Поиск по истории сессии (или по истории оболочек — с явного разрешения)."""
    query = _text(args, "query")
    limit = _limit(args)
    source = (_text(args, "source") or "session").lower()
    if source not in HISTORY_SOURCES:
        raise ToolError(f"argument 'source' must be one of: {', '.join(HISTORY_SOURCES)}")
    if source in ("shells", "all") and not cfg.shell_history:
        raise ToolError(
            "source=shells reads the shell's own history files (bash/zsh/fish/…) — "
            "restart the server with --shell-history to allow it"
        )
    matches: list[str] = []
    notes: list[str] = []
    if source in ("session", "all"):
        lines, _key = history_store.read_history_file_lines(cfg.history_file)
        if not lines:
            notes.append(f"no session history at {cfg.history_file}")
        matches += [f"session  {line}" for line in lines]
    if source in ("shells", "all"):
        for result in history_import.read_sources(limit=SHELL_HISTORY_LIMIT):
            if result.error:
                notes.append(f"{result.shell}: {result.error}")
                continue
            matches += [f"{result.shell}  {line}" for line in result.commands]
    needle = query.lower()
    found = [line for line in dict.fromkeys(matches) if needle in line.lower()]
    header = f"history ({source}): {len(found)} line(s)"
    if query:
        header += f' matching "{query}"'
    body = _cut(found, limit)
    tail = notes[:5]
    return "\n".join([header, *body, *tail]) if (body or tail) else header


def tool_library_stats(cfg: Config, args: dict[str, Any]) -> str:
    """Сводка по библиотеке: размеры, что реально запускается (как `:stats`)."""
    _require_db(cfg)
    stats = database.usage_stats(cfg.db_file)
    lines = [
        f"library: {stats['live']} live, {stats['deleted']} soft-deleted, "
        f"{stats['tags']} tag(s), {stats['never_run']} never run"
    ]
    top = stats.get("top") or []
    if top:
        lines.append("most used commands:")
        lines += [_command_line(row) + f"  (runs: {_cell(row, 'use_count')})" for row in top[:10]]
    per_tag = [row for row in (stats.get("per_tag") or []) if row.get("runs")]
    if per_tag:
        lines.append("most used tags:")
        lines += [
            f"  {row['tag']}  ({row['live']} command(s), {row['runs']} run(s))"
            for row in per_tag[:10]
        ]
    return "\n".join(lines)


# --- описания инструментов (их читает модель, поэтому по-английски) -----------


def _schema(properties: dict[str, Any], required: tuple[str, ...] = ()) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(required),
        "additionalProperties": False,
    }


TOOLS: tuple[dict[str, Any], ...] = (
    {
        "name": "search_commands",
        "description": (
            "Search the user's saved commands (tag library) by substring, the same way "
            "the app's `?text` does: it matches command text and comments, "
            "case-insensitively. Returns `tag[tid]  command  # comment` lines."
        ),
        "inputSchema": _schema(
            {
                "query": {"type": "string", "description": "Substring to look for."},
                "tag": {"type": "string", "description": "Only this tag."},
                "limit": {"type": "integer", "description": f"Max lines (default {DEFAULT_LIMIT})."},
            },
            ("query",),
        ),
        "handler": tool_search_commands,
    },
    {
        "name": "list_tags",
        "description": (
            "List tags of the library with the number of live commands and tag comments. "
            "Use it to see which domains the user has covered (k8s, git, docker, …)."
        ),
        "inputSchema": _schema(
            {
                "include_hidden": {
                    "type": "boolean",
                    "description": "Also list tags that have only soft-deleted commands.",
                }
            }
        ),
        "handler": tool_list_tags,
    },
    {
        "name": "get_tag",
        "description": "All live commands of one tag, with tid and comments (like `?tag` in the app).",
        "inputSchema": _schema(
            {
                "tag": {"type": "string", "description": "Tag name."},
                "limit": {"type": "integer", "description": f"Max lines (default {DEFAULT_LIMIT})."},
            },
            ("tag",),
        ),
        "handler": tool_get_tag,
    },
    {
        "name": "search_history",
        "description": (
            "Search what the user actually typed: the current session history file by "
            "default, or the shell's own history (bash/zsh/fish/atuin) when the server "
            "was started with --shell-history."
        ),
        "inputSchema": _schema(
            {
                "query": {"type": "string", "description": "Substring; empty lists recent lines."},
                "source": {
                    "type": "string",
                    "enum": list(HISTORY_SOURCES),
                    "description": "session (default) | shells | all.",
                },
                "limit": {"type": "integer", "description": f"Max lines (default {DEFAULT_LIMIT})."},
            }
        ),
        "handler": tool_search_history,
    },
    {
        "name": "library_stats",
        "description": (
            "Overview of the library: how many commands and tags, which commands are "
            "actually used (run counters from the app) and which were never run."
        ),
        "inputSchema": _schema({}),
        "handler": tool_library_stats,
    },
)

TOOL_BY_NAME = {str(tool["name"]): tool for tool in TOOLS}


# --- JSON-RPC ----------------------------------------------------------------


def _result(ident: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": ident, "result": result}


def _error(ident: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": ident, "error": {"code": code, "message": message}}


def _initialize(params: dict[str, Any]) -> dict[str, Any]:
    requested = params.get("protocolVersion")
    version = requested if requested in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0]
    return {
        "protocolVersion": version,
        "capabilities": {"tools": {"listChanged": False}},
        "serverInfo": {"name": SERVER_NAME, "title": SERVER_TITLE, "version": server_version()},
        "instructions": INSTRUCTIONS,
    }


def _tool_spec(tool: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": tool["name"],
        "description": tool["description"],
        "inputSchema": tool["inputSchema"],
    }


def _call_tool(ident: Any, params: dict[str, Any], cfg: Config) -> dict[str, Any]:
    name = params.get("name")
    tool = TOOL_BY_NAME.get(str(name))
    if tool is None:
        return _error(ident, -32602, f"Unknown tool: {name!r}")
    arguments = params.get("arguments") or {}
    if not isinstance(arguments, dict):
        return _error(ident, -32602, "Invalid params: 'arguments' must be an object")
    try:
        text = str(tool["handler"](cfg, arguments))
    except ToolError as exc:
        return _result(ident, {"content": [{"type": "text", "text": str(exc)}], "isError": True})
    return _result(ident, {"content": [{"type": "text", "text": text}], "isError": False})


def handle_message(message: Any, cfg: Config) -> dict[str, Any] | None:
    """Ответ на одно сообщение клиента; None — отвечать не нужно (уведомление)."""
    if not isinstance(message, dict):
        return _error(None, -32600, "Invalid Request: expected a JSON-RPC object")
    method = message.get("method")
    if not isinstance(method, str):
        return None  # ответ клиента на наш запрос — пропускаем
    ident = message.get("id")
    params = message.get("params")
    params = params if isinstance(params, dict) else {}
    if method == "initialize":
        return _result(ident, _initialize(params))
    if method == "ping":
        return _result(ident, {})
    if method == "tools/list":
        return _result(ident, {"tools": [_tool_spec(tool) for tool in TOOLS]})
    if method == "tools/call":
        return _call_tool(ident, params, cfg)
    if method.startswith("notifications/"):
        return None
    return _error(ident, -32601, f"Method not found: {method}")


def serve(stdin: Any, stdout: Any, cfg: Config, *, stderr: Any = None) -> None:
    """Цикл stdio: строка — сообщение. В stdout только JSON-RPC, ошибки — в stderr."""
    log = sys.stderr if stderr is None else stderr
    for raw in stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except ValueError:
            response: Any = _error(None, -32700, "Parse error")
        else:
            if isinstance(message, list):
                responses = [
                    answer
                    for answer in (handle_message(item, cfg) for item in message)
                    if answer is not None
                ]
                response = responses or None
            else:
                response = handle_message(message, cfg)
        if response is None:
            continue
        try:
            stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            stdout.flush()
        except OSError as exc:
            print(f"mcp: cannot write to stdout: {exc}", file=log)
            return


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="IDvjPy_term MCP server (read-only, stdio) — exposes the tag library to AI clients",
    )
    parser.add_argument("--data-dir", default=None, help="Data directory (default: $IDVJPY_DATA_DIR / settings.yml cwd / system)")
    parser.add_argument("--db", default=None, help="SQLite library file (default: database_tags_file from settings.yml)")
    parser.add_argument("--instance", default=DEFAULT_INSTANCE, help="Session name for history_<instance>.txt")
    parser.add_argument(
        "--shell-history",
        action="store_true",
        help="Allow source=shells in search_history (reads the shell's own history files)",
    )
    args = parser.parse_args(argv)
    cfg = build_config(
        data_dir=args.data_dir,
        db_file=args.db,
        instance=args.instance,
        shell_history=args.shell_history,
    )
    print(
        f"mcp: {SERVER_NAME} {server_version()} — library {cfg.db_file}, "
        f"history {os.path.basename(cfg.history_file)}, shell history "
        f"{'on' if cfg.shell_history else 'off'}",
        file=sys.stderr,
    )
    serve(sys.stdin, sys.stdout, cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
