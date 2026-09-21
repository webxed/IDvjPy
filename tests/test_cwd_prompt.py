"""Строка ввода: серое приглашение с cwd и превью длинной строки.

Плейсхолдера «Enter command» больше нет: путь видно и когда строка пуста, и пока
в неё набирают команду. Укорачивание (`~`, хвост длинного пути) проверяется
отдельно — оно не должно отдавать полю ввода меньше трети ширины окна.
Поле однострочное, поэтому длинное значение (в т.ч. вставленное) целиком видно в
превью под полем, а переносы строк из буфера склопываются в пробел (`paste_line`).
"""
from __future__ import annotations

import os
from typing import Any, cast

import pyperclip
from textual import events
from textual.widgets import Static

from app import CWD_PROMPT_SEP, CommandRunner, paste_line, shorten_path
from tests.conftest import (
    input_widget,
    last_info,
    right_click,
    submit,
    type_keys,
    wait_command_done,
)


async def test_bare_dash_without_previous_dir_reports(isolated_home, monkeypatch):
    """`-` без предыдущего каталога — явная ошибка, а не молчание."""
    monkeypatch.delenv("OLDPWD", raising=False)
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "-")
        assert "OLDPWD not set" in last_info(app).text_content
        assert os.path.samefile(os.getcwd(), isolated_home)


async def test_bare_path_is_cd(isolated_home):
    """Строка целиком — путь к каталогу: это `cd` без слова `cd`.

    Навигация без лишнего набора: `subdir`, `./subd` → подсказка → Enter, `..`.
    Файл (`./run.sh`) остаётся командой — путь-не-каталог в cd не превращается.
    """
    (isolated_home / "subdir").mkdir()
    script = isolated_home / "run.sh"
    script.write_text("#!/bin/sh\necho ran\n", encoding="utf-8")
    script.chmod(0o755)
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "subdir")
        assert os.path.samefile(os.getcwd(), isolated_home / "subdir")
        assert "cwd:" in last_info(app).text_content

        await submit(pilot, "..")
        assert os.path.samefile(os.getcwd(), isolated_home)

        # `-` — как `cd -`: обратно в предыдущий каталог.
        await submit(pilot, "subdir")
        await submit(pilot, "-")
        assert os.path.samefile(os.getcwd(), isolated_home)
        assert "cwd:" in last_info(app).text_content

        # Файл — не путь-каталог: строка уходит shell'у, а не в `cd`.
        await submit(pilot, "./run.sh")
        assert "ran" in (await wait_command_done(app)).raw_stdout
        assert os.path.samefile(os.getcwd(), isolated_home)

        # Та же навигация через подсказку пути: дополнили → перешли.
        await type_keys(pilot, "./subd")
        await pilot.pause()
        assert app._completion_list.is_visible()
        await pilot.press("enter")
        await pilot.pause()
        assert input_widget(app).value == "./subdir/"
        await pilot.press("enter")
        await pilot.pause()
        assert os.path.samefile(os.getcwd(), isolated_home / "subdir")


async def test_cd_emits_osc7_for_the_terminal(isolated_home):
    """`cd` говорит терминалу свой каталог (OSC 7) — как это делает сама оболочка."""
    (isolated_home / "subdir").mkdir()
    writes: list[str] = []

    class _Driver:
        is_headless = False

        def write(self, data: str) -> None:
            writes.append(data)

        def flush(self) -> None:
            pass

    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        real_driver = app._driver
        cast(Any, app)._driver = _Driver()
        try:
            app._change_cwd(str(isolated_home / "subdir"))
        finally:
            cast(Any, app)._driver = real_driver
    osc = [w for w in writes if w.startswith("\x1b]7;file://localhost/")]
    assert osc and osc[-1].endswith("subdir\x07")


async def test_exit_cwd_note_is_ready_made_command(isolated_home):
    """Приложение отдаёт лаунчеру готовую строку `cd …` ("" — каталог не менялся)."""
    (isolated_home / "sub dir").mkdir()
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert app.exit_cwd_note() == ""
        await submit(pilot, "'./sub dir'")
        target = isolated_home / "sub dir"
        # Пробел в пути — кавычки наши (`quote_shell_path`), готовая команда без сюрпризов.
        assert app.exit_cwd_note() == f"cd '{target}'"
        await submit(pilot, "..")
        assert app.exit_cwd_note() == ""


async def test_exit_writes_cwd_file_and_emits_osc7(isolated_home, monkeypatch):
    """Выход: каталог окна едет в `$IDVJPY_CWD_FILE` (для обёртки) и в OSC 7.

    Сменить каталог родительской оболочки процесс не может — поэтому обёртка в
    shell читает файл после выхода и делает `cd "$(cat …)"` (как ranger/nnn).
    """
    (isolated_home / "subdir").mkdir()
    cwd_file = isolated_home / "cwd.txt"
    monkeypatch.setenv("IDVJPY_CWD_FILE", str(cwd_file))
    calls: list[str] = []
    monkeypatch.setattr(
        CommandRunner, "_emit_terminal_cwd", lambda self: calls.append(os.getcwd())
    )
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await submit(pilot, "subdir")
        assert os.path.samefile(os.getcwd(), isolated_home / "subdir")
    assert cwd_file.read_text(encoding="utf-8").strip() == str(isolated_home / "subdir")
    # `cd` и выход — оба говорят терминалу про каталог.
    assert len(calls) >= 2


def test_cwd_followup_note_file_missing_is_silent(tmp_path, monkeypatch):
    """Обёртки нет — приложение просто молчит (файл не создаётся)."""
    monkeypatch.delenv("IDVJPY_CWD_FILE", raising=False)
    app = CommandRunner()
    app._write_cwd_file()  # не должно бросить


def test_wrap_display_line_by_width():
    from app import wrap_display_line

    assert wrap_display_line("aaa bbb ccc ddd", 7) == ["aaa bbb", "ccc ddd"]
    # Длинный токен (путь без пробелов) режется по ширине.
    assert wrap_display_line("x" * 25, 10) == ["x" * 10, "x" * 10, "x" * 5]
    assert wrap_display_line("short", 40) == ["short"]


def test_paste_line_collapses_newlines():
    assert paste_line("a\nb") == "a b"
    assert paste_line("a\r\nb") == "a b"
    assert paste_line("a \n  b") == "a b"
    assert paste_line("a\n\nb") == "a b"
    # Однострочный текст не трогаем — отступы автора сохраняются.
    assert paste_line("one line") == "one line"
    assert paste_line("  padded  ") == "  padded  "


async def test_long_line_preview_shows_whole_command(isolated_home):
    """Длинная строка не умещается в поле — её видно целиком в превью под ним."""
    app = CommandRunner()
    async with app.run_test(size=(80, 30)) as pilot:
        preview = app.query_one(f"#{app.ID_INPUT_PREVIEW}", Static)
        inp = input_widget(app)

        inp.value = "echo short"
        await pilot.pause()
        await pilot.pause()
        assert preview.styles.display == "none"  # короткая — превью не нужно

        line = "echo " + " ".join(f"part{i:02d}" for i in range(20))
        inp.value = line
        await pilot.pause()
        await pilot.pause()
        assert preview.styles.display == "block"
        shown = "\n".join(str(preview.content).splitlines())
        # Ничего не потеряли: все токены строки видны в превью.
        assert shown.split() == line.split()
        # И строка ввода стала выше (превью заняло строки).
        assert inp.value == line


async def test_preview_hidden_for_secret_entries(isolated_home):
    """Секретная строка замаскирована — превью её не раскрывает."""
    app = CommandRunner()
    async with app.run_test(size=(80, 30)) as pilot:
        preview = app.query_one(f"#{app.ID_INPUT_PREVIEW}", Static)
        input_widget(app).value = "$$TOKEN=" + "s3cr3t" * 30
        await pilot.pause()
        await pilot.pause()
        assert preview.styles.display == "none"


async def test_preview_masks_live_secret_values(isolated_home):
    """Живой `$$`-секрет в обычной строке — в превью вместо значения маска."""
    app = CommandRunner()
    async with app.run_test(size=(80, 30)) as pilot:
        preview = app.query_one(f"#{app.ID_INPUT_PREVIEW}", Static)
        await submit(pilot, "$$TOKEN=super-secret-value")
        secret = app.local_env.get("TOKEN") or "super-secret-value"
        assert secret

        input_widget(app).value = f"curl -H 'Authorization: Bearer {secret}' " + "x" * 60
        await pilot.pause()
        await pilot.pause()
        shown = str(preview.content)
        assert secret not in shown
        assert "****" in shown


async def test_terminal_paste_inserts_all_lines(isolated_home):
    """Вставка терминалом (Paste-событие) не теряет хвост многострочного текста."""
    app = CommandRunner()
    async with app.run_test(size=(80, 30)) as pilot:
        app.post_message(events.Paste("paste-one\npaste-two\npaste-three"))
        await pilot.pause()
        await pilot.pause()
        assert input_widget(app).value == "paste-one paste-two paste-three"


async def test_right_click_and_ctrl_v_agree_about_newlines(isolated_home):
    """Правый клик и буфер дают одно и то же: переносы → пробел."""
    app = CommandRunner()
    async with app.run_test(size=(80, 30)) as pilot:
        pyperclip.copy("multi\nline\ncommand")
        await right_click(pilot, offset=(20, 20))
        await pilot.pause()
        assert input_widget(app).value == "multi line command"
        assert "\n" not in input_widget(app).value


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
    return str(app.query_one(f"#{app.ID_CWD_PROMPT}", Static).content)


async def test_prompt_shows_cwd_and_follows_cd(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        # Долгий временный путь укорачивается с начала, но хвост виден.
        assert _prompt(app).endswith(f"{os.path.basename(os.getcwd())} {CWD_PROMPT_SEP} ")
        # Плейсхолдер «Enter command» заменён путём.
        assert input_widget(app).placeholder == ""
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
