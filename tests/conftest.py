"""Общие фикстуры для Pilot-тестов TUI."""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest

from app import CommandBlock, CommandInput, CommandRunner, InfoBlock
from json_viewer import JSONViewer

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_SETTINGS = """\
max_lines: 1000
history_lines: 20
database_tags_file: test_history.db
command_timeout: 5
terminal_mouse: false
"""


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    """Изолирует cwd, БД, history и .bashrc_term от рабочей копии проекта."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "settings.yml").write_text(TEST_SETTINGS, encoding="utf-8")
    monkeypatch.setattr(CommandRunner, "CSS_PATH", str(PROJECT_ROOT / "app.css"))

    clip = {"text": ""}
    monkeypatch.setattr("pyperclip.copy", lambda text: clip.update(text=text or ""))
    monkeypatch.setattr("pyperclip.paste", lambda: clip["text"])

    linux_clip = {"clipboard": b"", "primary": b""}

    def fake_linux(selection, data=None):
        if data is not None:
            linux_clip[selection] = data
            return b""
        return linux_clip.get(selection) or None

    monkeypatch.setattr("app._linux_clipboard_cmd", fake_linux)
    return tmp_path


@pytest.fixture
def clip_store(monkeypatch):
    """Доступ к подменённому буферу обмена (тот же объект, что в isolated_home)."""
    import pyperclip

    # isolated_home already patched pyperclip; expose current paste/copy via module.
    return pyperclip


def input_widget(app: CommandRunner) -> CommandInput:
    return app.query_one(f"#{app.ID_INPUT}", CommandInput)


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
    inp = pilot.app.query_one("#command-input", CommandInput)
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
