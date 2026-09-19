"""`$$NAME=value` — секретные переменные: ввод и вывод маскируются.

Значение хранится в отдельном `secrets_<instance>.json` (0600), в `.bashrc_term`,
историю и журнал не попадает; в командах подставляется как `$NAME`, а в
отображаемом тексте блока заменяется на `****`.
"""
import os
import stat
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.slow

from app import CommandRunner
from tests.conftest import input_widget, last_info, submit, wait_command_done

SECRET = "supersecret-value"


def test_mask_secrets_unit():
    """`_mask_secrets` прячет значения всех секретов (длинные — первыми)."""
    app = CommandRunner()
    app.local_env["A"] = "s3cr3t"
    app.local_env["B"] = "s3cr3t-longer"
    app._secret_names = {"A", "B"}
    assert app._mask_secrets("x s3cr3t-longer y s3cr3t z") == "x **** y **** z"
    app._secret_names = set()
    assert app._mask_secrets("plain text") == "plain text"


async def test_secret_set_hides_value_and_stores_0600(isolated_home):
    """`$$TOKEN=…` не показывает значение, пишет файл 0600 и не пишет в history."""
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, f"$$TOKEN={SECRET}")
        info = last_info(app).text_content
        assert SECRET not in info
        assert "Secret $TOKEN set" in info
        assert app.local_env.get("TOKEN") == SECRET
        assert os.environ.get("TOKEN") == SECRET

        # Отдельный файл только для владельца, со значением.
        path = app.FILE_SECRETS
        assert os.path.isfile(path)
        assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
        assert SECRET in Path(path).read_text(encoding="utf-8")

        # Значение не утекает в .bashrc_term и history.
        assert SECRET not in Path(app.FILE_BASHRC).read_text(encoding="utf-8")
        hist = Path(app.FILE_HISTORY)
        assert (not hist.exists()) or (SECRET not in hist.read_text(encoding="utf-8"))

        # Статус и удаление.
        await submit(pilot, "$$TOKEN")
        assert "is set (value hidden)" in last_info(app).text_content
        await submit(pilot, "$$TOKEN-")
        assert "removed" in last_info(app).text_content
        assert "TOKEN" not in app.local_env
        await submit(pilot, "$$TOKEN")
        assert "is not set" in last_info(app).text_content


async def test_secret_value_masked_in_journal(isolated_home):
    """В шапке и в показываемом выводе значение маскируется, raw остаётся целым."""
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, f"$$TOKEN={SECRET}")
        await submit(pilot, "echo prefix-$TOKEN suffix")
        block = await wait_command_done(app, timeout=8.0)
        assert SECRET not in (block.header or "")
        assert "****" in (block.header or "")
        display = block._format_output()
        assert SECRET not in display
        assert "****" in display
        # Для пайпов/копирования raw_stdout настоящий.
        assert SECRET in (block.raw_stdout or "")


async def test_secret_input_line_is_masked(isolated_home):
    """Пока набирается значение (`$$NAME=X`), поле ввода маскируется."""
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        inp = input_widget(app)
        inp.value = f"$$TOKEN={SECRET}"
        inp.cursor_position = len(inp.value)
        await pilot.pause()
        assert inp.password is True
        # Без значения (только имя) и в обычной строке маски нет.
        inp.value = "$$TOKEN="
        await pilot.pause()
        assert inp.password is False
        inp.value = "echo hi"
        await pilot.pause()
        assert inp.password is False


async def test_secrets_reload_on_start(isolated_home):
    """`secrets_<instance>.json` подхватывается при старте как `$NAME`."""
    (isolated_home / "secrets_default.json").write_text(
        '{"API_KEY": "k-123"}', encoding="utf-8"
    )
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert app.local_env.get("API_KEY") == "k-123"
        assert "API_KEY" in app._secret_names


async def test_secrets_file_removed_on_exit(isolated_home):
    """Файл секретов удаляется при выходе из приложения (сессия не хранит их)."""
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, f"$$TOKEN={SECRET}")
        path = app.FILE_SECRETS
        assert os.path.isfile(path)
    assert not os.path.exists(path)
    assert not os.path.exists(path + ".tmp")


async def test_secrets_never_sent_to_llm(isolated_home, monkeypatch):
    """Значение секрета не уходит в LLM даже через $OUT."""
    import app as app_module

    (isolated_home / "llm_providers.yml").write_text(
        "default: ds\nproviders:\n  ds:\n    url: http://x\n    model: m\n",
        encoding="utf-8",
    )
    seen: list[str] = []

    def fake(provider, message, env, timeout=60, **kwargs):
        seen.append(message)
        return "ok"

    monkeypatch.setattr(app_module, "perform_request", fake)
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, f"$$TOKEN={SECRET}")
        await submit(pilot, "echo $TOKEN")
        await wait_command_done(app, timeout=8.0)
        await submit(pilot, ":llm ds explain this: $OUT")
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline and not seen:
            await pilot.pause()
    assert seen
    assert all(SECRET not in message for message in seen)
    assert any("****" in message for message in seen)


def _enable_clear_clip(isolated_home) -> None:
    """Дописать флаг очистки буфера в settings.yml (до создания app)."""
    path = isolated_home / "settings.yml"
    path.write_text(
        path.read_text(encoding="utf-8") + "\nclear_clipboard_after_secret: true\n",
        encoding="utf-8",
    )


async def test_secret_paste_clears_clipboard_when_enabled(isolated_home):
    """С флагом: вставка значения в `$$NAME=` очищает буфер обмена."""
    import pyperclip

    _enable_clear_clip(isolated_home)
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        assert app.clear_clipboard_after_secret is True
        inp = input_widget(app)
        inp.value = "$$TOKEN="
        inp.cursor_position = len(inp.value)
        await pilot.pause()
        pyperclip.copy(SECRET)
        await pilot.press("shift+insert")
        await pilot.pause()
        assert inp.value == f"$$TOKEN={SECRET}"
        assert pyperclip.paste() == ""


async def test_secret_paste_keeps_clipboard_by_default(isolated_home):
    """Без флага (по умолчанию) буфер не трогается; обычный текст — всегда."""
    import pyperclip

    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        assert app.clear_clipboard_after_secret is False
        inp = input_widget(app)
        inp.value = "$$TOKEN="
        inp.cursor_position = len(inp.value)
        pyperclip.copy(SECRET)
        await pilot.press("shift+insert")
        await pilot.pause()
        assert inp.value == f"$$TOKEN={SECRET}"
        assert pyperclip.paste() == SECRET


async def test_non_secret_paste_keeps_clipboard(isolated_home):
    """Даже с включённым флагом обычная вставка буфер не чистит."""
    import pyperclip

    _enable_clear_clip(isolated_home)
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        inp = input_widget(app)
        inp.value = "echo "
        inp.cursor_position = len(inp.value)
        pyperclip.copy("plain-text")
        await pilot.press("shift+insert")
        await pilot.pause()
        assert inp.value == "echo plain-text"
        assert pyperclip.paste() == "plain-text"


# --- Замороженная маскировка (инвариант: значение не появляется в журнале) ----


async def test_masking_survives_secret_removal(isolated_home):
    """После `$$NAME-` повторный рендер блока не показывает значение.

    Маскировка «на момент показа» брала текущий набор секретов, поэтому снятый
    (или переопределённый, или потерянный при `:session`) секрет проявлялся при
    любом перерендере: space/←→, F8, F2, поиск `:/`, `:w`.
    """
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, f"$$TOKEN={SECRET}")
        await submit(pilot, "echo $TOKEN")
        block = await wait_command_done(app, timeout=8.0)
        assert SECRET not in block._format_output()
        await submit(pilot, "$$TOKEN-")
        assert SECRET not in block._format_output()
        assert SECRET not in (block.text_content or "")
        # Перерендер сворачиванием — тот же путь, что space / ←→.
        block.collapsed = True
        assert SECRET not in block._format_output()
        block.collapsed = False
        assert SECRET not in block._format_output()


async def test_output_history_is_masked_after_secret_removal(isolated_home):
    """`:o` хранит уже замаскированный вывод, а не сырой."""
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, f"$$TOKEN={SECRET}")
        await submit(pilot, "echo $TOKEN")
        await wait_command_done(app, timeout=8.0)
        stored = app._output_history[-1]
        assert SECRET not in stored["stdout"]
        await submit(pilot, "$$TOKEN-")
        await submit(pilot, ":o")
        assert SECRET not in last_info(app).text_content


async def test_log_title_masks_secret(isolated_home):
    """Шапка `:log` — тоже показ: значение из команды маскируется."""
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, f"$$TOKEN={SECRET}")
        await submit(pilot, f"echo {SECRET}")
        await wait_command_done(app, timeout=8.0)
        await submit(pilot, ":log")
        await pilot.pause()
        assert SECRET not in (app.screen.title or "")
        await pilot.press("escape")
        await pilot.pause()


async def test_watch_body_masks_secret(isolated_home):
    """Блок `:watch` прячет значение и в заголовке, и в теле."""
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, f"$$TOKEN={SECRET}")
        await submit(pilot, ":watch 5 echo $TOKEN")
        await pilot.pause()
        state = app._watch_state
        assert state is not None, "watch не запустился"
        block = state["block"]
        assert SECRET not in (block.text_content or "")
        assert "****" in (block.text_content or "")
        await submit(pilot, ":watch stop")
        await pilot.pause()


async def test_env_reload_does_not_overwrite_secret(isolated_home):
    """`.bashrc_term` не подменяет значение секрета (иначе маска разъедется)."""
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, f"$$TOKEN={SECRET}")
        Path(app.FILE_BASHRC).write_text("TOKEN=from-bashrc\n", encoding="utf-8")
        await submit(pilot, ":env")
        await pilot.pause()
        assert app.local_env["TOKEN"] == SECRET


async def test_exit_keeps_other_session_secrets_file(isolated_home):
    """Выход удаляет только своё хранилище — соседнюю сессию не трогает."""
    other = isolated_home / "secrets_s2.json"
    other.write_text('{"K": "v"}', encoding="utf-8")
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, f"$$TOKEN={SECRET}")
        own = app.FILE_SECRETS
        assert os.path.isfile(own)
    assert not os.path.exists(own)
    assert other.is_file()


async def test_cmd_does_not_copy_secret_when_clipboard_flag_on(isolated_home):
    """С `clear_clipboard_after_secret` `:cmd` не кладёт значение в буфер."""
    import pyperclip

    _enable_clear_clip(isolated_home)
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, f"$$TOKEN={SECRET}")
        await submit(pilot, "echo $TOKEN")
        await wait_command_done(app, timeout=8.0)
        pyperclip.copy("sentinel")
        await submit(pilot, ":cmd")
        info = last_info(app).text_content
        assert "Not copied" in info
        assert SECRET not in info
        assert pyperclip.paste() == "sentinel"


async def test_llm_app_context_masks_secrets(isolated_home, monkeypatch):
    """Контекст библиотеки (`:llm ask`) тоже уходит замаскированным."""
    import app as app_module

    (isolated_home / "llm_providers.yml").write_text(
        "default: ds\nproviders:\n  ds:\n    url: http://x\n    model: m\n",
        encoding="utf-8",
    )
    seen: dict = {}

    def fake(provider, message, env, timeout=60, **kwargs):
        seen.update(kwargs)
        seen["message"] = message
        return "ok"

    monkeypatch.setattr(app_module, "perform_request", fake)
    app = CommandRunner()
    async with app.run_test(size=(140, 40)) as pilot:
        # Тег хранит ЛИТЕРАЛЬНОЕ значение — раньше оно уезжало в контексте.
        await submit(pilot, f"#api curl -H 'Bearer {SECRET}' https://api")
        await submit(pilot, f"$$TOKEN={SECRET}")
        await submit(pilot, ":llm ask explain the library")
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline and not seen:
            await pilot.pause()
    assert seen
    assert SECRET not in seen["message"]
    context = seen.get("app_context") or ""
    assert context
    assert SECRET not in context
