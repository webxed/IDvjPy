"""Опечатки (command not found) не остаются в истории (фича history-hygiene)."""
import asyncio

import pytest

pytestmark = pytest.mark.slow

from app import CommandRunner
from history_store import append_history_file_line, remove_history_file_line
from tests.conftest import submit, wait_command_done


def test_remove_history_line_helper(tmp_path):
    path = tmp_path / "h.txt"
    append_history_file_line(str(path), "echo ok", lock_timeout=1)
    append_history_file_line(str(path), "Жр", lock_timeout=1)
    append_history_file_line(str(path), "echo again", lock_timeout=1)
    assert remove_history_file_line(str(path), "Жр", lock_timeout=1) is True
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines == ["echo ok", "echo again"]
    # Повторный вызов ничего не удаляет.
    assert remove_history_file_line(str(path), "Жр", lock_timeout=1) is False


async def test_typo_not_written_to_history(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        await submit(pilot, "Жр")
        block = await wait_command_done(app, timeout=8.0)
        assert block.return_code == 127
        hist_path = isolated_home / "history_default.txt"
        # Ждём «забывание» строки (оно идёт сразу после update блока).
        for _ in range(60):
            text = hist_path.read_text(encoding="utf-8", errors="replace")
            if "Жр" not in text:
                break
            await asyncio.sleep(0.05)
        assert "Жр" not in hist_path.read_text(encoding="utf-8")
        assert not any(line.strip() == "Жр" for line in app.session_history)
        # Ошибка при этом осталась видимой в журнале.
        assert "command not found" in block.raw_stderr.lower()


async def test_successful_and_other_127_keep_history(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        await submit(pilot, "echo fine")
        await wait_command_done(app, timeout=8.0)
        # exit 127 без 'command not found' — не опечатка, строку не трогаем.
        await submit(pilot, "bash -c 'exit 127'")
        await wait_command_done(app, timeout=8.0)
        hist_path = isolated_home / "history_default.txt"
        text = hist_path.read_text(encoding="utf-8")
        assert "echo fine" in text
        assert "bash -c 'exit 127'" in text
