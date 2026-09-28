"""Ctrl+C в чужой программе (`> cmd`, `:ed`, консоль Ctrl+O) не должен ронять TUI.

Ребёнок живёт в той же группе процессов, что и приложение, поэтому SIGINT от
Ctrl+C приходит обоим. Пока терминал отдан ребёнку, родитель глотает сигнал
**обработчиком**, а не `SIG_IGN`: `SIG_IGN` наследуется потомком через `exec`
и оставил бы чужую программу без Ctrl+C (приложение застревало в `suspend()`).
"""
from __future__ import annotations

import contextlib
import signal

import pytest

import app as app_module
from app import CommandRunner, _ignore_interrupt_signals


@pytest.fixture(autouse=True)
def _restore_signals():
    """Не оставлять подменённые обработчики соседним тестам."""
    saved = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGQUIT)}
    yield
    for sig, handler in saved.items():
        signal.signal(sig, handler)


def test_uses_handler_not_sig_ign():
    """Ключевой инвариант: именно обработчик — SIG_IGN унаследовался бы ребёнком."""
    before = signal.getsignal(signal.SIGINT)
    restore = _ignore_interrupt_signals()
    installed = signal.getsignal(signal.SIGINT)
    assert installed is not signal.SIG_IGN, "SIG_IGN наследуется через exec"
    assert installed is not signal.SIG_DFL
    assert installed is not before
    restore()
    assert signal.getsignal(signal.SIGINT) is before


def test_restore_is_idempotent():
    before = signal.getsignal(signal.SIGINT)
    restore = _ignore_interrupt_signals()
    restore()
    restore()  # повторный вызов — no-op, а не падение
    assert signal.getsignal(signal.SIGINT) is before


def test_ignores_sigquit_too():
    before = signal.getsignal(signal.SIGQUIT)
    restore = _ignore_interrupt_signals()
    assert signal.getsignal(signal.SIGQUIT) is not before
    restore()
    assert signal.getsignal(signal.SIGQUIT) is before


async def test_run_in_tty_swallows_signals_and_reports_shell_code(
    isolated_home, monkeypatch
):
    """На время ребёнка сигнал проглочен; смерть от SIGINT — код 130, как в shell."""
    app = CommandRunner()
    async with app.run_test(size=(80, 24)):
        seen: dict[str, object] = {}

        class Result:
            returncode = -2  # ребёнок убит SIGINT

        def fake_run(*args, **kwargs):
            seen["sigint"] = signal.getsignal(signal.SIGINT)
            return Result()

        monkeypatch.setattr(app_module.subprocess, "run", fake_run)
        monkeypatch.setattr(app, "_ingest_tty_session", lambda *a, **k: [])
        # Наш `suspend()` оставляем живым — он и ставит обработчик; подменяем только
        # родительский Textual-`App.suspend`, которому в headless-режиме нет драйвера.
        monkeypatch.setattr(app_module.App, "suspend", lambda self: contextlib.nullcontext())
        before = signal.getsignal(signal.SIGINT)

        code = app._run_in_tty("sleep 30")

        assert seen["sigint"] is not signal.SIG_IGN
        assert seen["sigint"] is not before, "пока ребёнок жив, сигнал проглочен"
        assert code == 130, "128 + SIGINT, а не сырое -2"
        assert signal.getsignal(signal.SIGINT) is before, "обработчик восстановлен"


async def test_app_suspend_swallows_signals_inside(isolated_home, monkeypatch):
    """Сам `suspend()` (общий для `> cmd`, `:ed`, Ctrl+O) оборачивает сигналы."""
    app = CommandRunner()
    async with app.run_test(size=(80, 24)):
        seen: dict[str, object] = {}

        @contextlib.contextmanager
        def fake_super_suspend(self):
            seen["during"] = signal.getsignal(signal.SIGINT)
            yield

        monkeypatch.setattr(app_module.App, "suspend", fake_super_suspend)
        before = signal.getsignal(signal.SIGINT)

        with app.suspend():
            pass

        assert seen["during"] is not signal.SIG_IGN
        assert seen["during"] is not before
        assert signal.getsignal(signal.SIGINT) is before
