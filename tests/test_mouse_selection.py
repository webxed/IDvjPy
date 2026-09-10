"""Выделение мышью в журнале: автокопирование в буфер и Ctrl+C.

Эмуляция протяжки — через внутренний pilot._post_mouse_events (MouseDown →
MouseMove → MouseUp): публичный Pilot умеет только click.
"""
import pyperclip
import pytest
from textual import events

pytestmark = pytest.mark.slow

from app import CommandBlock, CommandRunner
from tests.conftest import submit, wait_command_done


async def _drag_select(pilot, widget, start: tuple[int, int] = (0, 0), end: tuple[int, int] = (15, 0)) -> None:
    await pilot._post_mouse_events([events.MouseDown], widget, offset=start)
    await pilot._post_mouse_events([events.MouseMove], widget, offset=end)
    await pilot._post_mouse_events([events.MouseUp], widget, offset=end)
    await pilot.pause()


async def _output_block(pilot) -> CommandBlock:
    await submit(pilot, "echo 'hello-mouse-selection-0123456789'")
    block = await wait_command_done(pilot.app)
    await pilot.pause()
    return block


async def test_drag_selection_copies_to_clipboard(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        block = await _output_block(pilot)
        pyperclip.copy("sentinel")
        await _drag_select(pilot, block)
        selected = app.screen.get_selected_text()
        assert selected and selected.strip()
        assert pyperclip.paste() == selected
        assert app.clipboard == selected
        assert app.sub_title.startswith("Copied selection")


async def test_ctrl_c_copies_selection_not_block(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        block = await _output_block(pilot)
        await _drag_select(pilot, block)
        selected = app.screen.get_selected_text()
        assert selected

        pyperclip.copy("sentinel")
        await pilot.press("ctrl+c")
        await pilot.pause()
        assert pyperclip.paste() == selected  # выделение, а не весь блок


async def test_plain_click_keeps_clipboard(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        block = await _output_block(pilot)
        pyperclip.copy("sentinel")
        await pilot.click(block, offset=(2, 0))  # без протяжки — выделения нет
        await pilot.pause()
        assert pyperclip.paste() == "sentinel"
