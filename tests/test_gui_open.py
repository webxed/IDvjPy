"""OS defaults and $FILEMAN / $TERMINAL overrides for :fm / :term."""
import subprocess

import pytest

from gui_open import (
    LINUX_TERMINALS,
    GuiOpenError,
    build_fileman_argv,
    build_term_argv,
    build_terminal_exec_argv,
    format_opened,
    resolve_target_dir,
    spawn_detached,
)


def _which_only(present, monkeypatch):
    names = set(present)

    def fake_which(name):
        return f"/bin/{name}" if name in names else None

    monkeypatch.setattr("gui_open.shutil.which", fake_which)


def test_resolve_target_dir_cwd_and_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert resolve_target_dir(None) == str(tmp_path)
    sub = tmp_path / "inner"
    sub.mkdir()
    assert resolve_target_dir("inner") == str(sub.resolve())
    with pytest.raises(GuiOpenError, match="not a directory"):
        resolve_target_dir("no-such-dir")


def test_fileman_linux_xdg_open(monkeypatch, tmp_path):
    _which_only({"xdg-open"}, monkeypatch)
    target = str(tmp_path)
    assert build_fileman_argv(target, {}, platform="linux") == ["xdg-open", target]


def test_fileman_darwin_open(monkeypatch, tmp_path):
    _which_only({"open"}, monkeypatch)
    target = str(tmp_path)
    assert build_fileman_argv(target, {}, platform="darwin") == ["open", target]


def test_fileman_win32_explorer(monkeypatch, tmp_path):
    _which_only({"explorer"}, monkeypatch)
    target = str(tmp_path)
    assert build_fileman_argv(target, {}, platform="win32") == ["explorer", target]


def test_fileman_override_beats_os(monkeypatch, tmp_path):
    _which_only({"nautilus", "xdg-open"}, monkeypatch)
    target = str(tmp_path)
    argv = build_fileman_argv(target, {"FILEMAN": "nautilus"}, platform="linux")
    assert argv == ["nautilus", target]


def test_fileman_override_with_args(monkeypatch, tmp_path):
    _which_only({"open"}, monkeypatch)
    target = str(tmp_path)
    argv = build_fileman_argv(
        target, {"FILEMAN": "open -a ForkLift"}, platform="darwin"
    )
    assert argv == ["open", "-a", "ForkLift", target]


def test_fileman_missing_xdg_open(monkeypatch, tmp_path):
    _which_only(set(), monkeypatch)
    with pytest.raises(GuiOpenError, match=r"xdg-open not found; set \$FILEMAN="):
        build_fileman_argv(str(tmp_path), {}, platform="linux")


def test_fileman_override_missing_binary(monkeypatch, tmp_path):
    _which_only(set(), monkeypatch)
    with pytest.raises(GuiOpenError, match=r"nautilus not found; set \$FILEMAN="):
        build_fileman_argv(str(tmp_path), {"FILEMAN": "nautilus"}, platform="linux")


def test_term_linux_first_which(monkeypatch, tmp_path):
    _which_only({"kgx", "xterm"}, monkeypatch)
    argv = build_term_argv(str(tmp_path), {}, platform="linux")
    assert argv == ["kgx"]
    assert argv[0] in LINUX_TERMINALS


def test_term_linux_none(monkeypatch, tmp_path):
    _which_only(set(), monkeypatch)
    with pytest.raises(GuiOpenError, match=r"set \$TERMINAL="):
        build_term_argv(str(tmp_path), {}, platform="linux")


def test_term_darwin_terminal_app(monkeypatch, tmp_path):
    _which_only({"open"}, monkeypatch)
    target = str(tmp_path)
    assert build_term_argv(target, {}, platform="darwin") == [
        "open",
        "-a",
        "Terminal",
        target,
    ]


def test_term_win32_wt(monkeypatch, tmp_path):
    _which_only({"wt", "cmd.exe"}, monkeypatch)
    target = str(tmp_path)
    assert build_term_argv(target, {}, platform="win32") == ["wt", "-d", target]


def test_term_win32_cmd_fallback(monkeypatch, tmp_path):
    _which_only({"cmd.exe"}, monkeypatch)
    argv = build_term_argv(str(tmp_path), {}, platform="win32")
    assert argv == ["cmd.exe", "/c", "start", "cmd.exe", "/k"]


def test_term_override_does_not_append_path(monkeypatch, tmp_path):
    _which_only({"kitty"}, monkeypatch)
    argv = build_term_argv(str(tmp_path), {"TERMINAL": "kitty"}, platform="linux")
    assert argv == ["kitty"]


def test_term_override_missing_binary(monkeypatch, tmp_path):
    _which_only(set(), monkeypatch)
    with pytest.raises(GuiOpenError, match=r"kitty not found; set \$TERMINAL="):
        build_term_argv(str(tmp_path), {"TERMINAL": "kitty"}, platform="linux")


def test_format_opened_pid():
    text = format_opened(["xdg-open", "/home/foo"], 12345)
    assert text.startswith("Opened: ")
    assert "xdg-open" in text
    assert "/home/foo" in text
    assert "pid 12345" in text


def test_spawn_detached_posix(monkeypatch, tmp_path):
    captured = {}

    class FakeProc:
        pid = 7

    def fake_popen(argv, **kwargs):
        captured["argv"] = argv
        captured["kwargs"] = kwargs
        return FakeProc()

    monkeypatch.setattr("gui_open.subprocess.Popen", fake_popen)
    proc = spawn_detached(
        ["xdg-open", str(tmp_path)],
        cwd=str(tmp_path),
        env={"DISPLAY": ":0"},
        platform="linux",
    )
    assert proc.pid == 7
    assert captured["kwargs"]["start_new_session"] is True
    assert captured["kwargs"]["cwd"] == str(tmp_path)
    assert captured["kwargs"]["stdin"] is subprocess.DEVNULL
    assert captured["kwargs"]["env"]["DISPLAY"] == ":0"
    assert "creationflags" not in captured["kwargs"]


def test_spawn_detached_win32_term_console(monkeypatch, tmp_path):
    captured = {}

    class FakeProc:
        pid = 9

    def fake_popen(argv, **kwargs):
        captured["argv"] = argv
        captured["kwargs"] = kwargs
        return FakeProc()

    monkeypatch.setattr("gui_open.subprocess.Popen", fake_popen)
    spawn_detached(
        ["wt", "-d", str(tmp_path)],
        cwd=str(tmp_path),
        env={},
        new_console=True,
        platform="win32",
    )
    flags = captured["kwargs"]["creationflags"]
    assert flags & getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
    assert flags & getattr(subprocess, "CREATE_NEW_CONSOLE", 0x00000010)
    assert "start_new_session" not in captured["kwargs"]


def test_resolve_expands_user(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    nested = tmp_path / "docs"
    nested.mkdir()
    monkeypatch.chdir(tmp_path)
    assert resolve_target_dir("~/docs") == str(nested.resolve())


def test_exec_linux_known_terminal_prefix(monkeypatch):
    _which_only({"kgx", "xterm"}, monkeypatch)
    argv = build_terminal_exec_argv(["python3", "app.py"], {}, platform="linux")
    assert argv == ["kgx", "--", "python3", "app.py"]


def test_exec_linux_xterm_dash_e(monkeypatch):
    _which_only({"xterm"}, monkeypatch)
    assert build_terminal_exec_argv(["app"], {}, platform="linux") == [
        "xterm",
        "-e",
        "app",
    ]


def test_exec_override_appended_as_is(monkeypatch):
    _which_only({"kitty"}, monkeypatch)
    argv = build_terminal_exec_argv(["app"], {"TERMINAL": "kitty"}, platform="linux")
    assert argv == ["kitty", "app"]


def test_exec_override_with_flag(monkeypatch):
    _which_only({"alacritty"}, monkeypatch)
    argv = build_terminal_exec_argv(
        ["app"], {"TERMINAL": "alacritty -e"}, platform="linux"
    )
    assert argv == ["alacritty", "-e", "app"]


def test_exec_linux_none(monkeypatch):
    _which_only(set(), monkeypatch)
    with pytest.raises(GuiOpenError, match=r"set \$TERMINAL="):
        build_terminal_exec_argv(["app"], {}, platform="linux")


def test_exec_darwin_requires_terminal(monkeypatch):
    _which_only({"open"}, monkeypatch)
    with pytest.raises(GuiOpenError, match=r"set \$TERMINAL="):
        build_terminal_exec_argv(["app"], {}, platform="darwin")


def test_exec_empty_command():
    with pytest.raises(GuiOpenError, match="empty command"):
        build_terminal_exec_argv([], {}, platform="linux")
