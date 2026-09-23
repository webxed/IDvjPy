"""`& cmd` — команда в отдельном окне терминала.

Терминал остаётся у приложения: `> cmd` отдаёт TUI чужому процессу, а `&`
открывает **новое окно** и возвращает приложение сразу. Проверяем без окон —
`open_terminal_command` мокается: argv/cwd/env, маскировка и отказ от подстановки
значений `$$`-секретов (иначе они уехали бы в argv нового окна), запись в историю,
явная ошибка без терминала и то, что синтаксис shell (`&&`, `&>`) не перехватывается.
"""
from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.slow

from app import CommandRunner
from gui_open import GuiOpenError
from tests.conftest import last_info, submit


class _Proc:
    pid = 4242


def _patch_open(monkeypatch, *, error: str | None = None) -> list[dict]:
    """Подменить открытие окна; вернуть список вызовов (``error`` — бросок)."""
    import app as app_module

    calls: list[dict] = []

    def fake(command, *, cwd, environ, platform=None, mode="window"):
        calls.append({"command": list(command), "cwd": cwd, "env": dict(environ), "mode": mode})
        if error:
            raise GuiOpenError(error)
        return ["xterm", "-e", *command], _Proc()

    monkeypatch.setattr(app_module, "open_terminal_command", fake)
    return calls


async def test_window_command_runs_in_a_new_terminal(isolated_home, monkeypatch):
    """`& sleep 30` — новое окно с `bash -c`, cwd приложения, приложение свободно."""
    calls = _patch_open(monkeypatch)
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "& sleep 30")
        await pilot.pause()
        assert calls
        assert calls[0]["command"] == ["/bin/bash", "-c", "sleep 30"]
        assert calls[0]["cwd"] == os.getcwd()
        text = last_info(app).text_content
        assert "Window: sleep 30" in text
        assert "pid 4242" in text


async def test_window_command_expands_vars_but_keeps_secrets(isolated_home, monkeypatch):
    """`$VAR` раскрывается, значение `$$`-секрета в текст окна не попадает."""
    calls = _patch_open(monkeypatch)
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "$$TOKEN=supersecret")
        await submit(pilot, "$HOST=example.com")
        await submit(pilot, "& ssh $HOST -o TokenAuthentication=$TOKEN")
        await pilot.pause()
        command = " ".join(calls[0]["command"])
        assert "$HOST" not in command and "example.com" in command
        # Имя осталось, значение — нет: его раскроет shell окна из env.
        assert "$TOKEN" in command
        assert "supersecret" not in command
        assert "supersecret" not in last_info(app).text_content
        # Значение секрета доступно новому окну — через env, не через argv.
        assert calls[0]["env"].get("TOKEN") == "supersecret"


async def test_window_command_without_arguments_shows_usage(isolated_home, monkeypatch):
    calls = _patch_open(monkeypatch)
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "&")
        await pilot.pause()
        assert not calls
        assert "Usage: & <command>" in last_info(app).text_content


async def test_window_command_reports_a_missing_terminal(isolated_home, monkeypatch):
    """Нет `$TERMINAL` и системных терминалов — явная ошибка, а не молчание."""
    _patch_open(monkeypatch, error="set $TERMINAL= (e.g. kitty)")
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "& htop")
        await pilot.pause()
        assert "$TERMINAL" in last_info(app).text_content


async def test_window_command_records_history(isolated_home, monkeypatch):
    """Строка с `&` — обычная запись истории (↑ и файл), как `>` и `@`."""
    _patch_open(monkeypatch)
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "& echo window-history")
        await pilot.pause()
        assert "& echo window-history" in app.session_history
        history = (isolated_home / app.FILE_HISTORY).read_text(encoding="utf-8")
        assert "& echo window-history" in history


async def test_shell_syntax_is_not_a_window_command(isolated_home, monkeypatch):
    """`&&` и `&>` — синтаксис shell: в окно не уезжают, выполняется как обычно."""
    calls = _patch_open(monkeypatch)
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "&> out.txt")
        await pilot.pause()
        assert not calls
        assert (isolated_home / "out.txt").exists()
        await submit(pilot, "true && echo and-ok")
        await pilot.pause()
        assert not calls


async def test_window_command_honours_term_open(isolated_home, monkeypatch):
    """`term_open: tab` — окно просят вкладкой (механика `:term`, см. `src/gui_open.py`)."""
    settings = isolated_home / "settings.yml"
    settings.write_text(
        settings.read_text(encoding="utf-8") + "term_open: tab\n", encoding="utf-8"
    )
    calls = _patch_open(monkeypatch)
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        assert app.term_open == "tab"
        await submit(pilot, "& htop")
        await pilot.pause()
        assert calls[0]["mode"] == "tab"


async def test_term_open_env_override(isolated_home, monkeypatch):
    """Быстрый переключатель `$IDVJPY_TERM_OPEN=tab` — без правки settings.yml."""
    monkeypatch.setenv("IDVJPY_TERM_OPEN", "tab")
    app = CommandRunner()
    async with app.run_test(size=(120, 40)):
        assert app.term_open == "tab"


async def test_window_command_defaults_to_a_new_window(isolated_home, monkeypatch):
    calls = _patch_open(monkeypatch)
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        assert app.term_open == "window"
        await submit(pilot, "& htop")
        await pilot.pause()
        assert calls[0]["mode"] == "window"
