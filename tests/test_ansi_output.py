"""ANSI/ESC в выводе команд: цвета как в терминале, мусор не течёт в кадр.

Проверяем две вещи:
1. разбор (`ansi_output`): SGR → разметка, прочие последовательности и `\\r`
   обрабатываются как в терминале;
2. приложение (`ansi_colors`): сырых escape-кодов нет ни в кадре, ни в плоском
   тексте, который уходит в копирование/пайп/`$OUT`.
"""
from __future__ import annotations

import re

import pytest
from textual.content import Content

from ansi_output import (
    MAX_MARKUP_CHARS,
    collapse_carriage_returns,
    keep_sgr,
    strip_escapes,
    to_markup,
    to_plain,
)
from tests.conftest import input_widget, submit, wait_command_done

RE_COLOR_TAG = re.compile(r"\[(?:ansi_|rgb\(|#)")


# --- разбор текста -----------------------------------------------------------


def test_strip_escapes_removes_sgr_osc_and_control():
    assert strip_escapes("\x1b[31mred\x1b[0m") == "red"
    assert strip_escapes("\x1b]0;window title\x07tail") == "tail"
    assert strip_escapes("bell\x07 and backspace\x08") == "bell and backspace"
    # \n и \t — часть текста, а не управление терминалом.
    assert strip_escapes("tab\there\nnew") == "tab\there\nnew"


def test_strip_escapes_leaves_brackets_alone():
    """Скобки — текст, а не управление: их экранирует разметка, а не вырезание."""
    assert strip_escapes("json [1, 2] and \x1b[31mbold\x1b[0m") == "json [1, 2] and bold"


def test_collapse_carriage_returns_matches_terminal():
    assert collapse_carriage_returns("abc\rde") == "dec"  # перезапись с колонки 0
    # Хвост старого текста остаётся — ровно как в терминале.
    assert collapse_carriage_returns("100%\r50%") == "50%%"
    # `\x1b[K` стирает хвост: разбирает `to_plain`, у collapse последовательности ещё на месте.
    assert to_plain("100%\r\x1b[K50%") == "50%"
    assert collapse_carriage_returns("a\r\nb") == "a\nb"  # CRLF не добавляет строк
    assert collapse_carriage_returns("no cr here") == "no cr here"


def test_to_plain_progress_bar_becomes_one_line():
    progress = "".join(f"\r{percent}%" for percent in (10, 55, 100))
    assert to_plain(progress) == "100%"
    assert to_plain("curl: downloading 10%\r\x1b[Kcurl: done").splitlines() == ["curl: done"]


def test_to_plain_keeps_text_without_escapes_untouched():
    text = "plain [text] with\ttab\nand newline"
    assert to_plain(text) == text


def test_to_markup_turns_sgr_into_colors_without_leaking_escapes():
    markup = to_markup("\x1b[31mred\x1b[0m [x] \x1b[1mbold\x1b[0m")
    assert "\x1b" not in markup
    assert RE_COLOR_TAG.search(markup)
    # `[x]` из вывода остаётся текстом, а не разметкой Textual.
    assert Content.from_markup(markup).plain == "red [x] bold"


def test_to_markup_drops_cursor_and_osc_but_keeps_color():
    markup = to_markup("\x1b[32mgreen\x1b]0;title\x07\x1b[2K still green")
    assert Content.from_markup(markup).plain == "green still green"
    assert "\x1b" not in markup


def test_keep_sgr_leaves_only_color_codes():
    kept = keep_sgr("a\x1b[1;31mb\x1b[0mc\x1b[2Kd")
    assert kept == "a\x1b[1;31mb\x1b[0mcd"


def test_to_markup_falls_back_to_plain_for_huge_output():
    """Разбор ANSI не должен тормозить кадр: выше лимита — плоский текст."""
    text = "\x1b[31mx\x1b[0m " * (MAX_MARKUP_CHARS // 6)
    assert len(text) > MAX_MARKUP_CHARS
    markup = to_markup(text)
    assert "\x1b" not in markup
    assert Content.from_markup(markup).plain == "x " * (MAX_MARKUP_CHARS // 6)


# --- приложение --------------------------------------------------------------


@pytest.mark.slow
async def test_ansi_output_is_colored_but_never_raw_in_frame(isolated_home):
    from app import CommandBlock, CommandRunner

    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, r"printf '\033[38;5;226mYELLOW\033[0m plain\nsecond\rOVER\n'")
        block = await wait_command_done(app)
        assert isinstance(block, CommandBlock)

        # Данные команды остаются настоящими: ANSI сохранён для цветного рендера.
        assert "\x1b[38;5;226m" in block.raw_stdout
        # Плоский текст — без escape-кодов и с терминальным `\r`.
        assert "\x1b" not in block.plain_stdout
        assert "YELLOW plain" in block.plain_stdout
        assert "OVERnd" in block.plain_stdout
        assert "\x1b" not in block.text_content

        payload = block._display_payload()
        assert "\x1b" not in payload
        shown = Content.from_markup(payload).plain
        assert "YELLOW plain" in shown and "OVERnd" in shown
        # В кадре (strip'ах) сырых последовательностей тоже нет: цвета — в стилях.
        frame = "".join(
            block.render_line(y).text for y in range(int(block.size.height))
        )
        assert "\x1b" not in frame
        # Хотя один из сегментов строки вывода действительно цветной.
        colors = [
            segment.style.color
            for y in range(int(block.size.height))
            for segment in block.render_line(y)
            if segment.style is not None and segment.style.color is not None
        ]
        assert colors


@pytest.mark.slow
async def test_ansi_colors_render_on_line_api_blocks(isolated_home):
    """Второй путь рендера (`line_api_blocks: true`) тоже без сырых ESC."""
    from app import CommandRunner

    settings = isolated_home / "settings.yml"
    settings.write_text(
        settings.read_text(encoding="utf-8") + "line_api_blocks: true\n", encoding="utf-8"
    )
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        assert app._line_api_blocks is True
        await submit(pilot, r"printf '\033[38;5;226mYELLOW\033[0m plain\n'")
        block = await wait_command_done(app)
        body = [
            block.render_line(y).text for y in range(int(block.size.height))
        ]
        joined = "\n".join(body)
        assert "\x1b" not in joined
        assert "YELLOW plain" in joined
        colors = [
            segment.style.color
            for y in range(int(block.size.height))
            for segment in block.render_line(y)
            if segment.style is not None and segment.style.color is not None
        ]
        assert colors


@pytest.mark.slow
async def test_output_history_and_log_viewer_are_escape_free(isolated_home):
    """`:o` и `:log` / F7 показывают плоский текст: escape-коды в кадр не уходят."""
    import asyncio

    from app import CommandRunner
    from output_viewer import OutputViewerScreen
    from tests.conftest import last_info

    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, r"printf '\033[31mred-err\033[0m\n' >&2; echo ready")
        await wait_command_done(app)

        await submit(pilot, ":o")
        stored = last_info(app).text_content
        assert "\x1b" not in stored
        assert "red-err" in stored

        await submit(pilot, ":log")
        deadline = asyncio.get_running_loop().time() + 3.0
        while not isinstance(app.screen, OutputViewerScreen):
            assert asyncio.get_running_loop().time() < deadline, "viewer did not open"
            await asyncio.sleep(0.05)
        viewer = app.screen
        lines = getattr(viewer, "_lines", [])
        assert lines
        assert "\x1b" not in "\n".join(lines)
        assert any("red-err" in line for line in lines)


@pytest.mark.slow
async def test_ansi_colors_off_keeps_text_plain(isolated_home):
    """Ключ `ansi_colors: false` — плоский вывод без разметки цвета."""
    from app import CommandBlock, CommandRunner

    settings = isolated_home / "settings.yml"
    settings.write_text(
        settings.read_text(encoding="utf-8") + "ansi_colors: false\n", encoding="utf-8"
    )
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        assert app.ansi_colors is False
        await submit(pilot, r"printf '\033[31mred\033[0m text\n'")
        block = await wait_command_done(app)
        assert isinstance(block, CommandBlock)
        payload = block._display_payload()
        assert "\x1b" not in payload
        assert not RE_COLOR_TAG.search(payload)
        assert "red text" in Content.from_markup(payload).plain


@pytest.mark.slow
async def test_copy_block_and_pipe_receive_plain_text(isolated_home):
    """F3 и `|` берут текст без escape-кодов: иначе ESC уходит в буфер и в команду."""
    import pyperclip

    from app import CommandBlock, CommandRunner

    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, r"printf '\033[31mred\033[0m\n'")
        block = await wait_command_done(app)
        block.focus()
        await pilot.pause()
        await pilot.press("f3")
        await pilot.pause()
        assert pyperclip.paste().strip() == "red"

        await submit(pilot, "| cat")
        piped = await wait_command_done(app)
        assert isinstance(piped, CommandBlock)
        assert piped.raw_stdout.strip() == "red"


@pytest.mark.slow
async def test_simple_output_mode_turns_colors_off(isolated_home):
    """F6 обещает плоский текст: цвета выключаются вместе с разметкой."""
    from app import CommandRunner

    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, r"printf '\033[31mred\033[0m\n'")
        block = await wait_command_done(app)
        await pilot.press("escape")
        block.focus()
        await pilot.pause()
        await pilot.press("f6")
        await pilot.pause()
        payload = block._display_payload()
        assert "\x1b" not in payload
        assert not RE_COLOR_TAG.search(payload)
        assert "red" in payload
        assert app.simple_output_mode
        await pilot.press("f6")
        await pilot.pause()
        assert not app.simple_output_mode


@pytest.mark.slow
async def test_ansi_colors_default_is_on(isolated_home):
    """Без ключа в settings.yml цвета включены: поведение по умолчанию — как в терминале."""
    from app import CommandRunner

    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert app.ansi_colors is True
        assert input_widget(app).has_focus
