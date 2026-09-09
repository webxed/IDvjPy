"""Word-wise editing во вводе: Ctrl+W/F, алиасы Ctrl+Backspace/Delete, Ctrl+←/→."""
import pytest

pytestmark = pytest.mark.slow

from app import CommandInput, CommandRunner
from tests.conftest import input_widget

TEXT = "kubectl get pods hello"


async def _focused_input(app: CommandRunner, pilot, value: str, pos: int) -> CommandInput:
    inp = input_widget(app)
    inp.focus()
    inp.value = value
    inp.cursor_position = pos
    await pilot.pause()
    return inp


async def test_ctrl_backspace_deletes_word_left(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        inp = await _focused_input(app, pilot, TEXT, len(TEXT))
        await pilot.press("ctrl+backspace")
        assert inp.value == "kubectl get pods "
        assert inp.cursor_position == len("kubectl get pods ")


async def test_ctrl_delete_deletes_word_right(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        text = "kubectl get pods hello world"
        inp = await _focused_input(app, pilot, text, len("kubectl get pods "))
        await pilot.press("ctrl+delete")
        assert inp.value == "kubectl get pods world"
        assert inp.cursor_position == len("kubectl get pods ")


async def test_canonical_word_keys_and_navigation(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        # Ctrl+W — каноническое удаление слова слева (встроено в Input)
        inp = await _focused_input(app, pilot, TEXT, len(TEXT))
        await pilot.press("ctrl+w")
        assert inp.value == "kubectl get pods "

        # Ctrl+←/→ — навигация по словам
        inp = await _focused_input(app, pilot, "kubectl get pods", len("kubectl get pods"))
        await pilot.press("ctrl+left")
        assert inp.cursor_position == len("kubectl get ")
        inp.cursor_position = 0
        await pilot.pause()
        await pilot.press("ctrl+right")
        # Textual прыгает к началу следующего слова (пропуская пробел после
        # 'kubectl' — это позиция 8: 'kubectl ' = 8 символов)
        assert inp.cursor_position == 8
