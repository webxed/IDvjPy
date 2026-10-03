"""Безопасное открытие файлов `:md`: тип/размер до чтения, чтение в фоне.

Аудит C2: каталоги, FIFO и устройства отклоняются до чтения (FIFO заблокировал
бы обработчик); текст читается и декодируется в фоновом потоке; слишком большой
файл отклоняется с подсказкой про `md_max_bytes`, а не тянется целиком в event
loop.
"""
from __future__ import annotations

import asyncio
import os
import threading
from pathlib import Path

import pytest

from app import CommandRunner
from md_viewer import HandbookMarkdownScreen
from tests.conftest import last_info, wait_md


def _append_setting(home: Path, line: str) -> None:
    settings = home / "settings.yml"
    settings.write_text(settings.read_text(encoding="utf-8") + line, encoding="utf-8")


async def test_md_rejects_directory(isolated_home):
    target = isolated_home / "folder"
    target.mkdir()
    app = CommandRunner()
    async with app.run_test(size=(100, 20)) as pilot:
        app._open_md_file(target)
        await pilot.pause()
        assert "not a regular file" in last_info(app).text_content
        assert not isinstance(app.screen, HandbookMarkdownScreen)


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="FIFO is POSIX-only")
async def test_md_rejects_fifo(isolated_home):
    fifo = isolated_home / "pipe"
    os.mkfifo(fifo)
    app = CommandRunner()
    async with app.run_test(size=(100, 20)) as pilot:
        app._open_md_file(fifo)
        await pilot.pause()
        assert "not a regular file" in last_info(app).text_content


async def test_md_refuses_oversized_text(isolated_home):
    _append_setting(isolated_home, "md_max_bytes: 100\n")
    note = isolated_home / "big.md"
    note.write_text("x" * 500, encoding="utf-8")
    app = CommandRunner()
    async with app.run_test(size=(100, 20)) as pilot:
        app._open_md_file(note)
        await pilot.pause()
        text = last_info(app).text_content
        assert "md_max_bytes" in text
        assert "500 B" in text  # размер файла в сообщении
        assert app._md_worker is not None  # проверка размера работает в worker-е
        assert not isinstance(app.screen, HandbookMarkdownScreen)


async def test_md_read_error_is_reported(isolated_home, monkeypatch):
    note = isolated_home / "note.md"
    note.write_text("# ok\n", encoding="utf-8")
    app = CommandRunner()
    async with app.run_test(size=(100, 20)) as _pilot:

        def boom(self: Path):
            raise OSError("simulated read failure")

        monkeypatch.setattr(Path, "read_bytes", boom)
        app._open_md_file(note)
        await wait_md(app)
        assert "simulated read failure" in last_info(app).text_content


async def test_md_text_read_is_offloaded(isolated_home):
    """Текст открывается после фонового чтения в управляемом Worker."""
    note = isolated_home / "note.md"
    note.write_text("# note\n\ntext\n", encoding="utf-8")
    app = CommandRunner()
    async with app.run_test(size=(100, 20)) as _pilot:
        app._open_md_file(note)
        assert app._md_worker is not None
        await wait_md(app)
        assert isinstance(app.screen, HandbookMarkdownScreen)


async def test_late_md_result_does_not_replace_newer_request(isolated_home, monkeypatch):
    """Медленный первый `:md` не открывается поверх второго запроса."""
    slow = isolated_home / "slow.md"
    fast = isolated_home / "fast.md"
    slow.write_text("# slow\n", encoding="utf-8")
    fast.write_text("# fast\n", encoding="utf-8")
    entered = threading.Event()
    release = threading.Event()
    real_read = Path.read_bytes

    def delayed_read(self: Path) -> bytes:
        if self == slow:
            entered.set()
            release.wait(timeout=2)
        return real_read(self)

    monkeypatch.setattr(Path, "read_bytes", delayed_read)
    app = CommandRunner()
    async with app.run_test(size=(100, 20)) as _pilot:
        app._open_md_file(slow)
        assert await asyncio.to_thread(entered.wait, 1)
        app._open_md_file(fast)
        release.set()
        await wait_md(app)
        assert isinstance(app.screen, HandbookMarkdownScreen)
        assert app.screen._path == fast
