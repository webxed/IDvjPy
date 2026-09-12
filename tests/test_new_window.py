"""`:new [NAME]` — новое окно приложения в отдельном терминале.

Отдельная сессия (свои `.bashrc_term_<NAME>` / `history_<NAME>.txt`), общий
data-каталог и БД тегов; секреты (`$$`) в новое окно не переносятся.
"""
import pytest

pytestmark = pytest.mark.slow

from app import CommandRunner
from tests.conftest import last_info, submit


class _Proc:
    pid = 4242


def _patch_open(monkeypatch) -> list[dict]:
    """Подменить запуск терминала; вернуть список вызовов."""
    import app as app_module

    calls: list[dict] = []

    def fake(command, *, cwd, environ, platform=None):
        calls.append({"command": list(command), "cwd": cwd, "env": dict(environ)})
        return ["xterm", "-e", *command], _Proc()

    monkeypatch.setattr(app_module, "open_terminal_command", fake)
    return calls


def _flag(command: list[str], prefix: str) -> str | None:
    for part in command:
        if part.startswith(prefix):
            return part
    return None


async def test_new_window_launches_instance(isolated_home, monkeypatch):
    calls = _patch_open(monkeypatch)
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ":new mysess")
        await pilot.pause()
        assert calls
        command = calls[0]["command"]
        assert _flag(command, "--instance-name=") == "--instance-name=mysess"
        assert _flag(command, "--data-dir=") == f"--data-dir={isolated_home}"
        assert calls[0]["cwd"] == str(isolated_home)
        assert "New window (session mysess," in last_info(app).text_content


async def test_new_window_default_name(isolated_home, monkeypatch):
    calls = _patch_open(monkeypatch)
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ":new")
        await pilot.pause()
        assert _flag(calls[0]["command"], "--instance-name=") == "--instance-name=s2"


async def test_session_new_alias(isolated_home, monkeypatch):
    calls = _patch_open(monkeypatch)
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ":session new alpha")
        await pilot.pause()
        assert _flag(calls[0]["command"], "--instance-name=") == "--instance-name=alpha"


async def test_new_window_invalid_name(isolated_home, monkeypatch):
    calls = _patch_open(monkeypatch)
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ":new ../evil")
        await pilot.pause()
        assert not calls
        assert "Usage: :new" in last_info(app).text_content


async def test_new_window_does_not_pass_secrets(isolated_home, monkeypatch):
    calls = _patch_open(monkeypatch)
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "$$TOKEN=supersecret")
        await submit(pilot, ":new")
        await pilot.pause()
        assert calls[0]["env"].get("TOKEN") is None


async def test_new_window_with_dir(isolated_home, monkeypatch):
    calls = _patch_open(monkeypatch)
    work = isolated_home / "work"
    work.mkdir()
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, f":new stage {work}")
        await pilot.pause()
        assert _flag(calls[0]["command"], "--instance-name=") == "--instance-name=stage"
        assert calls[0]["cwd"] == str(work)
        assert f"cwd {work}" in last_info(app).text_content


async def test_new_window_auto_name_dash_with_dir(isolated_home, monkeypatch):
    calls = _patch_open(monkeypatch)
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, f":new - {isolated_home}")
        await pilot.pause()
        assert _flag(calls[0]["command"], "--instance-name=") == "--instance-name=s2"
        assert calls[0]["cwd"] == str(isolated_home)


async def test_new_window_bad_dir(isolated_home, monkeypatch):
    calls = _patch_open(monkeypatch)
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ":new stage /no/such/dir")
        await pilot.pause()
        assert not calls
        assert "not a directory" in last_info(app).text_content


async def test_ctrl_n_opens_new_window(isolated_home, monkeypatch):
    """Footer-биндинг Ctrl+N / «New session» открывает новое окно."""
    calls = _patch_open(monkeypatch)
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("ctrl+n")
        await pilot.pause()
        assert calls
        assert _flag(calls[0]["command"], "--instance-name=") == "--instance-name=s2"
