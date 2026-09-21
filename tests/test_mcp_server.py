"""MCP-сервер (`src/mcp_server.py`): JSON-RPC на stdio поверх библиотеки.

Проверяем: конфигурацию (каталог данных и путь к базе — как у приложения),
протокол (`initialize` / `tools/list` / `tools/call`, ошибки и уведомления),
работу инструментов на живой базе и **инварианты**: только чтение, никаких
секретов, никакой сети, в stdout — только сообщения JSON-RPC.
"""
from __future__ import annotations

import hashlib
import io
import json
import pathlib
import re
import subprocess
import sys

import pytest

import database_v2 as database
import mcp_server
import seed_sqlite

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _data_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    (tmp_path / "settings.yml").write_text("database_tags_file: mytags.db\n", encoding="utf-8")
    return tmp_path


def _cfg(tmp_path: pathlib.Path, **kwargs) -> mcp_server.Config:
    directory = _data_dir(tmp_path)
    return mcp_server.build_config(data_dir=str(directory), **kwargs)


def _seeded(tmp_path: pathlib.Path) -> mcp_server.Config:
    cfg = _cfg(tmp_path)
    seed_sqlite.run_seed(cfg.db_file)
    (tmp_path / "history_default.txt").write_text(
        "echo from-session\nkubectl get pods -A\n", encoding="utf-8"
    )
    return cfg


def _call(cfg: mcp_server.Config, name: str, arguments: dict | None = None) -> dict:
    response = mcp_server.handle_message(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
         "params": {"name": name, "arguments": arguments or {}}},
        cfg,
    )
    assert response is not None
    return response


def _text(response: dict) -> str:
    return response["result"]["content"][0]["text"]


def _serve(cfg: mcp_server.Config, lines: list[str]) -> list[dict]:
    out = io.StringIO()
    mcp_server.serve(io.StringIO("\n".join(lines) + "\n"), out, cfg, stderr=io.StringIO())
    return [json.loads(line) for line in out.getvalue().splitlines()]


# --- конфигурация ------------------------------------------------------------


def test_build_config_reads_settings_and_instance(tmp_path):
    cfg = _cfg(tmp_path)
    assert cfg.data_dir == str(tmp_path)
    assert cfg.db_file == str(tmp_path / "mytags.db")
    assert cfg.history_file == str(tmp_path / "history_default.txt")
    assert cfg.shell_history is False
    named = mcp_server.build_config(data_dir=str(tmp_path), instance="git")
    assert named.history_file == str(tmp_path / "history_git.txt")


def test_build_config_absolute_db_and_env(tmp_path, monkeypatch):
    other = tmp_path / "elsewhere"
    other.mkdir()
    cfg = mcp_server.build_config(data_dir=str(tmp_path), db_file=str(other / "lib.db"))
    assert cfg.db_file == str(other / "lib.db")
    monkeypatch.setenv("IDVJPY_DATA_DIR", str(other))
    assert mcp_server.build_config().data_dir == str(other)


def test_settings_db_file_falls_back(tmp_path):
    assert mcp_server.settings_db_file(str(tmp_path)) == "mytags.db"  # нет settings.yml
    (tmp_path / "settings.yml").write_text("database_tags_file: [broken\n", encoding="utf-8")
    assert mcp_server.settings_db_file(str(tmp_path)) == "mytags.db"  # битый YAML
    (tmp_path / "settings.yml").write_text("database_tags_file: other.db\n", encoding="utf-8")
    assert mcp_server.settings_db_file(str(tmp_path)) == "other.db"


def test_server_version_matches_the_application():
    from app import CommandRunner

    assert mcp_server.server_version() == CommandRunner.VERSION


# --- протокол ----------------------------------------------------------------


def test_tools_list_specs(tmp_path):
    cfg = _cfg(tmp_path)
    response = mcp_server.handle_message({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, cfg)
    tools = response["result"]["tools"]
    names = [tool["name"] for tool in tools]
    assert names == ["search_commands", "list_tags", "get_tag", "search_history", "library_stats"]
    for tool in tools:
        assert tool["description"] and tool["inputSchema"]["type"] == "object"
        assert tool["name"] in mcp_server.TOOL_BY_NAME


def test_initialize_echoes_known_version_and_announces_capabilities(tmp_path):
    cfg = _cfg(tmp_path)
    known = mcp_server.PROTOCOL_VERSIONS[0]
    response = mcp_server.handle_message(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": known, "clientInfo": {"name": "test"}}},
        cfg,
    )
    result = response["result"]
    assert result["protocolVersion"] == known
    assert result["capabilities"]["tools"] == {"listChanged": False}
    assert result["serverInfo"]["name"] == "idvjpy"
    assert "Read-only" in result["instructions"]
    # Неизвестная версия протокола — отвечаем своей, а не падаем.
    unknown = mcp_server.handle_message(
        {"jsonrpc": "2.0", "id": 2, "method": "initialize", "params": {"protocolVersion": "1999-01-01"}},
        cfg,
    )
    assert unknown["result"]["protocolVersion"] == known


def test_serve_reports_parse_error_and_keeps_reading(tmp_path):
    cfg = _cfg(tmp_path)
    responses = _serve(
        cfg,
        [
            "not json at all",
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}),
            json.dumps([]),
        ],
    )
    assert responses[0]["error"]["code"] == -32700  # Parse error
    assert responses[1]["result"] == {}
    assert len(responses) == 2  # пустой batch не отвечает


def test_serve_skips_notifications_and_reports_unknown_method(tmp_path):
    cfg = _cfg(tmp_path)
    responses = _serve(
        cfg,
        [
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
            json.dumps({"jsonrpc": "2.0", "id": 7, "method": "nope"}),
            json.dumps({"jsonrpc": "2.0", "id": 8, "method": "tools/call",
                        "params": {"name": "nope", "arguments": {}}}),
        ],
    )
    assert [r["id"] for r in responses] == [7, 8]
    assert responses[0]["error"]["code"] == -32601
    assert responses[1]["error"]["code"] == -32602


def test_batch_messages_are_answered_as_a_batch(tmp_path):
    cfg = _cfg(tmp_path)
    batch = [
        {"jsonrpc": "2.0", "id": 1, "method": "ping"},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ]
    responses = _serve(cfg, [json.dumps(batch)])
    assert len(responses) == 1 and isinstance(responses[0], list)
    assert [r["id"] for r in responses[0]] == [1, 2]


def test_stdout_carries_only_jsonrpc(tmp_path):
    cfg = _seeded(tmp_path)
    lines = [
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                    "params": {"name": "list_tags", "arguments": {}}}),
    ]
    out = io.StringIO()
    mcp_server.serve(io.StringIO("\n".join(lines) + "\n"), out, cfg, stderr=io.StringIO())
    assert out.getvalue().endswith("\n")
    for line in out.getvalue().splitlines():
        payload = json.loads(line)  # каждая строка — самостоятельное сообщение
        assert payload["jsonrpc"] == "2.0"


# --- инструменты -------------------------------------------------------------


def test_search_commands_finds_commands_and_comments(tmp_path):
    cfg = _seeded(tmp_path)
    text = _text(_call(cfg, "search_commands", {"query": "VACUUM"}))
    assert 'sqlite[13]' in text and "shrink the file" in text
    assert "1 match" in text
    by_comment = _text(_call(cfg, "search_commands", {"query": "integrity"}))
    assert "sqlite[14]" in by_comment
    assert _text(_call(cfg, "search_commands", {"query": "nonesuch"})) == 'no match for "nonesuch"'


def test_search_commands_filters_by_tag_and_limits(tmp_path):
    cfg = _seeded(tmp_path)
    text = _text(_call(cfg, "search_commands", {"query": "deleted", "tag": "sqlstat", "limit": 5}))
    # в тексте есть ссылки `!sqlite[5]`, поэтому смотрим на **начало** строки
    assert "sqlstat[1]" in text
    assert not [line for line in text.splitlines() if line.startswith("sqlite[")]
    limited = _text(_call(cfg, "search_commands", {"query": "deleted", "limit": "3"}))
    command_lines = [line for line in limited.splitlines() if re.match(r"\S+\[\d+\]", line)]
    assert len(command_lines) == 3
    assert "more (raise 'limit')" in limited


def test_list_tags_counts_comments_and_hidden(tmp_path):
    cfg = _seeded(tmp_path)
    text = _text(_call(cfg, "list_tags"))
    assert "3 tag(s), 18 live command(s), 0 hidden" in text
    assert "sqlite  (16)" in text and "sqlite3: schema" in text
    database.delete_commands_by_tag(cfg.db_file, "sqlstat")
    hidden = _text(_call(cfg, "list_tags"))
    assert "1 hidden" in hidden and "include_hidden=true" in hidden
    assert "sqlstat" not in hidden
    listed = _text(_call(cfg, "list_tags", {"include_hidden": True}))
    assert "hidden tags (only soft-deleted rows): sqlstat" in listed


def test_get_tag_lists_commands_and_reports_hidden_or_missing(tmp_path):
    cfg = _seeded(tmp_path)
    text = _text(_call(cfg, "get_tag", {"tag": "sqlstat"}))
    assert "sqlstat: 1 live command(s)" in text and "sqlstat[1]" in text
    database.delete_commands_by_tag(cfg.db_file, "sqlstat")
    hidden = _call(cfg, "get_tag", {"tag": "sqlstat"})
    assert hidden["result"]["isError"] is True
    assert "soft-deleted" in _text(hidden)
    missing = _call(cfg, "get_tag", {"tag": "nonesuch"})
    assert missing["result"]["isError"] is True and "not found" in _text(missing)


def test_search_history_session_file_and_shell_gate(tmp_path):
    cfg = _seeded(tmp_path)
    text = _text(_call(cfg, "search_history", {"query": "kubectl"}))
    assert "history (session): 1 line(s) matching \"kubectl\"" in text
    assert "session  kubectl get pods -A" in text
    assert "echo from-session" not in text
    gated = _call(cfg, "search_history", {"source": "shells"})
    assert gated["result"]["isError"] is True
    assert "--shell-history" in _text(gated)
    bad = _call(cfg, "search_history", {"source": "nope"})
    assert bad["result"]["isError"] is True and "source" in _text(bad)


def test_library_stats_reports_usage(tmp_path):
    cfg = _seeded(tmp_path)
    database.bump_command_usage(cfg.db_file, "sqlite3 $DBFILE \".tables\"")
    text = _text(_call(cfg, "library_stats"))
    assert "18 live, 0 soft-deleted, 3 tag(s)" in text
    assert "17 never run" in text
    assert "most used commands:" in text and "runs: 1" in text


def test_limits_are_validated(tmp_path):
    cfg = _seeded(tmp_path)
    bad = _call(cfg, "search_commands", {"query": "x", "limit": "abc"})
    assert bad["result"]["isError"] is True and "integer" in _text(bad)
    zero = _call(cfg, "search_commands", {"query": "x", "limit": 0})
    assert zero["result"]["isError"] is True and "positive" in _text(zero)
    missing = _call(cfg, "search_commands", {})
    assert missing["result"]["isError"] is True and "'query'" in _text(missing)
    args = _call(cfg, "search_commands", {"query": "x"})
    assert args["result"]["isError"] is False  # пустой ответ — не ошибка инструмента


# --- инварианты --------------------------------------------------------------


def test_missing_library_is_an_error_and_is_not_created(tmp_path):
    cfg = _cfg(tmp_path)
    for tool in ("search_commands", "list_tags", "get_tag", "library_stats"):
        arguments = {"tag": "x"} if tool == "get_tag" else ({"query": "x"} if tool == "search_commands" else {})
        response = _call(cfg, tool, arguments)
        assert response["result"]["isError"] is True, tool
        assert "not found" in _text(response)
    assert not pathlib.Path(cfg.db_file).exists()  # база не создана


def test_library_history_and_secrets_are_untouched(tmp_path):
    cfg = _seeded(tmp_path)
    secret_file = tmp_path / "secrets_default.json"
    secret_file.write_text('{"TOKEN": "super-secret-value"}\n', encoding="utf-8")
    db = pathlib.Path(cfg.db_file)
    history = pathlib.Path(cfg.history_file)
    before = (hashlib.sha256(db.read_bytes()).hexdigest(), history.read_text(encoding="utf-8"))
    texts = [
        _text(_call(cfg, "search_commands", {"query": "sqlite"})),
        _text(_call(cfg, "list_tags", {})),
        _text(_call(cfg, "get_tag", {"tag": "sqlite"})),
        _text(_call(cfg, "search_history", {})),
        _text(_call(cfg, "library_stats", {})),
    ]
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before[0]
    assert history.read_text(encoding="utf-8") == before[1]
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(
        ["settings.yml", "mytags.db", "history_default.txt", "secrets_default.json"]
    )
    assert secret_file.read_text(encoding="utf-8") == '{"TOKEN": "super-secret-value"}\n'
    assert all("super-secret-value" not in text for text in texts)


def test_source_is_read_only_and_offline():
    """Сторож по исходнику: ни записи в БД, ни секретов, ни сети/портов."""
    source = (ROOT / "src" / "mcp_server.py").read_text(encoding="utf-8")
    body = source.split('"""', 2)[-1]  # без докстринга модуля (там это описано)
    for forbidden in (
        "init_db", "add_command", "delete_", "hard_delete", "set_command", "set_tag",
        "update_command", "move_command", "rename_tag", "restore_", "bump_command",
        "secrets_", "socket", "listen", "https", "urlopen",
    ):
        assert forbidden not in body, forbidden
    assert "database.search_commands_by_content" in body  # чтение — из слоя БД


def test_launcher_starts_the_server(tmp_path):
    """Корневой `mcp_server.py` — рабочий лаунчер (кладёт `src/` в sys.path)."""
    cfg = _seeded(tmp_path)
    request = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                          "params": {"name": "list_tags", "arguments": {}}})
    proc = subprocess.run(
        [sys.executable, str(ROOT / "mcp_server.py"), "--data-dir", str(tmp_path)],
        input=request + "\n",
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout.splitlines()[-1])
    assert "3 tag(s), 18 live command(s)" in payload["result"]["content"][0]["text"]
    assert re.search(r"mcp: idvjpy v[0-9.]+", proc.stderr)
    assert str(cfg.db_file) in proc.stderr  # сервер сказал, что читает


def test_help_topic_escapes_literal_brackets():
    """`:? mcp` — Rich-разметка: литеральные `[tid]` обязаны быть экранированы.

    Иначе Rich съест `[tid]` как тег и в справке останется дыра (тема `:? llm`
    сторожится так же).
    """
    from help_texts import help_topic

    body = help_topic("mcp") or ""
    assert "\\[tid]" in body
    assert "[tid]" not in body.replace("\\[tid]", "")


def test_launcher_help_works():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "mcp_server.py"), "--help"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0
    assert "--shell-history" in proc.stdout and "read-only" in proc.stdout


@pytest.mark.parametrize("key", ["tools", "content"])
def test_result_shapes(tmp_path, key):
    """Минимальные требования клиентов: `tools` — список, `content` — текст."""
    cfg = _seeded(tmp_path)
    if key == "tools":
        payload = mcp_server.handle_message({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, cfg)
        assert isinstance(payload["result"]["tools"], list)
    else:
        payload = _call(cfg, "library_stats")
        assert payload["result"]["content"][0] == {
            "type": "text",
            "text": payload["result"]["content"][0]["text"],
        }
