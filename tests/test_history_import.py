"""Импорт истории оболочки (`:h import`, src/history_import.py).

Юнит-часть — разбор форматов (zsh extended, bash timestamps, fish, PSReadLine),
поиск путей по ОС и запись пачкой в history_<instance>.txt; app-level — `:h import`
дописывает историю, уважает `$HISTFILE`/HOME и идемпотентен при повторе.
"""
from __future__ import annotations

import os

import history_import
from history_store import append_history_file_lines
from tests.conftest import last_info, submit

# --- разбор форматов --------------------------------------------------------

def test_parse_zsh_extended():
    text = ": 1700000000:0;git status\n: 1700000001:0;ls -la\n"
    assert history_import.parse_history(text, "zsh") == ["git status", "ls -la"]


def test_parse_zsh_plain_when_extended_is_off():
    assert history_import.parse_history("echo a\nls\n", "zsh") == ["echo a", "ls"]


def test_parse_zsh_multiline_folds_into_one_line():
    """zsh хранит многострочный ввод одной записью — в истории приложения одна строка."""
    text = ": 1700000000:0;echo one\necho two\n"
    assert history_import.parse_history(text, "zsh") == ["echo one ; echo two"]


def test_parse_bash_drops_timestamp_markers():
    text = "#1700000000\ngit status\n#1700000001\nls\n"
    assert history_import.parse_history(text, "bash") == ["git status", "ls"]


def test_parse_fish_cmd_lines_and_quotes():
    text = "- cmd: git status\n  when: 1700000000\n- cmd: 'echo \"hi\"'\n"
    assert history_import.parse_history(text, "fish") == ["git status", 'echo "hi"']


def test_parse_fish_escaped_newline_folds():
    assert history_import.parse_history("- cmd: printf a\\nb\n", "fish") == [
        "printf a ; b"
    ]


def test_parse_readline_is_plain():
    assert history_import.parse_history("Get-ChildItem\ncd C:\\\n", "pwsh") == [
        "Get-ChildItem",
        "cd C:\\",
    ]


def test_parse_skips_empty_lines():
    assert history_import.parse_history("\n  \nls\n\n", "sh") == ["ls"]


# --- пути по ОС -------------------------------------------------------------

def test_candidate_paths_linux():
    paths = {
        source.path: source.shell
        for source in history_import.candidate_sources(
            env={"HOME": "/home/u"}, platform="linux"
        )
    }
    assert paths["/home/u/.bash_history"] == "bash"
    assert paths["/home/u/.zsh_history"] == "zsh"
    assert paths["/home/u/.sh_history"] == "ksh"
    assert paths["/home/u/.local/share/fish/fish_history"] == "fish"


def test_candidate_paths_macos_uses_application_support():
    paths = {
        source.path
        for source in history_import.candidate_sources(
            env={"HOME": "/Users/u"}, platform="darwin"
        )
    }
    assert "/Users/u/Library/Application Support/fish/fish_history" in paths
    assert "/Users/u/.zsh_history" in paths


def test_candidate_paths_windows_uses_appdata():
    appdata = "C:\\Users\\u\\AppData\\Roaming"
    env = {"USERPROFILE": "C:\\Users\\u", "APPDATA": appdata}
    sources = history_import.candidate_sources(
        env=env, platform="win32", home="C:\\Users\\u"
    )
    consoles = {
        source.shell: source.path
        for source in sources
        if source.path.endswith("ConsoleHost_history.txt")
    }
    assert consoles == {
        "pwsh": os.path.join(
            appdata, "Microsoft", "PowerShell", "PSReadLine",
            "ConsoleHost_history.txt",
        ),
        "powershell": os.path.join(
            appdata, "Microsoft", "Windows", "PowerShell", "PSReadLine",
            "ConsoleHost_history.txt",
        ),
    }


def test_candidate_paths_respect_xdg_data_home():
    paths = {
        source.path
        for source in history_import.candidate_sources(
            env={"HOME": "/home/u", "XDG_DATA_HOME": "/data"}, platform="linux"
        )
    }
    assert "/data/fish/fish_history" in paths
    assert "/data/nushell/history.txt" in paths


def test_candidate_paths_pwsh_core_on_unix_uses_xdg():
    paths = {
        source.path
        for source in history_import.candidate_sources(
            env={"HOME": "/home/u", "XDG_DATA_HOME": "/data"}, platform="linux"
        )
    }
    assert "/data/powershell/PSReadLine/ConsoleHost_history.txt" in paths


def test_histfile_comes_first_and_defines_shell():
    sources = history_import.candidate_sources(
        env={"HOME": "/home/u", "HISTFILE": "/data/my_zsh_hist"}
    )
    assert sources[0].shell == "zsh"
    assert sources[0].path == "/data/my_zsh_hist"


def test_find_sources_keeps_existing_and_dedupes(tmp_path):
    hist = tmp_path / ".zsh_history"
    hist.write_text("ls\n", encoding="utf-8")
    sources = history_import.find_sources(
        env={"HOME": str(tmp_path), "HISTFILE": str(hist)}, platform="linux"
    )
    assert sources == [history_import.Source("zsh", str(hist))]


def test_find_sources_filters_by_shell(tmp_path):
    (tmp_path / ".bash_history").write_text("ls\n", encoding="utf-8")
    (tmp_path / ".zsh_history").write_text("ls\n", encoding="utf-8")
    shells = {
        source.shell
        for source in history_import.find_sources(
            "bash", env={"HOME": str(tmp_path)}, platform="linux"
        )
    }
    assert shells == {"bash"}


def test_read_sources_limits_to_the_tail(tmp_path):
    (tmp_path / ".bash_history").write_text(
        "".join(f"cmd{i}\n" for i in range(10)), encoding="utf-8"
    )
    results = history_import.read_sources(
        "bash", limit=3, env={"HOME": str(tmp_path)}, platform="linux"
    )
    assert len(results) == 1
    assert results[0].commands == ["cmd7", "cmd8", "cmd9"]


# --- запись пачкой ----------------------------------------------------------

def test_append_history_file_lines_skips_existing_and_empty(tmp_path):
    path = str(tmp_path / "history.txt")
    (tmp_path / "history.txt").write_text("old\n", encoding="utf-8")
    assert append_history_file_lines(path, ["old", "", "new", "new2"]) == 2
    assert (tmp_path / "history.txt").read_text(encoding="utf-8") == "old\nnew\nnew2\n"


def test_append_history_file_lines_creates_missing_file(tmp_path):
    path = str(tmp_path / "nope.txt")
    assert append_history_file_lines(path, ["a", "b"]) == 2
    assert (tmp_path / "nope.txt").read_text(encoding="utf-8") == "a\nb\n"


# --- `:h import` в TUI -------------------------------------------------------

def _isolate_history_env(monkeypatch, home) -> None:
    """Спрятать настоящий HOME: иначе импорт подхватит историю разработчика."""
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("XDG_DATA_HOME", str(home / "xdg"))
    monkeypatch.setenv("APPDATA", str(home / "appdata"))
    monkeypatch.delenv("HISTFILE", raising=False)


async def test_h_import_appends_shell_history(isolated_home, monkeypatch):
    from app import CommandRunner

    _isolate_history_env(monkeypatch, isolated_home)
    (isolated_home / ".bash_history").write_text(
        "#1700000000\necho imported-1\ngit status\n", encoding="utf-8"
    )
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":h import bash")
        text = last_info(app).text_content
        assert "bash 2" in text
        assert "2 new" in text
        saved = (isolated_home / "history_default.txt").read_text(encoding="utf-8")
        assert "echo imported-1" in saved
        assert "git status" in saved


async def test_h_import_is_idempotent(isolated_home, monkeypatch):
    from app import CommandRunner

    _isolate_history_env(monkeypatch, isolated_home)
    (isolated_home / ".bash_history").write_text("echo once\n", encoding="utf-8")
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":h import bash")
        await submit(pilot, ":h import bash")
        assert "0 new" in last_info(app).text_content


async def test_h_import_unknown_shell(isolated_home, monkeypatch):
    from app import CommandRunner

    _isolate_history_env(monkeypatch, isolated_home)
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":h import nope")
        assert "Unknown shell: nope" in last_info(app).text_content


async def test_h_import_reports_searched_paths(isolated_home, monkeypatch):
    from app import CommandRunner

    _isolate_history_env(monkeypatch, isolated_home)
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":h import")
        text = last_info(app).text_content
        assert "No shell history found" in text
        assert ".bash_history" in text
