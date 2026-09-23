"""`:term [--tab|--window] [path]` — режим терминала на сессию.

Режим (`window` / `tab`) задаёт `settings.yml: term_open` или `$IDVJPY_TERM_OPEN`,
а `:term --tab` / `:term --window` переключают его **на текущую сессию** (как
`:screensaver matrix|stars`) и сразу открывают терминал — им же пользуются
`:new` и `& cmd`. Проверяем без окон: `open_terminal` мокается.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.slow

from app import CommandRunner
from gui_open import GuiOpenError
from tests.conftest import last_info, submit


class _Proc:
    pid = 4311


def _patch_open(monkeypatch, *, error: str | None = None) -> list[dict]:
    """Подменить открытие терминала; вернуть список вызовов."""
    import app as app_module

    calls: list[dict] = []

    def fake(path_arg, environ, *, platform=None, mode="window"):
        calls.append({"path": path_arg, "env": dict(environ), "mode": mode})
        if error:
            raise GuiOpenError(error)
        return ["gnome-terminal", "--tab" if mode == "tab" else "--"], _Proc()

    monkeypatch.setattr(app_module, "open_terminal", fake)
    return calls


async def test_term_tab_switches_the_session_and_opens(isolated_home, monkeypatch):
    calls = _patch_open(monkeypatch)
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ":term --tab")
        await pilot.pause()
        assert app.term_open == "tab"
        assert calls and calls[0]["mode"] == "tab"
        assert calls[0]["path"] is None
        assert (isolated_home / "settings.yml").read_text(encoding="utf-8").count(
            "term_open"
        ) == 0  # settings.yml не трогаем: режим только на сессию


async def test_term_window_switches_back(isolated_home, monkeypatch):
    calls = _patch_open(monkeypatch)
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ":term --tab")
        await submit(pilot, ":term --window")
        await pilot.pause()
        assert app.term_open == "window"
        assert [call["mode"] for call in calls] == ["tab", "window"]


async def test_term_flag_with_a_path(isolated_home, monkeypatch):
    calls = _patch_open(monkeypatch)
    target = isolated_home / "work"
    target.mkdir()
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, f":term --tab {target}")
        await pilot.pause()
        assert calls[0]["mode"] == "tab"
        assert calls[0]["path"] == str(target)


async def test_term_unknown_flag_is_usage_and_changes_nothing(isolated_home, monkeypatch):
    """Опечатка (`--nope`) — явное Usage, режим не меняется, окно не открывается."""
    calls = _patch_open(monkeypatch)
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ":term --nope")
        await pilot.pause()
        assert not calls
        assert app.term_open == "window"
        assert "Usage: :term" in last_info(app).text_content


async def test_term_two_paths_is_usage(isolated_home, monkeypatch):
    calls = _patch_open(monkeypatch)
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ":term /tmp /var")
        await pilot.pause()
        assert not calls
        assert "Usage: :term" in last_info(app).text_content


async def test_term_tab_mode_is_shared_with_ampersand(isolated_home, monkeypatch):
    """Режим сессии виден и `& cmd` (одна настройка на все три места)."""
    import app as app_module

    opened = _patch_open(monkeypatch)
    windowed: list[dict] = []

    def fake_window(command, *, cwd, environ, platform=None, mode="window"):
        windowed.append({"command": list(command), "mode": mode})
        return ["gnome-terminal", "--tab"], _Proc()

    monkeypatch.setattr(app_module, "open_terminal_command", fake_window)
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ":term --tab")
        await submit(pilot, "& htop")
        await pilot.pause()
        assert opened[0]["mode"] == "tab"
        assert windowed[0]["mode"] == "tab"


async def test_term_open_error_keeps_the_switched_mode(isolated_home, monkeypatch):
    """Переключили, а терминал не нашёлся: ошибка явная, режим остаётся выбранным."""
    _patch_open(monkeypatch, error="no terminal with tab support found")
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ":term --tab")
        await pilot.pause()
        assert app.term_open == "tab"
        assert "tab support" in last_info(app).text_content
