"""`:diff` — сравнение stdout двух блоков (фича diff)."""
import pytest

pytestmark = pytest.mark.slow

from app import CommandRunner
from tests.conftest import last_info, submit, wait_command_done


async def test_diff_identical_outputs(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "printf 'a\\nb\\n'")
        await wait_command_done(app, timeout=8.0)
        await submit(pilot, "printf 'a\\nb\\n'")
        await wait_command_done(app, timeout=8.0)
        await submit(pilot, ":diff")
        assert "outputs are identical" in last_info(app).text_content


async def test_diff_shows_changes(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        await submit(pilot, "printf 'a\\nb\\nc\\n'")
        await wait_command_done(app, timeout=8.0)
        await submit(pilot, "printf 'a\\nB\\nc\\n'")
        await wait_command_done(app, timeout=8.0)
        await submit(pilot, ":diff")
        text = last_info(app).text_content
        assert "Diff:" in text
        assert "- b" in text
        assert "+ B" in text


async def test_diff_requires_two_blocks(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "echo only-one")
        await wait_command_done(app, timeout=8.0)
        await submit(pilot, ":diff")
        assert "need at least two command blocks" in last_info(app).text_content


async def test_diff_focused_block_against_previous(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        await submit(pilot, "printf 'keep\\n'")
        await wait_command_done(app, timeout=8.0)
        await submit(pilot, "printf 'keep\\nchanged\\n'")
        block = await wait_command_done(app, timeout=8.0)
        block.focus()
        await pilot.press("escape")
        await submit(pilot, ":diff")
        text = last_info(app).text_content
        assert "+ changed" in text
