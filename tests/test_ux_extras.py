"""UX-мелочи: :r N, индикатор running, :alias (фича ux-extras)."""
import asyncio

import pytest

pytestmark = pytest.mark.slow

from app import CommandRunner
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
        await submit(pilot, ":kill")
        await wait_command_done(app, timeout=8.0)
        await asyncio.sleep(0.2)
        assert app.title == app.TITLE


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
