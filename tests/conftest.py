"""Общие фикстуры для Pilot-тестов TUI."""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC = PROJECT_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from app import CommandBlock, CommandLineInput, CommandRunner, InfoBlock
from json_viewer import JSONViewer

TEST_SETTINGS = """\
max_lines: 1000
history_lines: 20
database_tags_file: test_history.db
command_timeout: 5
terminal_mouse: false
check_updates: false
screensaver_idle: 0
"""


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    """Изолирует cwd, БД, history и .bashrc_term от рабочей копии проекта."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "settings.yml").write_text(TEST_SETTINGS, encoding="utf-8")
    monkeypatch.setattr(CommandRunner, "CSS_PATH", str(PROJECT_ROOT / "src" / "app.tcss"))

    clip = {"text": ""}
    monkeypatch.setattr("pyperclip.copy", lambda text: clip.update(text=text or ""))
    monkeypatch.setattr("pyperclip.paste", lambda: clip["text"])

    linux_clip = {"clipboard": b"", "primary": b""}

    def fake_linux(selection, data=None):
        if data is not None:
            linux_clip[selection] = data
            return b""
        return linux_clip.get(selection) or None

    monkeypatch.setattr("clipboard._linux_clipboard_cmd", fake_linux)
    return tmp_path


@pytest.fixture(autouse=True)
def isolated_instance_name():
    """Откатить переключение сессии (`:session NAME`) после теста.

    `app.apply_instance_name` меняет **модульную** `INSTANCE_NAME` и классовые
    `FILE_HISTORY` / `FILE_BASHRC` — то есть на весь процесс. Без отката
    переключение сессии в одном тесте ломает все следующие: заголовок окна
    (`IDvjPy_term · NAME`), `secrets_<NAME>.json`, `inbox_<NAME>.jsonl`,
    `history_<NAME>.txt`, реестр `session_<NAME>.pid`. Именно так падал полный
    прогон (14 тестов в CI), хотя те же файлы по отдельности проходили.
    """
    import app as app_module

    original_name = app_module.INSTANCE_NAME
    original_history = app_module.CommandRunner.FILE_HISTORY
    original_bashrc = app_module.CommandRunner.FILE_BASHRC
    yield
    app_module.INSTANCE_NAME = original_name
    app_module.CommandRunner.FILE_HISTORY = original_history
    app_module.CommandRunner.FILE_BASHRC = original_bashrc


@pytest.fixture
def clip_store(monkeypatch):
    """Доступ к подменённому буферу обмена (тот же объект, что в isolated_home)."""
    import pyperclip

    # isolated_home already patched pyperclip; expose current paste/copy via module.
    return pyperclip


def input_widget(app: CommandRunner) -> CommandLineInput:
    return app.query_one(f"#{app.ID_INPUT}", CommandLineInput)


async def type_keys(pilot, text: str) -> None:
    """Печатает строку посимвольно, как с клавиатуры."""
    if text:
        await pilot.press(*text)


async def submit(pilot, text: str) -> None:
    """Фокус на input → очистить → набор → скрыть completion → Enter.

    Enter при открытом списке подсказок вставляет *другого* кандидата.
    Если выбран уже введённый путь (`ls ~/`), Enter выполняет команду.
    """
    await pilot.press("escape")
    inp = pilot.app.query_one("#command-input", CommandLineInput)
    inp.value = ""
    inp.cursor_position = 0
    await type_keys(pilot, text)
    await pilot.pause()
    await pilot.press("escape")
    await pilot.press("enter")
    await pilot.pause()


async def wait_command_done(app: CommandRunner, timeout: float = 8.0) -> CommandBlock:
    """Ждёт завершения фонового subprocess у последнего CommandBlock."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        blocks = list(app.query(CommandBlock))
        if (
            blocks
            and not blocks[-1].pending
            and blocks[-1].raw_stdout != "[Executing...]"
        ):
            return blocks[-1]
        await asyncio.sleep(0.05)
    raise AssertionError("Timed out waiting for CommandBlock to finish")


def last_info(app: CommandRunner) -> InfoBlock:
    blocks = list(app.query(InfoBlock))
    assert blocks, "No InfoBlock found"
    return blocks[-1]


def info_texts(app: CommandRunner) -> list[str]:
    return [block.text_content for block in app.query(InfoBlock)]


def completion_click_spans(clist) -> dict[int, str]:
    """{строка списка подсказок: текст, накрытый `@click`} по отрисованным strip'ам.

    Показывает, что именно в кадре стало ссылкой (и подсвечено): только команда
    или вся строка со счётчиком/описанием.
    """
    spans: dict[int, str] = {}
    for row in range(int(clist.size.height)):
        parts = [
            segment.text
            for segment in clist.render_line(row)
            if segment.style is not None
            and segment.style.meta
            and "@click" in segment.style.meta
        ]
        text = "".join(parts).strip()
        if text:
            spans[row] = text
    return spans


def completion_underline_spans(clist) -> dict[int, str]:
    """{строка списка: текст, нарисованный с подчёркиванием} — «вид ссылки» в кадре.

    Ссылка в Textual (`@click`-span) получает `link-style` темы — подчёркивание;
    по нему и видно, что строка выглядит ссылкой, а не обычным текстом.
    """
    spans: dict[int, str] = {}
    for row in range(int(clist.size.height)):
        parts = [
            segment.text
            for segment in clist.render_line(row)
            if segment.style is not None and segment.style.underline
        ]
        text = "".join(parts).strip()
        if text:
            spans[row] = text
    return spans


async def confirm_input(pilot, app: CommandRunner, timeout: float = 8.0) -> CommandBlock:
    """Enter по уже вставленной в input команде (! / !!)."""
    await pilot.press("escape")
    await pilot.press("enter")
    await pilot.pause()
    return await wait_command_done(app, timeout=timeout)


async def wait_json_viewer(app: CommandRunner, timeout: float = 3.0) -> JSONViewer:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if isinstance(app.screen, JSONViewer):
            return app.screen
        await asyncio.sleep(0.05)
    raise AssertionError(
        "JSONViewer did not open. Last info: "
        + (last_info(app).text_content if list(app.query(InfoBlock)) else "<none>")
    )
