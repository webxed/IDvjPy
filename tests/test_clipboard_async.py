"""C1: системный clipboard не должен блокировать Textual event loop.

Внутренний буфер Textual обновляется сразу, системные backend-ы
(`pyperclip`, `xclip`/`xsel`/`wl-copy`/`wl-paste`) уходят в фоновый поток:
медленный или сломанный backend не морозит UI и не ломает fallback на
внутренний буфер.
"""
from __future__ import annotations

import asyncio
import threading
import time

import pyperclip
import pytest

pytestmark = pytest.mark.slow

from app import CommandRunner
from tests.conftest import input_widget, wait_clipboard


async def test_copy_does_not_block_on_slow_backend(isolated_home, monkeypatch):
    """`copy_text` возвращает управление сразу; системный backend — в фоне."""
    import app as app_module

    started: list[str] = []

    def slow_copy(text: str) -> None:
        started.append(text)
        time.sleep(0.5)

    monkeypatch.setattr(app_module, "copy_system", slow_copy)
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        t0 = time.monotonic()
        app.copy_text("payload")
        elapsed = time.monotonic() - t0
        assert elapsed < 0.2, f"обработчик ждал backend {elapsed:.2f}s"
        assert app.clipboard == "payload"  # внутренний буфер уже обновлён
        await wait_clipboard(app)
        assert started == ["payload"]


async def test_paste_falls_back_to_internal_when_system_empty(isolated_home, monkeypatch):
    """Пустой системный буфер — вставка берёт внутренний clipboard Textual."""
    import app as app_module

    monkeypatch.setattr(app_module, "read_system", lambda: "")
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        app.copy_to_clipboard("internal-only")
        app._paste_clipboard_into_input()
        await wait_clipboard(app)
        assert input_widget(app).value == "internal-only"


async def test_backend_error_keeps_internal_fallback(isolated_home, monkeypatch):
    """Ошибка backend-а не ломает fallback на внутренний буфер."""
    import app as app_module

    def boom() -> str:
        raise OSError("no clipboard backend")

    monkeypatch.setattr(app_module, "read_system", boom)
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        app.copy_to_clipboard("still-works")
        app._paste_clipboard_into_input()
        await wait_clipboard(app)
        assert input_widget(app).value == "still-works"


async def test_late_paste_does_not_modify_edited_input(isolated_home, monkeypatch):
    """Поздний clipboard worker не вставляет текст в уже изменённую строку."""
    import app as app_module

    started = threading.Event()
    release = threading.Event()

    def delayed_read() -> str:
        started.set()
        release.wait(timeout=2)
        return "late-paste"

    monkeypatch.setattr(app_module, "read_system", delayed_read)
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        inp = input_widget(app)
        inp.value = "before"
        inp.cursor_position = 3
        app._paste_clipboard_into_input()
        assert await asyncio.to_thread(started.wait, 1)
        inp.value = "changed"
        release.set()
        await wait_clipboard(app)
        assert inp.value == "changed"


async def test_vault_clear_skips_new_user_clipboard(isolated_home):
    """Выход из TTY/таймер не сотрёт то, что человек скопировал после секрета."""
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        pyperclip.copy("user-copied-new")
        app._vault_clip_pending = True
        app._vault_clip_value = "vault-secret-value"
        app._vault_clear_clipboard()
        await wait_clipboard(app)
        assert app._vault_clip_pending is False
        assert pyperclip.paste() == "user-copied-new"


async def test_vault_clear_erases_its_own_value(isolated_home):
    """Пока в буфере лежит значение vault, очистка его стирает."""
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        pyperclip.copy("vault-secret-value")
        app._vault_clip_pending = True
        app._vault_clip_value = "vault-secret-value"
        app._vault_clear_clipboard()
        await wait_clipboard(app)
        assert pyperclip.paste() == ""


async def test_old_vault_copy_cannot_overwrite_newer_value(isolated_home, monkeypatch):
    """Поздняя системная запись A не возвращает A после `:vault cp B`."""
    import app as app_module

    a_started = threading.Event()
    release_a = threading.Event()
    copied: list[str] = []

    def delayed_copy(value: str) -> None:
        if value == "A":
            a_started.set()
            release_a.wait(timeout=2)
        copied.append(value)
        pyperclip.copy(value)

    monkeypatch.setattr(app_module, "copy_system", delayed_copy)
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        app._vault_entries = {"A": {"value": "A"}, "B": {"value": "B"}}
        app._vault_copy("A")
        assert await asyncio.to_thread(a_started.wait, 1)
        app._vault_copy("B")
        release_a.set()
        await wait_clipboard(app)
        assert pyperclip.paste() == "B"
        assert copied == ["A", "B"]


async def test_old_vault_timer_cannot_clear_newer_value(isolated_home):
    """TTL A не имеет права очистить B после второй команды `:vault cp`."""
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        app._vault_entries = {"A": {"value": "A"}, "B": {"value": "B"}}
        app._vault_copy("A")
        old_generation = app._vault_clip_generation
        app._vault_copy("B")
        await wait_clipboard(app)
        app._vault_clear_clipboard(old_generation)
        await wait_clipboard(app)
        assert pyperclip.paste() == "B"
