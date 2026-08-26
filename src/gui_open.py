"""Open a file manager or system terminal in a new window (detached)."""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from typing import List, Mapping, Optional, Sequence, Tuple

LINUX_TERMINALS = (
    "xdg-terminal-exec",
    "gnome-terminal",
    "kgx",
    "konsole",
    "xfce4-terminal",
    "x-terminal-emulator",
    "xterm",
)

# subprocess flags exist on Windows; keep numeric fallbacks for tests on POSIX.
_CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
_CREATE_NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0x00000010)


class GuiOpenError(Exception):
    """User-facing error: missing binary, bad path, empty override."""


def _norm_platform(platform: Optional[str] = None) -> str:
    plat = sys.platform if platform is None else platform
    if plat.startswith("linux"):
        return "linux"
    if plat == "darwin":
        return "darwin"
    if plat.startswith("win"):
        return "win32"
    return "linux"


def _split_cmd(value: str, platform: str) -> List[str]:
    return shlex.split(value, posix=(platform != "win32"))


def _require_which(name: str, var: str) -> None:
    if shutil.which(name) is None:
        raise GuiOpenError(f"{name} not found; set ${var}=")


def resolve_target_dir(path_arg: Optional[str] = None) -> str:
    """Absolute directory for :fm / :term. ``~`` is expanded."""
    if not path_arg:
        return os.getcwd()
    target = os.path.abspath(os.path.expanduser(path_arg))
    if not os.path.isdir(target):
        raise GuiOpenError(f"{path_arg}: not a directory")
    return target


def build_fileman_argv(
    target: str,
    environ: Mapping[str, str],
    *,
    platform: Optional[str] = None,
) -> List[str]:
    """Argv that opens a file manager at ``target``. Path is always appended."""
    plat = _norm_platform(platform)
    override = (environ.get("FILEMAN") or "").strip()
    if override:
        argv = _split_cmd(override, plat)
        if not argv:
            raise GuiOpenError("set $FILEMAN=")
        _require_which(argv[0], "FILEMAN")
        return argv + [target]
    if plat == "darwin":
        _require_which("open", "FILEMAN")
        return ["open", target]
    if plat == "win32":
        _require_which("explorer", "FILEMAN")
        return ["explorer", target]
    _require_which("xdg-open", "FILEMAN")
    return ["xdg-open", target]


def build_term_argv(
    target: str,
    environ: Mapping[str, str],
    *,
    platform: Optional[str] = None,
) -> List[str]:
    """Argv for a system terminal. Working directory is ``Popen(cwd=target)``."""
    plat = _norm_platform(platform)
    override = (environ.get("TERMINAL") or "").strip()
    if override:
        argv = _split_cmd(override, plat)
        if not argv:
            raise GuiOpenError("set $TERMINAL=")
        _require_which(argv[0], "TERMINAL")
        return argv
    if plat == "darwin":
        _require_which("open", "TERMINAL")
        return ["open", "-a", "Terminal", target]
    if plat == "win32":
        if shutil.which("wt") is not None:
            return ["wt", "-d", target]
        if shutil.which("cmd.exe") is not None or shutil.which("cmd") is not None:
            exe = "cmd.exe" if shutil.which("cmd.exe") is not None else "cmd"
            return [exe, "/c", "start", exe, "/k"]
        raise GuiOpenError("set $TERMINAL=")
    for name in LINUX_TERMINALS:
        if shutil.which(name) is not None:
            return [name]
    raise GuiOpenError("set $TERMINAL=")


def spawn_detached(
    argv: Sequence[str],
    *,
    cwd: str,
    env: Mapping[str, str],
    new_console: bool = False,
    platform: Optional[str] = None,
) -> subprocess.Popen:
    """Start a GUI/terminal without waiting or stealing this TTY."""
    plat = _norm_platform(platform)
    kwargs = {
        "cwd": cwd,
        "env": dict(env),
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if plat == "win32":
        flags = _CREATE_NEW_PROCESS_GROUP
        if new_console:
            flags |= _CREATE_NEW_CONSOLE
        kwargs["creationflags"] = flags
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(list(argv), **kwargs)


def format_opened(argv: Sequence[str], pid: int) -> str:
    return f"Opened: {shlex.join(list(argv))}  pid {pid}"


def open_file_manager(
    path_arg: Optional[str],
    environ: Mapping[str, str],
    *,
    platform: Optional[str] = None,
) -> Tuple[List[str], subprocess.Popen]:
    target = resolve_target_dir(path_arg)
    argv = build_fileman_argv(target, environ, platform=platform)
    proc = spawn_detached(argv, cwd=target, env=environ, new_console=False, platform=platform)
    return argv, proc


def open_terminal(
    path_arg: Optional[str],
    environ: Mapping[str, str],
    *,
    platform: Optional[str] = None,
) -> Tuple[List[str], subprocess.Popen]:
    target = resolve_target_dir(path_arg)
    argv = build_term_argv(target, environ, platform=platform)
    proc = spawn_detached(argv, cwd=target, env=environ, new_console=True, platform=platform)
    return argv, proc
