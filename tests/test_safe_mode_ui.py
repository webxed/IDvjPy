"""Safe execution mode at the real launch boundaries (Pilot scenarios).

Confirmation is keyboard-driven, non-blocking, and must run the exact frozen
expansion; cancelling must never start a process or hang a runbook.
"""
from __future__ import annotations

import asyncio
import time

import pytest

pytestmark = pytest.mark.slow

import app as app_module
import database_v2 as database
from app import CommandBlock, CommandRunner, InfoBlock
from safe_mode_prompt import SafeModeScreen
from tests.conftest import last_info, submit

RISKY = "chmod 000 /tmp/idvjpy-safe-mode-nonexistent"


def _text(app: CommandRunner) -> str:
    return "\n".join(block.text_content for block in app.query(InfoBlock))


async def _wait_for_modal(app: CommandRunner, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while not isinstance(app.screen, SafeModeScreen) and time.monotonic() < deadline:
        await asyncio.sleep(0.05)
    assert isinstance(app.screen, SafeModeScreen), "safe-mode modal did not open"


async def test_safe_mode_is_off_by_default(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        assert app.safe_mode is False
        await submit(pilot, ":safe")
        assert "off" in last_info(app).text_content


async def test_safe_command_toggles_only_this_session(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":safe on")
        assert app.safe_mode is True
        assert "on" in last_info(app).text_content
        await submit(pilot, ":safe off")
        assert app.safe_mode is False
        await submit(pilot, ":safe")
        assert "off" in last_info(app).text_content


async def test_off_runs_risky_command_without_confirmation(isolated_home, monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        CommandRunner, "_execute_in_thread",
        lambda self, block, command, stdin_data, no_timeout=False, extra_env=None: calls.append(command),
    )
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, RISKY)
        assert not isinstance(app.screen, SafeModeScreen)
        assert calls == [RISKY]


async def test_cancel_blocks_execution(isolated_home, monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        CommandRunner, "_execute_in_thread",
        lambda self, block, command, stdin_data, no_timeout=False, extra_env=None: calls.append(command),
    )
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":safe on")
        await submit(pilot, RISKY)
        await _wait_for_modal(app)
        assert calls == []
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, SafeModeScreen)
        assert calls == []
        assert not app.query(CommandBlock)
        assert "cancel" in _text(app).lower()


async def test_confirm_runs_exact_frozen_command(isolated_home, monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        CommandRunner, "_execute_in_thread",
        lambda self, block, command, stdin_data, no_timeout=False, extra_env=None: calls.append(command),
    )
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":safe on")
        app.local_env["SAFE_T"] = "AAA"
        await submit(pilot, "chmod 000 /tmp/$SAFE_T")
        await _wait_for_modal(app)
        # Change the source after confirmation is requested: the frozen text must win.
        app.local_env["SAFE_T"] = "BBB"
        await pilot.press("enter")
        await pilot.pause()
        assert calls == ["chmod 000 /tmp/AAA"], calls


async def test_vault_launch_preserves_frozen_env_and_stdin(isolated_home, monkeypatch):
    seen: list[tuple[str, str | None, dict[str, str] | None]] = []
    monkeypatch.setattr(
        CommandRunner, "_execute_in_thread",
        lambda self, block, command, stdin_data, no_timeout=False, extra_env=None: seen.append(
            (command, stdin_data, dict(extra_env) if extra_env else None)
        ),
    )
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":safe on")
        app.run_command(
            RISKY,
            stdin_data="vault value\\n",
            extra_env={"VAULT_VALUE": "s3cr3t"},
        )
        await _wait_for_modal(app)
        assert seen == []
        await pilot.press("enter")
        await pilot.pause()
        assert seen == [(RISKY, "vault value\\n", {"VAULT_VALUE": "s3cr3t"})]


async def test_tty_launch_requires_confirmation(isolated_home, monkeypatch):
    seen: list[str] = []
    monkeypatch.setattr(CommandRunner, "_run_in_tty", lambda self, command: seen.append(command) or 0)
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":safe on")
        await submit(pilot, "> chmod 000 /tmp/tty-x")
        await _wait_for_modal(app)
        assert seen == []
        await pilot.press("enter")
        await pilot.pause()
        assert seen == ["chmod 000 /tmp/tty-x"]


async def test_window_launch_requires_confirmation(isolated_home, monkeypatch):
    opened: list[list[str]] = []

    class _Proc:
        pid = 4242

    def fake_open(argv, cwd=None, environ=None, mode="window"):
        opened.append(list(argv))
        return (["terminal", *argv], _Proc())

    monkeypatch.setattr(app_module, "open_terminal_command", fake_open)
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":safe on")
        await submit(pilot, "& chmod 000 /tmp/window-x")
        await _wait_for_modal(app)
        assert opened == []
        await pilot.press("enter")
        await pilot.pause()
        assert opened and opened[0][-1] == "chmod 000 /tmp/window-x"


async def test_watch_confirms_once_per_activation(isolated_home, monkeypatch):
    count = {"n": 0}

    def fake_confirm(owner, command, risks, callback, cancelled=None):
        count["n"] += 1
        callback()

    monkeypatch.setattr(app_module, "confirm_safe_mode", fake_confirm)
    monkeypatch.setattr(CommandRunner, "_watch_loop", lambda self: None)
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":safe on")
        await submit(pilot, ":watch 5 chmod 000 /tmp/watch-x")
        assert count["n"] == 1, "watch must confirm once, not per tick"
        assert app._watch_state is not None
        await submit(pilot, ":watch stop")


async def test_watch_cancel_does_not_start(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":safe on")
        await submit(pilot, ":watch 5 chmod 000 /tmp/watch-x")
        await _wait_for_modal(app)
        await pilot.press("escape")
        await pilot.pause()
        assert app._watch_state is None
        assert not app.query(CommandBlock)


async def test_runbook_cancel_does_not_hang(isolated_home):
    db = isolated_home / "test_history.db"
    database.init_db(str(db))
    database.add_command(str(db), "chmod 000 /tmp/runbook-x", "chain")
    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        await submit(pilot, ":safe on")
        await submit(pilot, ":run chain")
        await _wait_for_modal(app)
        await pilot.press("escape")
        deadline = time.monotonic() + 10.0
        while app._run_active and time.monotonic() < deadline:
            await asyncio.sleep(0.05)
        assert not app._run_active, "runbook hung after a cancelled safe step"
        assert not app.query(CommandBlock)
