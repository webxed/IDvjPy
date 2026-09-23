"""`:new [NAME]` — новое окно приложения в отдельном терминале.

Отдельная сессия (свои `.bashrc_term_<NAME>` / `history_<NAME>.txt`), общий
data-каталог и БД тегов; секреты (`$$`) в новое окно не переносятся.
"""
import os

import pytest

pytestmark = pytest.mark.slow

from app import CommandRunner
from session_registry import active_sessions, registry_path, unregister
from tests.conftest import last_info, submit


class _Proc:
    def __init__(self, pid: int = 4242) -> None:
        self.pid = pid


def _patch_open(monkeypatch, *, pid: int = 4242) -> list[dict]:
    """Подменить запуск терминала; вернуть список вызовов.

    ``pid`` — pid «поднятого» терминала. По умолчанию выдуманный (мёртвый),
    поэтому автоимя следующего окна его не увидит; тесты, которым нужно живое
    окно, передают ``os.getpid()``.
    """
    import app as app_module

    calls: list[dict] = []

    def fake(command, *, cwd, environ, platform=None, mode="window"):
        calls.append({"command": list(command), "cwd": cwd, "env": dict(environ), "mode": mode})
        return ["xterm", "-e", *command], _Proc(pid)

    monkeypatch.setattr(app_module, "open_terminal_command", fake)
    return calls


def _names(calls: list[dict]) -> list[str | None]:
    """Автоимена/имена сессий из всех вызовов запуска окна."""
    return [_flag(call["command"], "--instance-name=") for call in calls]


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


async def test_new_window_does_not_inherit_cwd_file(isolated_home, monkeypatch):
    """Чужой `$IDVJPY_CWD_FILE` не уезжает в новое окно.

    Иначе его `on_unmount` перезапишет каталог родительской обёртки (кто вышел
    последним — тот и «победил»). Свой каталог окно отдаёт только своей обёртке.
    """
    monkeypatch.setenv("IDVJPY_CWD_FILE", str(isolated_home / "cwd.txt"))
    calls = _patch_open(monkeypatch)
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ":new")
        await pilot.pause()
        assert calls[0]["env"].get("IDVJPY_CWD_FILE") is None


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


def _touch_closed_session_files(isolated_home) -> None:
    """Остатки закрытых сессий: `.bashrc_term_*` и `history_*.txt`."""
    for name in ("history_s2.txt", "history_s3.txt", ".bashrc_term_s2", ".bashrc_term_s3"):
        (isolated_home / name).write_text("seq 1\n", encoding="utf-8")


async def test_new_window_auto_name_ignores_files_of_closed_sessions(isolated_home, monkeypatch):
    """Кнопка «New session» не считает файлы закрытых сессий занятыми именами.

    Раньше автоимя считалось по `history_*.txt` / `.bashrc_term_*`, поэтому
    каждое нажатие давало следующее `sN` (s2, s3, s4…), хотя работала одна
    сессия. Теперь источник — реестр `session_<имя>.pid`.
    """
    _touch_closed_session_files(isolated_home)
    calls = _patch_open(monkeypatch)
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ":new")
        await pilot.pause()
        assert _names(calls) == ["--instance-name=s2"]


async def test_new_window_two_presses_get_distinct_names(isolated_home, monkeypatch):
    """Два Ctrl+N подряд — разные имена: имя резервируется сразу при запуске."""
    calls = _patch_open(monkeypatch, pid=os.getpid())
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ":new")
        await submit(pilot, ":new")
        assert _names(calls) == ["--instance-name=s2", "--instance-name=s3"]


async def test_new_window_reuses_name_after_session_exits(isolated_home, monkeypatch):
    """Закрылась сессия `s2` — то же имя снова свободно."""
    calls = _patch_open(monkeypatch, pid=os.getpid())
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ":new")
        unregister(str(isolated_home), "s2")
        await submit(pilot, ":new")
        assert _names(calls) == ["--instance-name=s2", "--instance-name=s2"]


async def test_new_window_reserves_session_name(isolated_home, monkeypatch):
    """`:new NAME` сразу занимает имя в реестре (активная сессия)."""
    _patch_open(monkeypatch, pid=os.getpid())
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ":new mysess")
        assert os.path.exists(registry_path(str(isolated_home), "mysess"))
        assert "mysess" in active_sessions(str(isolated_home))


async def test_session_switch_moves_registration(isolated_home, monkeypatch):
    """`:session NAME` — та же копия приложения отвечает за другое имя."""
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        before = app.instance_name
        await submit(pilot, ":session alpha")
        assert app.instance_name == "alpha"
        assert os.path.exists(registry_path(str(isolated_home), "alpha"))
        assert not os.path.exists(registry_path(str(isolated_home), before))
