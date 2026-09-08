"""Остановка фоновой команды: F4 / :kill / :kill all.

Фича: долгая команда (@ cmd без timeout) исполняется в потоке с Popen;
F4 или :kill шлют SIGTERM группе процесса — блок помечается как остановленный,
а не ждёт command_timeout.
"""
import asyncio
import time

import pytest

pytestmark = pytest.mark.slow

from app import CommandBlock, CommandRunner
from tests.conftest import last_info, submit, wait_command_done


async def _last_running_block(app: CommandRunner, timeout: float = 6.0) -> CommandBlock:
    """Ждёт появления блока в состоянии «выполняется» (pending)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        running = [
            b for b in app.query(CommandBlock)
            if getattr(b, "pending", False)
        ]
        if running:
            return running[-1]
        await asyncio.sleep(0.05)
    raise AssertionError("Timed out waiting for a running CommandBlock")


async def test_f4_stops_running_command(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "@ sleep 30")
        block = await _last_running_block(app)
        await pilot.press("f4")
        await pilot.pause()
        done = await wait_command_done(app, timeout=8.0)
        assert done is block
        assert "stopped by user" in done.raw_stderr.lower()
        assert done.return_code == 143  # 128 + SIGTERM


async def test_colon_kill_stops_last_running(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "@ sleep 30")
        block = await _last_running_block(app)
        await submit(pilot, ":kill")
        done = await wait_command_done(app, timeout=8.0)
        assert done is block
        assert "stopped by user" in done.raw_stderr.lower()


async def test_kill_all_stops_everything(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "@ sleep 30")
        await _last_running_block(app)
        await submit(pilot, "@ sleep 40")
        second = await _last_running_block(app)
        await submit(pilot, ":kill all")
        await wait_command_done(app, timeout=8.0)
        assert "stopped by user" in second.raw_stderr.lower()
        # Оба блока остановлены, registry пуст — ничего не висит.
        assert app._running_command_blocks() == []


async def test_kill_without_running_reports_message(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "echo quick")
        await wait_command_done(app, timeout=8.0)
        await pilot.press("f4")
        await pilot.pause()
        text = last_info(app).text_content
        assert "No running commands to stop" in text
        await submit(pilot, ":kill")
        assert "No running commands to stop" in last_info(app).text_content


async def test_finished_command_returns_clean_output(isolated_home):
    """Регрессия: Popen-путь не меняет обычный вывод и код возврата."""
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "echo hello-stop")
        block = await wait_command_done(app, timeout=8.0)
        assert block.raw_stdout == "hello-stop"
        assert block.return_code == 0
        assert not block.raw_stderr
        assert not getattr(block, "_stop_requested", False)
