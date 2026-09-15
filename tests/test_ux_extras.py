"""UX-мелочи: :r N, индикатор running, :alias, консоль под TUI (Ctrl+O)."""
import asyncio
from contextlib import contextmanager
from typing import Any, cast

import pytest

pytestmark = pytest.mark.slow

from app import CommandRunner, InfoBlock
from tests.conftest import input_widget, last_info, submit, wait_command_done


async def test_replay_n_back(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "echo first")
        await wait_command_done(app, timeout=8.0)
        await submit(pilot, "echo second")
        await wait_command_done(app, timeout=8.0)
        await submit(pilot, "echo third")
        await wait_command_done(app, timeout=8.0)
        await submit(pilot, ":r 1")  # один назад от последнего → second
        assert input_widget(app).value == "echo second"
        await submit(pilot, ":r 0")  # последний → third
        assert input_widget(app).value == "echo third"


async def test_replay_too_far_and_none(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "echo only")
        await wait_command_done(app, timeout=8.0)
        await submit(pilot, ":r 5")
        assert "too far back" in last_info(app).text_content
        app2 = CommandRunner()
    async with app2.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":r")
        assert "No command block to replay" in last_info(app2).text_content


async def test_title_shows_running_count(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "@ sleep 30")
        # Ждём появления запущенного процесса.
        for _ in range(100):
            if app._proc_registry:
                break
            await asyncio.sleep(0.05)
        assert app._proc_registry
        await asyncio.sleep(0.2)
        assert "1 running" in app.title
        assert app.instance_name in app.title  # заголовок несёт имя сессии
        await submit(pilot, ":kill")
        await wait_command_done(app, timeout=8.0)
        await asyncio.sleep(0.2)
        assert "running" not in app.title
        assert app.title == app._base_title()


async def test_terminal_title_has_session_and_osc(isolated_home):
    """Заголовок окна/вкладки: OSC 0 с именем сессии (кроме headless)."""
    writes: list[str] = []

    class _Driver:
        is_headless = False

        def write(self, data: str) -> None:
            writes.append(data)

        def flush(self) -> None:
            writes.append("<flush>")

    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        real_driver = app._driver
        cast(Any, app)._driver = _Driver()
        try:
            app._refresh_running_title()
        finally:
            cast(Any, app)._driver = real_driver
    assert any(
        w.startswith("\x1b]0;") and "default" in w and w.endswith("\x07")
        for w in writes
    )


async def test_alias_exports_shell_functions(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "#mine echo hello")
        await submit(pilot, ":alias mine out.sh")
        assert "Exported 1 shell function(s) to out.sh" in last_info(app).text_content
        text = (isolated_home / "out.sh").read_text(encoding="utf-8")
        assert "mine_1() {" in text
        assert "echo hello" in text
        # Всю библиотеку тоже можно выгрузить.
        await submit(pilot, ":alias * lib.sh")
        lib = (isolated_home / "lib.sh").read_text(encoding="utf-8")
        assert "mine_1() {" in lib


async def test_alias_usage_and_unknown(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":alias")
        assert "Usage: :alias" in last_info(app).text_content
        await submit(pilot, ":alias ghost")
        assert "no live commands for 'ghost'" in last_info(app).text_content


async def test_ctrl_o_shows_console(isolated_home, monkeypatch):
    """Ctrl+O: TUI уходит в фон на время просмотра консоли, возврат — клавиша.

    Проверяем порядок: suspend → ожидание клавиши → возврат в TUI. Настоящий
    `suspend()` в headless-тесте невозможен, поэтому подменяем его.
    """
    events: list[str] = []

    @contextmanager
    def fake_suspend(_self):
        events.append("suspend")
        try:
            yield
        finally:
            events.append("resume")

    monkeypatch.setattr(CommandRunner, "suspend", fake_suspend)
    monkeypatch.setattr(
        CommandRunner, "_wait_console_key", lambda _self: events.append("wait")
    )

    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("ctrl+o")
        await pilot.pause()

    assert events == ["suspend", "wait", "resume"]
    assert not [b for b in app.query(InfoBlock) if "Console error" in b.text_content]


async def test_ctrl_o_reports_when_suspend_unsupported(isolated_home, monkeypatch):
    """Терминал без suspend — явная ошибка, а не молчание."""
    from textual.app import SuspendNotSupported

    @contextmanager
    def bad_suspend(_self):
        raise SuspendNotSupported()
        yield  # pragma: no cover — генератор-контекст обязан содержать yield

    monkeypatch.setattr(CommandRunner, "suspend", bad_suspend)

    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("ctrl+o")
        await pilot.pause()
        assert "cannot suspend" in last_info(app).text_content
