"""Две ленты истории: сессия (↑) — всё набранное, файл — только разрешённое.

Концепция: перелистывание по ↑ во время сессии показывает **всё**, что человек
вводил (`:команды`, `?теги`, `!ссылки`, `#теги`, `$VAR=…`), а в
`history_<instance>.txt` попадает только то, что разрешает фильтр
(`history_queries`, сохранения `#tag`, подстановки — мимо).
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.slow

from app import CommandRunner
from tests.conftest import input_widget, submit, wait_command_done


def _file_history(app: CommandRunner) -> list[str]:
    return app._read_file_history()


async def test_session_walk_keeps_every_kind_of_line(isolated_home):
    """↑ помнит и `:`-команды, и `?`, `!`, `#`, `$VAR=` — файл всё это не берёт."""
    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        await submit(pilot, ":stats")
        await submit(pilot, "?demo")
        await submit(pilot, "$NS=team-a")
        await submit(pilot, "#saved echo saved-line")
        await submit(pilot, "!1")
        await submit(pilot, "echo plain-line")
        await wait_command_done(app, timeout=10)

        walk = app.session_history
        for line in (":stats", "?demo", "$NS=team-a", "#saved echo saved-line", "!1", "echo plain-line"):
            assert line in walk, f"{line!r} отсутствует в ленте сессии: {walk}"

        history = _file_history(app)
        assert "echo plain-line" in history
        for line in (":stats", "?demo", "$NS=team-a", "#saved echo saved-line", "!1"):
            assert line not in history, f"{line!r} не должен попадать в файл истории"


async def test_up_arrow_returns_colon_command(isolated_home):
    """Проверка «как у человека»: `:stats`, затем ↑ — строка вернулась во ввод."""
    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        await submit(pilot, "echo filler")
        await wait_command_done(app, timeout=10)
        await submit(pilot, ":stats")
        await pilot.pause()

        await pilot.press("escape")
        input_widget(app).value = ""
        input_widget(app).cursor_position = 0
        await pilot.press("up")
        await pilot.pause()
        assert input_widget(app).value == ":stats"


async def test_secrets_never_enter_the_session_walk(isolated_home):
    """`$$…` не попадает ни в ленту (иначе значение всплывёт по ↑), ни в файл."""
    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        await submit(pilot, "$$MY_TOKEN=hvs.secret-value")
        await pilot.pause()
        assert not any("MY_TOKEN" in line for line in app.session_history)
        assert not any("MY_TOKEN" in line for line in _file_history(app))


async def test_walk_dedupes_repeated_lines(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        await submit(pilot, ":stats")
        await submit(pilot, ":stats")
        await pilot.pause()
        assert app.session_history.count(":stats") == 1


async def test_walk_lines_are_not_suggested_for_plain_command(isolated_home):
    """Лента — для ↑, а подсказки по `:`-строкам даёт своя таблица (без дублей)."""
    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        await submit(pilot, ":stats")
        await pilot.pause()
        assert ":stats" in app.session_history
        assert ":stats" not in app.get_completion_candidates(":st")
        # Обычные команды из ленты по-прежнему подсказываются.
        app.session_history.append("echo session-hint")
        assert "echo session-hint" in app.get_completion_candidates("echo sess")
