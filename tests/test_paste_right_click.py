"""Правый клик — вставка из буфера, независимо от того, где фокус.

Мышь здесь ускорение (клавиатурный путь Ctrl+V / Shift+Insert не меняется):
правый клик по журналу или по списку подсказок кладёт текст буфера в строку
ввода, хотя курсора в ней нет. Ссылки (`--seed`, `.md`, `:команды`) от правого
клика не срабатывают — иначе он затирал бы только что вставленный текст.

Сам правый клик выделения не заводит и не снимает: выделенное мышью уже лежит
в буфере, и правый клик только вставляет его. Иначе в буфер попадал случайный
кусок под курсором (в приглашении — `~ ❯`), затирая выделенный человеком текст.
"""
from __future__ import annotations

import json

import pyperclip
from textual import events

from app import CommandRunner, InfoBlock
from tests.conftest import (
    input_widget,
    right_click,
    submit,
    wait_command_done,
    wait_json_viewer,
)


async def _drag(pilot, widget, start, end) -> None:
    """Протяжка мышью: MouseDown → MouseMove → MouseUp (у Pilot нет drag)."""
    await pilot._post_mouse_events([events.MouseDown], widget, offset=start)
    await pilot._post_mouse_events([events.MouseMove], widget, offset=end)
    await pilot._post_mouse_events([events.MouseUp], widget, offset=end)
    await pilot.pause()
    await pilot.pause()


async def _right_drag(pilot, widget, start, end) -> None:
    """Правый клик с дрогнувшей мышью — самый опасный случай."""
    await right_click(pilot, widget=widget, offset=start)
    await pilot._post_mouse_events([events.MouseMove], widget, offset=end)
    await right_click(pilot, widget=widget, offset=end)
    await pilot.pause()


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


async def test_right_click_on_block_does_not_steal_focus(isolated_home):
    """Правый клик не переводит фокус на блок: без этого вставка как бы тормозит.

    Textual сам фокусирует виджет под мышью (Screen MouseDown), и правый клик по
    журналу уводил фокус на блок, а вставка возвращала его в строку — два
    перефокуса на каждое нажатие.
    """
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "echo focus-keep")
        block = await wait_command_done(app, timeout=8.0)
        inp = input_widget(app)
        inp.value = ""
        inp.focus()
        await pilot.pause()
        pyperclip.copy("focused-paste")

        await right_click(pilot, widget=block, offset=(6, 0))
        await pilot.pause()
        assert inp.has_focus
        assert inp.value == "focused-paste"


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


async def test_right_click_pastes_selection_and_keeps_it(isolated_home):
    """Выделил мышью → сразу в буфере; правый клик вставляет и буфер не трогает.

    Сама вставка снимает подсветку (строка ввода получает фокус, а
    `Input._watch_selection` в Textual чистит выделение экрана) — но текст
    остаётся в буфере, это и есть то, что нужно человеку.
    """
    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        await submit(pilot, "echo selection-for-right-click")
        block = await wait_command_done(app, timeout=8.0)
        pyperclip.copy("sentinel")

        await _drag(pilot, block, (2, 0), (18, 0))
        selected = app.screen.get_selected_text()
        assert selected and selected.strip()
        assert pyperclip.paste() == selected  # выделение уже скопировано

        await right_click(pilot, widget=block, offset=(6, 0))
        await pilot.pause()
        assert input_widget(app).value == selected  # вставлено в строку
        assert pyperclip.paste() == selected  # буфер не перезаписан


async def test_right_click_on_block_keeps_clipboard_when_it_is_empty(isolated_home):
    """Пустой буфер: правый клик не снимает выделение и ничего не ломает."""
    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        await submit(pilot, "echo keep-selection")
        block = await wait_command_done(app, timeout=8.0)
        await _drag(pilot, block, (2, 0), (12, 0))
        selected = app.screen.get_selected_text()
        assert selected and selected.strip()
        app.copy_text("")  # чистим все слои буфера: pyperclip, xclip/xsel, внутренний

        await right_click(pilot, widget=block, offset=(6, 0))
        await pilot.pause()
        assert input_widget(app).value == ""
        assert "Clipboard is empty" in app.sub_title
        assert app.screen.get_selected_text() == selected  # выделение не тронуто


async def test_right_click_never_pastes_prompt_junk(isolated_home):
    """Дрогнувший правый клик не заводит выделение: чужое в буфере остаётся.

    Регрессия: Textual заводил выделение на любую кнопку MouseDown, и на
    отпускании приложение копировало случайный кусок под курсором — в пустой
    строке ввода это было приглашение `~ ❯`, и оно затирало буфер.
    """
    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        row = app.query_one("#input-row")
        pyperclip.copy("user-data")

        for offset in ((3, 1), (30, 1), (60, 1)):
            await _right_drag(pilot, row, offset, (offset[0] + 2, offset[1]))
            assert pyperclip.paste() == "user-data", offset
            assert app.screen.get_selected_text() is None, offset


async def test_right_click_pastes_selection_after_prompt_clicks(isolated_home):
    """Полный сценарий: выделил в выводе → правый клик в пустой строке → вставилось."""
    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        await submit(pilot, "echo scenario-text-for-paste")
        block = await wait_command_done(app, timeout=8.0)
        await _drag(pilot, block, (2, 0), (16, 0))
        selected = app.screen.get_selected_text()
        assert selected and selected.strip()

        # Правый клик по пустой строке ввода (там же, где приглашение с путём).
        input_widget(app).value = ""
        row = app.query_one("#input-row")
        await right_click(pilot, widget=row, offset=(3, 1))
        await pilot.pause()
        assert input_widget(app).value == selected
        assert pyperclip.paste() == selected


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
