"""Сессионная история вывода и поиск по ней: `:o` (фича output-history)."""
import pytest

pytestmark = pytest.mark.slow

from app import CommandRunner
from tests.conftest import last_info, submit, wait_command_done


async def test_out_lists_last_outputs(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        await submit(pilot, "echo first-out")
        await wait_command_done(app, timeout=8.0)
        await submit(pilot, "echo second-out")
        await wait_command_done(app, timeout=8.0)
        await submit(pilot, ":o")
        text = last_info(app).text_content
        assert "Last 2 command output(s)" in text
        assert "echo first-out" in text
        assert "echo second-out" in text
        assert "first-out" in text and "second-out" in text


async def test_out_search_finds_old_output_after_clear(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        await submit(pilot, "echo needle-payload")
        await wait_command_done(app, timeout=8.0)
        # :c убирает блоки журнала, но память выводов остаётся.
        await submit(pilot, ":c")
        await submit(pilot, ":o /needle-payload")
        text = last_info(app).text_content
        assert "Output search 'needle-payload'" in text
        assert "echo needle-payload" in text
        assert "needle-payload" in text


async def test_out_no_match_and_clear(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        await submit(pilot, "echo something")
        await wait_command_done(app, timeout=8.0)
        await submit(pilot, ":o /zzz-no-such")
        assert "no matches in output history" in last_info(app).text_content
        await submit(pilot, ":o clear")
        assert "Cleared session output history" in last_info(app).text_content
        await submit(pilot, ":o")
        assert "No command output stored this session" in last_info(app).text_content


async def test_out_keeps_stderr_and_exit_code(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        await submit(pilot, "echo err-msg >&2; exit 3")
        await wait_command_done(app, timeout=8.0)
        await submit(pilot, ":o 1")
        text = last_info(app).text_content
        assert "exit 3" in text
        assert "err-msg" in text
