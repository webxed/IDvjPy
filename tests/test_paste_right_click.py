"""Правый клик — вставка из буфера, независимо от того, где фокус.

Мышь здесь ускорение (клавиатурный путь Ctrl+V / Shift+Insert не меняется):
правый клик по журналу или по списку подсказок кладёт текст буфера в строку
ввода, хотя курсора в ней нет. Ссылки (`--seed`, `.md`, `:команды`) от правого
клика не срабатывают — иначе он затирал бы только что вставленный текст.
"""
from __future__ import annotations

import json

import pyperclip

from app import CommandRunner, InfoBlock
from tests.conftest import (
    input_widget,
    right_click,
    submit,
    wait_command_done,
    wait_json_viewer,
)


async def test_right_click_pastes_without_focus_in_input(isolated_home):
    """Курсор в журнале (фокус не в строке) — правый клик вставляет буфер."""
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "echo right-click")
        block = await wait_command_done(app, timeout=8.0)
        await pilot.press("tab")  # фокус уходит в журнал
        assert not input_widget(app).has_focus
        pyperclip.copy("pasted-by-mouse")

        assert await right_click(pilot, widget=block, offset=(6, 0))
        assert input_widget(app).value == "pasted-by-mouse"
        # Ничего не выполнилось: новых блоков нет (паст только вставился).
        assert len(list(app.query("CommandBlock"))) == 1


async def test_right_click_inserts_at_cursor(isolated_home):
    """Вставка идёт в позицию курсора строки, а не в конец."""
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "echo anchor")
        block = await wait_command_done(app, timeout=8.0)
        inp = input_widget(app)
        inp.value = "echo  end"
        inp.cursor_position = 5
        pyperclip.copy("middle")

        assert await right_click(pilot, widget=block, offset=(6, 0))
        assert inp.value == "echo middle end"


async def test_right_click_does_not_run_links(isolated_home):
    """Правый клик по ссылке не выполняет её (клик по `--seed` в каталоге seed)."""
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        pyperclip.copy("plain-paste")
        # В пустой БД журнал занят каталогом seed — там ссылки `--seed`.
        assert await right_click(pilot, offset=(20, 12))
        assert input_widget(app).value == "plain-paste"


async def test_right_click_does_not_pick_completion_row(isolated_home):
    """Правый клик по подсказке не выбирает пункт (это левый клик) — только вставка."""
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        (isolated_home / "alpha.txt").write_text("x\n", encoding="utf-8")
        inp = input_widget(app)
        inp.value = "ls ./alp"
        inp.cursor_position = len(inp.value)
        await pilot.pause()
        await pilot.pause()
        clist = app._completion_list
        assert clist.is_visible()
        pyperclip.copy("clip-text")

        await right_click(pilot, widget=clist, offset=(3, 2))
        # Пункт не выбран: в строке только набранное плюс буфер (а не `./alpha.txt`).
        value = input_widget(app).value
        assert value == "ls ./alpclip-text"
        assert "./alpha.txt" not in value


async def test_right_click_pastes_inside_block_without_focus_flip(isolated_home):
    """Клик по блоку правой кнопкой: буфер вставлен, блок не перехватывает фокус."""
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "echo block-click")
        block = await wait_command_done(app, timeout=8.0)
        pyperclip.copy("into-input")

        await right_click(pilot, widget=block, offset=(2, 0))
        assert input_widget(app).value == "into-input"
        assert input_widget(app).has_focus  # строка ввода остаётся рабочей


async def test_right_click_with_empty_clipboard_reports_it(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "echo empty-clip")
        block = await wait_command_done(app, timeout=8.0)
        pyperclip.copy("")

        assert await right_click(pilot, widget=block, offset=(6, 0))
        assert "Clipboard is empty" in app.sub_title
        assert input_widget(app).value == ""


async def test_right_click_clears_clipboard_after_secret_paste(isolated_home):
    """`clear_clipboard_after_secret` действует и на вставку правым кликом."""
    settings = isolated_home / "settings.yml"
    settings.write_text(
        settings.read_text(encoding="utf-8") + "\nclear_clipboard_after_secret: true\n",
        encoding="utf-8",
    )
    secret = "s3cr3t-value"
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        assert app.clear_clipboard_after_secret is True
        await submit(pilot, "echo secret-clip")
        block = await wait_command_done(app, timeout=8.0)
        # Незавершённый ввод секрета: строку не отправляем (стрелка/Enter стёрли бы её).
        inp = input_widget(app)
        inp.value = "$$TOKEN="
        inp.cursor_position = len(inp.value)
        await pilot.pause()
        pyperclip.copy(secret)

        await right_click(pilot, widget=block, offset=(6, 0))
        assert input_widget(app).value == "$$TOKEN=" + secret
        assert pyperclip.paste() == ""
        assert "Clipboard cleared (secret pasted)" in app.sub_title


async def test_right_click_does_not_touch_modal_screen(isolated_home):
    """Модалка (JSON viewer) сама ест мышь: правый клик по ней буфер не вставляет."""
    (isolated_home / "sample.json").write_text(
        json.dumps({"a": 1}, indent=2), encoding="utf-8"
    )
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "cat sample.json")
        await wait_command_done(app, timeout=8.0)
        await pilot.press("tab")
        await pilot.pause()
        await pilot.press("f5")
        viewer = await wait_json_viewer(app)
        assert getattr(app.screen, "_modal", False)
        pyperclip.copy("modal-paste")

        await right_click(pilot, widget=viewer, offset=(5, 3))
        assert input_widget(app).value == ""
        assert "modal-paste" not in "\n".join(
            block.text_content for block in app.query(InfoBlock)
        )
