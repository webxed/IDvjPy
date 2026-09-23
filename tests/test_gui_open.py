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
    normalize_term_mode,
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


# --- Режим вкладки (term_open: tab) ---------------------------------------


def test_normalize_term_mode_falls_back_to_window():
    assert normalize_term_mode("tab") == "tab"
    assert normalize_term_mode(" TAB ") == "tab"
    assert normalize_term_mode("nope") == "window"
    assert normalize_term_mode(None) == "window"


def test_term_tab_uses_gnome_terminal_flag(monkeypatch):
    _which_only({"gnome-terminal"}, monkeypatch)
    argv = build_term_argv("/tmp", {}, platform="linux", mode="tab")
    assert argv == ["gnome-terminal", "--tab"]
    # По умолчанию — окно, без флага.
    assert build_term_argv("/tmp", {}, platform="linux") == ["gnome-terminal"]


def test_term_tab_skips_terminals_without_tabs(monkeypatch):
    """xterm вкладок не умеет — в режиме tab берём konsole, хотя xterm тоже есть."""
    _which_only({"xterm", "konsole"}, monkeypatch)
    argv = build_term_argv("/tmp", {}, platform="linux", mode="tab")
    assert argv == ["konsole", "--new-tab"]
    # А в режиме окна остаётся первый доступный по списку.
    assert build_term_argv("/tmp", {}, platform="linux") == ["konsole"]


def test_term_tab_without_capable_terminal_is_an_error(monkeypatch):
    _which_only({"xterm"}, monkeypatch)
    with pytest.raises(GuiOpenError, match="no terminal with tab support"):
        build_term_argv("/tmp", {}, platform="linux", mode="tab")


def test_term_tab_override_gets_the_flag_inserted(monkeypatch):
    _which_only({"gnome-terminal"}, monkeypatch)
    argv = build_term_argv("/tmp", {"TERMINAL": "gnome-terminal --wait"},
                           platform="linux", mode="tab")
    assert argv == ["gnome-terminal", "--tab", "--wait"]


def test_term_tab_override_without_tabs_is_an_error(monkeypatch):
    """alacritty вкладок не умеет вообще — явная ошибка, а не окно молча."""
    _which_only({"alacritty"}, monkeypatch)
    with pytest.raises(GuiOpenError, match="alacritty: new tab is not supported"):
        build_term_argv("/tmp", {"TERMINAL": "alacritty -e"}, platform="linux", mode="tab")


def test_exec_tab_gnome_and_konsole(monkeypatch):
    _which_only({"gnome-terminal"}, monkeypatch)
    assert build_terminal_exec_argv(
        ["htop"], {}, platform="linux", mode="tab"
    ) == ["gnome-terminal", "--tab", "--", "htop"]

    _which_only({"konsole"}, monkeypatch)
    assert build_terminal_exec_argv(
        ["htop"], {}, platform="linux", mode="tab"
    ) == ["konsole", "--new-tab", "-e", "htop"]


def test_exec_tab_override_with_flag(monkeypatch):
    """`$TERMINAL` используется как есть: флаг запуска (`-e`/`-x`) — в самом `$TERMINAL`,
    к нему только дописывается флаг вкладки."""
    _which_only({"xfce4-terminal"}, monkeypatch)
    argv = build_terminal_exec_argv(
        ["htop"], {"TERMINAL": "xfce4-terminal -x"}, platform="linux", mode="tab"
    )
    assert argv == ["xfce4-terminal", "--tab", "-x", "htop"]


def test_term_tab_win32_needs_windows_terminal(monkeypatch):
    _which_only({"wt"}, monkeypatch)
    argv = build_term_argv(r"C:\tmp", {}, platform="win32", mode="tab")
    assert argv == ["wt", "-w", "0", "nt", "-d", r"C:\tmp"]
    assert build_terminal_exec_argv(
        ["htop"], {}, platform="win32", mode="tab"
    ) == ["wt", "-w", "0", "nt", "htop"]
    _which_only(set(), monkeypatch)
    with pytest.raises(GuiOpenError, match="needs Windows Terminal"):
        build_term_argv(r"C:\tmp", {}, platform="win32", mode="tab")


def test_term_tab_darwin_is_explicit(monkeypatch):
    _which_only({"open"}, monkeypatch)
    with pytest.raises(GuiOpenError, match="new tab is not supported"):
        build_term_argv("/tmp", {}, platform="darwin", mode="tab")
