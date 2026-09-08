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
    LlmError,
    _extract_text,
    build_body,
    build_headers,
    load_providers,
    perform_request,
)

DS_CFG = {
    "url": "https://api.deepseek.com/chat/completions",
    "model": "deepseek-chat",
    "system": "You are helpful.",
    "timeout": 5,
    "headers": {"Content-Type": "application/json", "Authorization": "Bearer $DEEPSEEK_API_KEY"},
    "response_path": "choices.0.message.content",
}


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
    def boom(request, timeout):
        raise urllib.error.HTTPError("u", 401, "Unauthorized", {}, io.BytesIO(b"bad key"))

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
