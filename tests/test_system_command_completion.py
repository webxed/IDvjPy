"""Автодополнение системных команд из $PATH (фича system-command-completion).

Без реального $PATH: каталоги подставляются через параметр ``path_env``, поэтому
тесты детерминированы. Проверяем скан (execute-bit, дедуп, обрезку, префикс),
кэш и гейтинг флагом ``system_command_completion`` в TUI.
"""
import os

import pytest

pytestmark = pytest.mark.slow

import system_complete
from system_complete import (
    cached_system_command_candidates,
    clear_cache,
    system_command_candidates,
)
from tests.conftest import input_widget, type_keys


def _make_exec(directory, name):
    """Создать исполняемый файл (POSIX execute-bit)."""
    path = directory / name
    path.write_text("#!/bin/sh\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def test_scans_executables_and_filters_by_prefix(tmp_path):
    clear_cache()
    bin1 = tmp_path / "bin1"
    bin1.mkdir()
    _make_exec(bin1, "git")
    _make_exec(bin1, "gitui")
    _make_exec(bin1, "ls")
    (bin1 / "notes.txt").write_text("x", encoding="utf-8")
    plain = bin1 / "plain"
    plain.write_text("x", encoding="utf-8")
    plain.chmod(0o644)  # без execute-bit — не команда

    path_env = str(bin1)
    assert system_command_candidates("gi", path_env=path_env) == ["git", "gitui"]
    assert system_command_candidates("", path_env=path_env) == ["git", "gitui", "ls"]
    # Точное имя модуль тоже возвращает — фильтр точного совпадения живёт в app.
    assert system_command_candidates("ls", path_env=path_env) == ["ls"]


def test_empty_path_component_means_current_directory(tmp_path, monkeypatch):
    clear_cache()
    _make_exec(tmp_path, "from_cwd")
    monkeypatch.chdir(tmp_path)
    assert system_command_candidates("from_", path_env=os.pathsep) == ["from_cwd"]


def test_dedupes_across_dirs(tmp_path):
    clear_cache()
    first = tmp_path / "a"
    second = tmp_path / "b"
    first.mkdir()
    second.mkdir()
    _make_exec(first, "dup")
    _make_exec(second, "dup")
    _make_exec(second, "other")
    path_env = os.pathsep.join([str(first), str(second)])
    assert system_command_candidates("", path_env=path_env) == ["dup", "other"]


def test_limit_caps_results(tmp_path):
    clear_cache()
    bin1 = tmp_path / "bin"
    bin1.mkdir()
    for i in range(25):
        _make_exec(bin1, f"cmd{i:02d}")
    path_env = str(bin1)
    assert len(system_command_candidates("cmd", path_env=path_env, limit=5)) == 5
    assert system_command_candidates("cmd", path_env=path_env, limit=0) == []


def test_missing_dir_is_ignored(tmp_path):
    clear_cache()
    bin1 = tmp_path / "bin"
    bin1.mkdir()
    _make_exec(bin1, "tool")
    path_env = os.pathsep.join([str(tmp_path / "nope"), str(bin1)])
    assert system_command_candidates("to", path_env=path_env) == ["tool"]


def test_cache_can_be_cleared(tmp_path):
    clear_cache()
    bin1 = tmp_path / "bin"
    bin1.mkdir()
    _make_exec(bin1, "git")
    path_env = str(bin1)
    assert system_command_candidates("gi", path_env=path_env) == ["git"]
    _make_exec(bin1, "gitui")
    # До очистки остаётся снимок, после — новый каталог сканируется заново.
    assert system_command_candidates("gi", path_env=path_env) == ["git"]
    clear_cache()
    assert system_command_candidates("gi", path_env=path_env) == ["git", "gitui"]


def test_cached_candidates_never_scan_on_cache_miss(tmp_path, monkeypatch):
    clear_cache()
    path_env = str(tmp_path / "bin")

    def forbidden_scan(_path_env):
        raise AssertionError("UI must not scan PATH")

    monkeypatch.setattr(system_complete, "_scan", forbidden_scan)
    assert cached_system_command_candidates("gi", path_env=path_env) is None


def test_windows_matching_and_dedupe_are_case_insensitive(tmp_path, monkeypatch):
    clear_cache()
    bin1 = tmp_path / "bin"
    bin1.mkdir()
    _make_exec(bin1, "Git.EXE")
    _make_exec(bin1, "git.CMD")
    monkeypatch.setattr(system_complete.os, "name", "nt")
    monkeypatch.setenv("PATHEXT", ".EXE;.CMD")
    names = system_command_candidates("GI", path_env=str(bin1))
    assert [name.casefold() for name in names] == ["git"]


def _fake_cached_candidates(prefix="", **kwargs):
    """Готовый снимок $PATH для TUI-тестов, без файлового I/O."""
    names = ["git", "gitui", "grep", "ls"]
    return [name for name in names if name.startswith(prefix)][:20]


async def test_enabled_offers_commands_only_at_command_position(isolated_home, monkeypatch):
    import app as app_module

    (isolated_home / "settings.yml").write_text(
        "system_command_completion: true\n"
        "check_updates: false\n"
        "command_timeout: 5\n"
        "screensaver_idle: 0\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        app_module, "cached_system_command_candidates", _fake_cached_candidates
    )
    app = app_module.CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert app.system_command_completion is True
        assert app.get_completion_candidates("gi") == ["git", "gitui"]
        # Аргумент/путь/`:`/`!` и хвостовой пробел — не позиция имени команды.
        assert app.get_completion_candidates("cat gi") == []
        assert app.get_completion_candidates("ls -la gi") == []
        assert app.get_completion_candidates("gi ") == []
        assert app.get_completion_candidates(":gi") == []
        assert app.get_completion_candidates("./gi") == []
        # Точное имя уже набрано — себя же не подсказываем, но более длинные
        # совпадения остаются (`git` → `gitui`, без самого `git`).
        assert app.get_completion_candidates("git") == ["gitui"]


async def test_disabled_by_flag(isolated_home, monkeypatch):
    import app as app_module

    # isolated_home по умолчанию пишет system_command_completion: false.
    monkeypatch.setattr(
        app_module, "cached_system_command_candidates", _fake_cached_candidates
    )
    app = app_module.CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert app.system_command_completion is False
        assert app.get_completion_candidates("gi") == []


async def test_hint_list_shows_system_commands(isolated_home, monkeypatch):
    import app as app_module

    (isolated_home / "settings.yml").write_text(
        "system_command_completion: true\n"
        "check_updates: false\n"
        "command_timeout: 5\n"
        "screensaver_idle: 0\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        app_module, "cached_system_command_candidates", _fake_cached_candidates
    )
    app = app_module.CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await type_keys(pilot, "gi")
        await pilot.pause()
        clist = app._completion_list
        assert clist.is_visible()
        assert "git" in clist.all_candidates
        # Tab подставляет команду и оставляет пробел под аргументы.
        await pilot.press("tab")
        await pilot.pause()
        assert input_widget(app).value == "git "
