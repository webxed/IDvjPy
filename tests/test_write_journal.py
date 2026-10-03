"""`:w` — запись журнала в файл: фон, дописывание/перезапись, маскирование.

Аудит C3: снимок журнала берётся в UI-потоке (только маскированный плоский
текст), а сериализация и запись идут в фоновом потоке; повторный `:w`
дописывает файл, `--overwrite` перезаписывает, ошибка возвращается в журнал.
"""
from __future__ import annotations

import asyncio
import threading
from pathlib import Path

from app import CommandRunner
from tests.conftest import last_info, submit, wait_command_done, wait_write

SECRET = "s3cr3t-token-value"


async def test_w_runs_in_background(isolated_home):
    target = isolated_home / "dump.txt"
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "echo hi")
        await wait_command_done(app)
        await submit(pilot, f":w {target}")
        assert app._write_worker_job is not None
        await wait_write(app)
        assert target.is_file()
        assert "written to" in last_info(app).text_content


async def test_w_appends_by_default_and_overwrites_with_flag(isolated_home):
    target = isolated_home / "dump.txt"
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "echo first-line")
        await wait_command_done(app)
        await submit(pilot, f":w {target}")
        await wait_write(app)
        first = target.read_text(encoding="utf-8")
        assert "first-line" in first

        await submit(pilot, "echo second-line")
        await wait_command_done(app)
        await submit(pilot, f":w {target}")  # повторный :w дописывает
        await wait_write(app)
        appended = target.read_text(encoding="utf-8")
        assert appended.startswith(first)
        assert "second-line" in appended

        await submit(pilot, f":w {target} --overwrite")
        await wait_write(app)
        overwritten = target.read_text(encoding="utf-8")
        assert overwritten != appended
        assert "second-line" in overwritten


async def test_w_failure_is_reported(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, f":w {isolated_home}")  # каталог, а не файл
        await wait_write(app)
        assert "Error writing to file" in last_info(app).text_content


async def test_w_without_args_shows_usage(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":w")
        assert "Usage: :w" in last_info(app).text_content


async def test_second_w_is_rejected_while_first_is_running(isolated_home, monkeypatch):
    """Два `:w` не могут конкурентно писать один и тот же журнал."""
    target = isolated_home / "dump.txt"
    app = CommandRunner()
    original = app._strip_formatting_tags
    entered = threading.Event()
    release = threading.Event()

    def slow_strip(value: str) -> str:
        entered.set()
        release.wait()
        return original(value)

    monkeypatch.setattr(app, "_strip_formatting_tags", slow_strip)
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "echo first")
        await wait_command_done(app)
        await submit(pilot, f":w {target}")
        assert await asyncio.to_thread(entered.wait, 1)
        try:
            await submit(pilot, f":w {target}")
            assert "already in progress" in last_info(app).text_content
        finally:
            release.set()
        await wait_write(app)


async def test_w_does_not_write_secret_value(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, f"$$TOKEN={SECRET}")
        await submit(pilot, "echo prefix-$TOKEN suffix")
        await wait_command_done(app, timeout=8.0)
        target = isolated_home / "dump.txt"
        await submit(pilot, f":w {target}")
        await wait_write(app)
        dumped = Path(target).read_text(encoding="utf-8")
        assert SECRET not in dumped
        assert "****" in dumped
