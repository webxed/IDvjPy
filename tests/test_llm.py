"""`:llm <provider> <message>` — запрос к LLM через API (фича llm).

Конфиг llm_providers.yml описывает URL/заголовки/тело/response_path.
Сеть не дёргаем: urllib и perform_request подменяются заглушками.
"""
import io
import json
import urllib.error

import pytest

pytestmark = pytest.mark.slow

import llm_client
from llm_client import (
    MAX_HISTORY_TURNS,
    LlmError,
    _extract_text,
    append_exchange,
    build_body,
    build_headers,
    expand_file_refs,
    history_turns_for,
    load_providers,
    perform_request,
    trim_history,
)

DS_CFG = {
    "url": "https://api.deepseek.com/chat/completions",
    "model": "deepseek-chat",
    "system": "You are helpful.",
    "timeout": 5,
    "headers": {"Content-Type": "application/json", "Authorization": "Bearer $DEEPSEEK_API_KEY"},
    "response_path": "choices.0.message.content",
}


def test_expand_file_refs_inlines_utf8_text(tmp_path):
    note = tmp_path / "note.txt"
    note.write_text("hello\nworld\n", encoding="utf-8")
    text, attachments = expand_file_refs("analyze @note.txt please", str(tmp_path))
    assert "```note.txt\nhello\nworld\n```" in text
    assert text.startswith("analyze ") and text.endswith(" please")
    assert attachments == [(str(note), len("hello\nworld\n"))]


def test_expand_file_refs_multiple_and_escaped(tmp_path):
    (tmp_path / "a.py").write_text("A=1\n", encoding="utf-8")
    (tmp_path / "b.log").write_text("B\n", encoding="utf-8")
    text, attachments = expand_file_refs("@a.py @@literal user@host @b.log", str(tmp_path))
    assert "A=1" in text and "B" in text
    assert "@@literal" in text and "user@host" in text  # не раскрываются
    assert [p.rsplit("/", 1)[-1] for p, _ in attachments] == ["a.py", "b.log"]


def test_expand_file_refs_safe_fence(tmp_path):
    (tmp_path / "md.md").write_text("a\n```\nb\n", encoding="utf-8")
    text, _ = expand_file_refs("@md.md", str(tmp_path))
    assert "````md.md" in text  # ограждение длиннее бэктиков в файле
    assert text.rstrip().endswith("````")


def test_expand_file_refs_errors(tmp_path):
    with pytest.raises(LlmError, match="Cannot read"):
        expand_file_refs("@missing.txt", str(tmp_path))
    (tmp_path / "dir").mkdir()
    with pytest.raises(LlmError, match="directory"):
        expand_file_refs("@dir", str(tmp_path))
    (tmp_path / "big.txt").write_text("x" * 50, encoding="utf-8")
    with pytest.raises(LlmError, match="too large"):
        expand_file_refs("@big.txt", str(tmp_path), max_bytes=10)
    (tmp_path / "bin.dat").write_bytes(b"\x00\x01")
    with pytest.raises(LlmError, match="binary"):
        expand_file_refs("@bin.dat", str(tmp_path))


def test_expand_file_refs_no_refs_keeps_text(tmp_path):
    text, attachments = expand_file_refs("just a message", str(tmp_path))
    assert text == "just a message" and attachments == []


def test_history_turns_for_clamps():
    assert history_turns_for({}) == 0
    assert history_turns_for({"history_turns": 3}) == 3
    assert history_turns_for({"history_turns": "2"}) == 2
    assert history_turns_for({"history_turns": -5}) == 0
    assert history_turns_for({"history_turns": "oops"}) == 0
    assert history_turns_for({"history_turns": 10_000}) == MAX_HISTORY_TURNS


def test_trim_history_and_append_exchange():
    msgs = [
        {"role": "user", "content": "u1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "u2"},
        {"role": "assistant", "content": "a2"},
    ]
    assert trim_history(msgs, 1) == msgs[-2:]
    assert trim_history(msgs, 0) == []
    assert trim_history(msgs, 5) == msgs
    assert append_exchange([], "hi", "yo", 1) == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "yo"},
    ]
    capped = append_exchange(append_exchange([], "hi", "yo", 1), "hi2", "yo2", 1)
    assert capped == [
        {"role": "user", "content": "hi2"},
        {"role": "assistant", "content": "yo2"},
    ]


def test_trim_history_drops_dangling_assistant():
    msgs = [
        {"role": "assistant", "content": "a0"},
        {"role": "user", "content": "u1"},
        {"role": "assistant", "content": "a1"},
    ]
    assert trim_history(msgs, 2) == msgs[1:]


def test_default_body_includes_history():
    provider = {"model": "m", "system": "sys"}
    history = [
        {"role": "user", "content": "u1"},
        {"role": "assistant", "content": "a1"},
    ]
    body = json.loads(build_body(provider, "now", {}, history))
    assert [m["role"] for m in body["messages"]] == ["system", "user", "assistant", "user"]
    assert body["messages"][-1]["content"] == "now"
    assert [m["role"] for m in json.loads(build_body(provider, "now", {}))["messages"]] == [
        "system",
        "user",
    ]


def test_template_history_placeholder():
    provider = {"model": "m", "body": '{"model":%MODEL%,"messages":%HISTORY%}'}
    history = [{"role": "user", "content": "u1"}]
    assert json.loads(build_body(provider, "now", {}, history))["messages"] == history


def test_load_providers_missing_file():
    with pytest.raises(LlmError, match="Config not found"):
        load_providers("/no/such/llm_providers.yml")


def test_default_body_is_openai_compatible_json():
    body = json.loads(build_body(DS_CFG, 'hi "quoted" \n', {"DEEPSEEK_API_KEY": "k"}))
    assert body["model"] == "deepseek-chat"
    assert body["stream"] is False
    assert body["messages"][0] == {"role": "system", "content": "You are helpful."}
    assert body["messages"][1]["content"] == 'hi "quoted" \n'


def test_custom_body_placeholders_json_escaped():
    provider = {"model": "m1", "system": "sys", "body": '{"c": %MSG%, "m": %MODEL%, "s": %SYSTEM%}'}
    raw = build_body(provider, 'a "b"', {})
    payload = json.loads(raw)
    assert payload == {"c": 'a "b"', "m": "m1", "s": "sys"}


def test_raw_placeholder_not_escaped():
    provider = {"model": "m1", "body": "echo:%MSG_RAW%:%MODEL%"}
    assert build_body(provider, "line1\nline2", {}) == 'echo:line1\nline2:"m1"'


def test_headers_env_missing_is_explicit():
    with pytest.raises(LlmError, match="Missing env variable\\(s\\).*DEEPSEEK_API_KEY"):
        build_headers(DS_CFG, {})


def test_headers_env_resolved():
    headers = build_headers(DS_CFG, {"DEEPSEEK_API_KEY": "secret"})
    assert headers["Authorization"] == "Bearer secret"


def test_extract_text_heuristics_and_path():
    payload = {"choices": [{"message": {"content": "hello-llm"}}]}
    assert _extract_text(payload, None) == "hello-llm"
    assert _extract_text(payload, "choices.0.message.content") == "hello-llm"
    assert _extract_text("plain answer", "choices.0.nope") == "plain answer"
    with pytest.raises(LlmError, match="response_path"):
        _extract_text({"a": 1}, "choices.0.nope")


def test_answer_language_rule_appended_to_system():
    base = {"model": "m", "system": "You are a helpful assistant."}
    no_lang = json.loads(build_body(base, "hi", {}))
    assert no_lang["messages"][0]["content"] == "You are a helpful assistant."

    with_lang = dict(base, answer_language="Russian")
    body = json.loads(build_body(with_lang, "hi", {}))
    system = body["messages"][0]["content"]
    assert "You are a helpful assistant." in system
    assert "always answer in russian" in system.lower()
    assert "Chinese" in system

    # Пользовательский шаблон тоже получает правило через %SYSTEM%.
    templated = dict(base, answer_language="Russian", body='{"s": %SYSTEM%}')
    payload = json.loads(build_body(templated, "hi", {}))
    assert "always answer in russian" in payload["s"].lower()

    # Без system, но с языком — правило само по себе системный промпт.
    only_lang = {"model": "m", "answer_language": "Russian"}
    body = json.loads(build_body(only_lang, "hi", {}))
    assert body["messages"][0]["content"] == llm_client._effective_system(only_lang)


def test_perform_request_success(monkeypatch):
    body = {"choices": [{"message": {"content": "answer-42"}}]}

    def fake_urlopen(request, timeout):
        assert request.headers["Authorization"] == "Bearer secret"
        assert timeout == 5
        return io.BytesIO(json.dumps(body).encode("utf-8"))

    monkeypatch.setattr(llm_client.urllib.request, "urlopen", fake_urlopen)
    env = {"DEEPSEEK_API_KEY": "secret"}
    assert perform_request(DS_CFG, "привет", env, timeout=5) == "answer-42"


def test_perform_request_http_error(monkeypatch):
    from typing import Any, cast

    def boom(request, timeout):
        raise urllib.error.HTTPError(
            "u", 401, "Unauthorized", cast(Any, {}), io.BytesIO(b"bad key")
        )

    monkeypatch.setattr(llm_client.urllib.request, "urlopen", boom)
    with pytest.raises(LlmError, match="HTTP 401"):
        perform_request(DS_CFG, "hi", {"DEEPSEEK_API_KEY": "x"}, timeout=2)


def test_llm_completion_items(isolated_home):
    from app import CommandRunner

    (isolated_home / "llm_providers.yml").write_text(
        "default: ds\nproviders:\n  ds:\n    url: http://x\n    model: deepseek-chat\n"
        "  openai:\n    url: http://x\n    model: gpt-4o-mini\n",
        encoding="utf-8",
    )
    app = CommandRunner()
    items, preview = app.get_llm_completions(":llm ", len(":llm "))
    assert preview == ""
    inserts = [i.insert for i in items]
    assert "ds" in inserts and "openai" in inserts
    ds_item = next(i for i in items if i.insert == "ds")
    assert ds_item.replace_token is True
    assert ds_item.add_space is True
    assert "(default)" in ds_item.display
    # По префиксу; после начала сообщения/пробела список не показываем.
    items, _ = app.get_llm_completions(":llm o", len(":llm o"))
    assert [i.insert for i in items] == ["openai"]
    assert app.get_llm_completions(":llm ds hi", 10) == ([], "")
    assert app.get_llm_completions(":llm ds ", len(":llm ds ")) == ([], "")


def test_llm_completion_without_config_empty(isolated_home):
    from app import CommandRunner

    app = CommandRunner()
    assert app.get_llm_completions(":llm ", len(":llm ")) == ([], "")


async def test_llm_tab_applies_provider_name(isolated_home):
    from app import CommandRunner
    from tests.conftest import input_widget

    (isolated_home / "llm_providers.yml").write_text(
        "providers:\n  ds:\n    url: http://x\n    model: m\n", encoding="utf-8"
    )
    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        await pilot.pause()
        inp = input_widget(app)
        inp.value = ":llm d"
        inp.cursor_position = len(":llm d")
        await pilot.pause()
        assert app._completion_list is not None and app._completion_list.is_visible()
        assert app._completion_list.total_candidates == 1
        await pilot.press("tab")
        await pilot.pause()
        # Подстановка заменила только токен имени, префикс :llm сохранён.
        assert inp.value == ":llm ds "


async def test_llm_enter_applies_provider_not_submits(isolated_home):
    """Enter при открытом списке провайдеров применяет имя, не выполняет :llm."""
    from app import CommandRunner
    from tests.conftest import info_texts, input_widget

    (isolated_home / "llm_providers.yml").write_text(
        "providers:\n  ds:\n    url: http://x\n    model: m\n", encoding="utf-8"
    )
    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        await pilot.pause()
        inp = input_widget(app)
        inp.value = ":llm "
        inp.cursor_position = len(":llm ")
        await pilot.pause()
        assert app._completion_list.is_visible()
        infos_before = len(info_texts(app))
        await pilot.press("enter")
        await pilot.pause()
        # Провайдер применён, команда НЕ выполнена, ввод готов к сообщению.
        assert inp.value == ":llm ds "
        assert len(info_texts(app)) == infos_before
        assert not app._completion_list.is_visible()


def test_perform_request_407_hint_when_no_proxy_creds(monkeypatch):
    def tunnel_407(request, timeout):
        raise urllib.error.URLError(
            OSError("Tunnel connection failed: 407 Proxy Authentication Required")
        )

    monkeypatch.setattr(llm_client.urllib.request, "urlopen", tunnel_407)
    with pytest.raises(LlmError) as exc:
        perform_request(DS_CFG, "hi", {"DEEPSEEK_API_KEY": "x"}, timeout=2)
    text = str(exc.value)
    assert "407" in text
    assert "Proxy requires login" in text
    assert "PROXY_USER" in text


def test_perform_request_uses_authenticated_proxy(monkeypatch):
    def fake_open(request, timeout, env):
        return io.BytesIO(
            json.dumps({"choices": [{"message": {"content": "via-proxy"}}]}).encode()
        )

    monkeypatch.setattr(llm_client, "_open_request", fake_open)
    env = {
        "DEEPSEEK_API_KEY": "x",
        "PROXY_USER": "u",
        "PROXY_PASS": "p",
        "HTTPS_PROXY": "http://proxy:8080",
    }
    assert perform_request(DS_CFG, "hi", env, timeout=2) == "via-proxy"


async def test_colon_llm_default_provider_without_name(isolated_home, monkeypatch):
    """:llm <свободный текст> уходит провайдеру по умолчанию (default:)."""
    import app as app_module

    (isolated_home / "llm_providers.yml").write_text(
        "default: ds\nproviders:\n"
        "  ds:\n    url: http://x\n    model: deepseek-chat\n"
        "  openai:\n    url: http://x\n    model: gpt\n",
        encoding="utf-8",
    )
    calls: list[tuple] = []

    def fake(provider, message, env, timeout=60):
        calls.append((provider["model"], message))
        return "default-answer"

    monkeypatch.setattr(app_module, "perform_request", fake)

    from app import CommandRunner
    from tests.conftest import submit, wait_command_done

    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        await submit(pilot, ":llm Привет как дела?")
        block = await wait_command_done(app, timeout=8.0)
        assert block.raw_stdout.strip() == "default-answer"
    # Провайдер по умолчанию и полное сообщение.
    assert calls == [("deepseek-chat", "Привет как дела?")]


async def test_colon_llm_sends_block_output_tokens(isolated_home, monkeypatch):
    """:llm раскрывает $OUT (последняя строка) и $BLOCK (весь stdout)."""
    import app as app_module

    (isolated_home / "llm_providers.yml").write_text(
        "default: ds\nproviders:\n  ds:\n    url: http://x\n    model: m\n",
        encoding="utf-8",
    )
    calls: list[str] = []

    def fake(provider, message, env, timeout=60):
        calls.append(message)
        return "ok"

    monkeypatch.setattr(app_module, "perform_request", fake)

    from app import CommandRunner
    from tests.conftest import submit, wait_command_done

    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        # $BLOCK: весь stdout сфокусированного/последнего CommandBlock.
        await submit(pilot, "printf 'l1\\nl2\\n'")
        await wait_command_done(app, timeout=8.0)
        await submit(pilot, ":llm $BLOCK привет")
        await wait_command_done(app, timeout=8.0)
        # $OUT: последняя непустая строка блока (свежий блок перед вызовом).
        await submit(pilot, "printf 'x1\\nx2\\n'")
        await wait_command_done(app, timeout=8.0)
        await submit(pilot, ":llm ds $OUT")
        await wait_command_done(app, timeout=8.0)
    assert calls == ["l1\nl2 привет", "x2"]


async def test_colon_llm_multi_turn_context_and_reset(isolated_home, monkeypatch):
    """history_turns: контекст пары уходит в следующий запрос; :llm reset чистит."""
    import app as app_module

    (isolated_home / "llm_providers.yml").write_text(
        "default: ds\nproviders:\n  ds:\n    url: http://x\n    model: m\n"
        "    history_turns: 2\n",
        encoding="utf-8",
    )
    calls: list[tuple[str, list]] = []

    def fake(provider, message, env, timeout=60, history=None):
        calls.append((message, list(history or [])))
        return f"ans-{len(calls)}"

    monkeypatch.setattr(app_module, "perform_request", fake)

    from app import CommandRunner, InfoBlock
    from tests.conftest import submit, wait_command_done

    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        await submit(pilot, ":llm first")
        await wait_command_done(app, timeout=8.0)
        await submit(pilot, ":llm second")
        block2 = await wait_command_done(app, timeout=8.0)

        # Второй запрос несёт первую пару; в шапке — счётчик контекста.
        assert calls[1] == (
            "second",
            [
                {"role": "user", "content": "first"},
                {"role": "assistant", "content": "ans-1"},
            ],
        )
        assert "ctx: 1/2 turns" in block2.header
        assert app._llm_threads["ds"] == [
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "ans-1"},
            {"role": "user", "content": "second"},
            {"role": "assistant", "content": "ans-2"},
        ]

        # :llm reset — ветка провайдера по умолчанию очищается.
        await submit(pilot, ":llm reset")
        texts = " ".join(b.text_content for b in app.query(InfoBlock))
        assert "LLM context reset: ds (2 turns)" in texts
        assert app._llm_threads.get("ds") is None

        await submit(pilot, ":llm third")
        await wait_command_done(app, timeout=8.0)
        assert calls[2][0] == "third" and calls[2][1] == []


def test_llm_attachment_completions(isolated_home):
    """`:llm ds … @no` → подсказка @notes.md (только токен файла)."""
    (isolated_home / "notes.md").write_text("x", encoding="utf-8")
    from app import CommandRunner

    app = CommandRunner()
    items, preview = app.get_llm_completions(":llm ds see @no", len(":llm ds see @no"))
    assert [item.insert for item in items] == ["@notes.md"]
    assert preview == ""


async def test_colon_llm_attaches_file_and_keeps_source(isolated_home, monkeypatch):
    """`:llm … @file` шлёт содержимое, а в source_command/истории остаётся @file."""
    import app as app_module

    (isolated_home / "llm_providers.yml").write_text(
        "default: ds\nproviders:\n  ds:\n    url: http://x\n    model: m\n",
        encoding="utf-8",
    )
    (isolated_home / "note.txt").write_text("HELLO-ATTACH\n", encoding="utf-8")
    calls: list[str] = []

    def fake(provider, message, env, timeout=60):
        calls.append(message)
        return "ok"

    monkeypatch.setattr(app_module, "perform_request", fake)

    from app import CommandRunner
    from tests.conftest import submit, wait_command_done

    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        await submit(pilot, ":llm summarize @note.txt")
        block = await wait_command_done(app, timeout=8.0)

    assert len(calls) == 1
    assert "summarize" in calls[0] and "HELLO-ATTACH" in calls[0]
    # Содержимое не оседает в source_command (нужно для :r) и в истории ввода.
    assert "@note.txt" in block.source_command
    assert "HELLO-ATTACH" not in block.source_command
    assert "@files: note.txt" in block.header
    history = (isolated_home / "history_default.txt").read_text(encoding="utf-8")
    assert ":llm summarize @note.txt" in history
    assert "HELLO-ATTACH" not in history


async def test_colon_llm_output_tokens_without_block(isolated_home):
    from app import CommandRunner
    from tests.conftest import last_info, submit

    (isolated_home / "llm_providers.yml").write_text(
        "providers:\n  ds:\n    url: http://x\n    model: m\n", encoding="utf-8"
    )
    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        await pilot.pause()
        await submit(pilot, ":llm ds $OUT")
        assert "$OUT / $BLOCK need a finished command block" in last_info(app).text_content


async def test_llm_recorded_in_history_but_not_in_hints(isolated_home, monkeypatch):
    """:llm пишется в history_*.txt (для ↑/:h), но не предлагается в подсказках."""
    import app as app_module

    (isolated_home / "llm_providers.yml").write_text(
        "providers:\n  ds:\n    url: http://x\n    model: m\n", encoding="utf-8"
    )
    monkeypatch.setattr(app_module, "perform_request", lambda *a, **k: "ok")

    from app import CommandRunner
    from tests.conftest import submit, wait_command_done

    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        await submit(pilot, ":llm ds привет")
        await wait_command_done(app, timeout=8.0)
        hist_path = isolated_home / "history_default.txt"
        lines = hist_path.read_text(encoding="utf-8").splitlines()
        assert ":llm ds привет" in lines
        # В подсказках (Tab) запрос-вопрос не предлагается.
        assert app.get_completion_candidates(":llm d") == []
        # Но доступен для поиска по истории.
        assert any(":llm ds привет" in line for line in app._history_pool())
        # Другие colon-команды по-прежнему в историю не пишутся.
        await submit(pilot, ":stats")
        lines = hist_path.read_text(encoding="utf-8").splitlines()
        assert not any(line.strip() == ":stats" for line in lines)


async def test_colon_llm_shows_answer(isolated_home, monkeypatch):
    import app as app_module

    (isolated_home / "llm_providers.yml").write_text(
        "default: ds\nproviders:\n  ds:\n"
        "    url: https://api.deepseek.com/chat/completions\n"
        "    model: deepseek-chat\n"
        "    headers:\n      Content-Type: application/json\n"
        "      Authorization: Bearer $DEEPSEEK_API_KEY\n"
        "    response_path: choices.0.message.content\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(app_module, "perform_request", lambda *a, **k: "Привет! Всё отлично.")

    from app import CommandRunner
    from tests.conftest import last_info, submit, wait_command_done

    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        await pilot.pause()
        # Список провайдеров.
        await submit(pilot, ":llm")
        assert "LLM providers:" in last_info(app).text_content
        assert "ds" in last_info(app).text_content
        # Запрос: сообщение из остатка строки.
        await submit(pilot, ":llm ds Привет, как дела?")
        block = await wait_command_done(app, timeout=8.0)
        assert "Привет! Всё отлично." in block.raw_stdout


async def test_colon_llm_errors(isolated_home):
    from app import CommandRunner
    from tests.conftest import last_info, submit

    (isolated_home / "llm_providers.yml").write_text(
        "providers:\n  ds:\n    url: http://x\n    model: m\n", encoding="utf-8"
    )
    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        await pilot.pause()
        await submit(pilot, ":llm ds")
        assert "Usage: :llm [<provider>] <message>" in last_info(app).text_content
        await submit(pilot, ":llm nope hi")
        text = last_info(app).text_content
        assert "unknown provider 'nope'" in text
        assert "no default provider is set" in text
        assert "ds" in text


async def test_colon_llm_missing_config_hint(isolated_home):
    from app import CommandRunner
    from tests.conftest import last_info, submit

    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        await pilot.pause()
        await submit(pilot, ":llm ds hi")
        text = last_info(app).text_content
        assert "Config not found" in text
        assert "llm_providers.example.yml" in text
