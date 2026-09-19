"""Приглашение в строке ввода: текущий каталог серым слева (как в терминале).

Плейсхолдера «Enter command» больше нет: путь видно и когда строка пуста, и пока
в неё набирают команду. Укорачивание (`~`, хвост длинного пути) проверяется
отдельно — оно не должно отдавать полю ввода меньше трети ширины окна.
"""
from __future__ import annotations

import os

from app import CWD_PROMPT_SEP, CommandRunner, shorten_path
from tests.conftest import input_widget, submit, wait_command_done


def test_shorten_path_home_and_plain():
    assert shorten_path("/home/u/w/work/proj", home="/home/u") == "~/w/work/proj"
    assert shorten_path("/home/u", home="/home/u") == "~"
    assert shorten_path("/home/u/", home="/home/u") == "~"
    # Дом — не префикс: путь остаётся как есть.
    assert shorten_path("/tmp/x", home="/home/u") == "/tmp/x"
    assert shorten_path("/home/ux", home="/home/u") == "/home/ux"


def test_shorten_path_keeps_the_tail():
    """Длинный путь укорачивается с начала: где ты — понятно по хвосту."""
    assert shorten_path("/home/u/w/work/proj", home="/home/u", max_len=12) == "…/work/proj"
    assert shorten_path("/home/u/w/work/proj", home="/home/u", max_len=6) == "…/proj"
    # Один компонент длиннее лимита — режется он сам.
    assert shorten_path("/home/u/very-long-dir-name", home="/home/u", max_len=8) == "…/very-…"


def test_shorten_path_without_limit_is_a_prompt_ready_path():
    assert shorten_path("/home/u/w/work/proj", home="/home/u", max_len=0) == "~/w/work/proj"


def _prompt(app: CommandRunner) -> str:
    return str(app.query_one(f"#{app.ID_CWD_PROMPT}").content)


async def test_prompt_shows_cwd_and_follows_cd(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        # Долгий временный путь укорачивается с начала, но хвост виден.
        assert _prompt(app).endswith(f"{os.path.basename(os.getcwd())} {CWD_PROMPT_SEP} ")
        # Плейсхолдер «Enter command» заменён путём.
        assert app.query_one(f"#{app.ID_INPUT}").placeholder == ""
        await submit(pilot, "cd /tmp")
        assert _prompt(app) == f"/tmp {CWD_PROMPT_SEP} "
        await submit(pilot, ":cd /")
        assert _prompt(app) == f"/ {CWD_PROMPT_SEP} "


async def test_prompt_shortens_home_and_long_paths(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(60, 24)) as pilot:
        home = os.path.expanduser("~")
        await submit(pilot, f":cd {home}")
        assert _prompt(app) == f"~ {CWD_PROMPT_SEP} "

        deep = os.path.join(home, "some", "quite", "deep", "directory", "name")
        os.makedirs(deep, exist_ok=True)
        await submit(pilot, f":cd {deep}")
        path = _prompt(app).removesuffix(f" {CWD_PROMPT_SEP} ")
        assert path.startswith("…/") and path.endswith("name")
        assert len(path) <= max(12, app.size.width // 3)


async def test_prompt_fits_a_narrow_window(isolated_home):
    """Узкое окно не отдаёт под путь больше трети ширины."""
    app = CommandRunner()
    async with app.run_test(size=(48, 24)):
        path = _prompt(app).removesuffix(f" {CWD_PROMPT_SEP} ")
        assert len(path) <= max(12, app.size.width // 3)


async def test_click_on_prompt_focuses_input(isolated_home):
    """Мышь — ускорение: клик по пути возвращает фокус в строку ввода."""
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "echo prompt-click")
        await wait_command_done(app, timeout=8.0)
        await pilot.press("tab")  # Tab уводит фокус в журнал
        assert not input_widget(app).has_focus
        await pilot.click(f"#{app.ID_CWD_PROMPT}")
        assert input_widget(app).has_focus
