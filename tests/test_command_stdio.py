"""stdin и таймаут у фоновых команд: приложение не отдаёт чужому ввод.

Симптом, из-за которого появился `stdin=DEVNULL`: `:kctx <cluster>` запускал
`tsh kube login`, тот повис на интерактиве и после таймаута приложение
«перестало отвечать» — клавиши и мышь уходили унаследовавшему терминал процессу
(поэтому не закрывалась даже заставка). Здесь проверяется, что фоновая команда
получает пустой stdin, а по таймауту группа добивается и подчищается.
"""
from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.slow

from app import CommandRunner
from tests.conftest import submit, wait_command_done


async def test_background_command_has_no_terminal_stdin(isolated_home):
    """`read` видит EOF (rc=1), а не клавиатуру TUI — команда не висит."""
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, 'read line; echo "rc=$? line=[$line]"')
        block = await wait_command_done(app, timeout=10)
        assert "rc=1 line=[]" in block.raw_stdout


async def test_pipe_input_still_reaches_the_command(isolated_home):
    """Пайп (`| cmd`) по-прежнему передаёт данные в stdin — DEVNULL только вместо TTY."""
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "echo pipe-payload")
        await wait_command_done(app, timeout=10)
        await submit(pilot, "| tr a-z A-Z")
        piped = await wait_command_done(app, timeout=10)
        assert piped.raw_stdout.strip() == "PIPE-PAYLOAD"


async def test_timeout_kills_group_and_hints_at_at_and_gt(isolated_home):
    """Таймаут: группа убита (процесса нет), вывод и подсказка `@ cmd` / `> cmd`."""
    app = CommandRunner()
    pid_file = isolated_home / "sleeper.pid"
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, f"sh -c 'echo $$ > {pid_file}; sleep 30'")
        block = await wait_command_done(app, timeout=25)
        assert block.return_code == 124
        stderr = block.raw_stderr
        assert "timed out" in stderr.lower()
        assert "`@ cmd`" in stderr and "`> cmd`" in stderr
        # Группа добита и дождана: процесса с этим pid больше нет.
        pid = int(pid_file.read_text(encoding="utf-8").strip())
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)
