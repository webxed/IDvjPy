"""Буфер обмена: CLIPBOARD, PRIMARY, Textual/OSC 52."""
from __future__ import annotations

import subprocess
from typing import Any, Optional

import pyperclip


def _linux_clipboard_cmd(selection: str, data: Optional[bytes] = None) -> Optional[bytes]:
    """Чтение/запись X11/Wayland буферов. selection: clipboard | primary."""
    writers_readers = []
    if selection == "primary":
        writers_readers = [
            (["xclip", "-selection", "primary"], ["xclip", "-selection", "primary", "-o"]),
            (["xsel", "--primary", "--input"], ["xsel", "--primary", "--output"]),
            (["wl-copy", "--primary"], ["wl-paste", "--primary", "-n"]),
        ]
    else:
        writers_readers = [
            (["xclip", "-selection", "clipboard"], ["xclip", "-selection", "clipboard", "-o"]),
            (["xsel", "--clipboard", "--input"], ["xsel", "--clipboard", "--output"]),
            (["wl-copy"], ["wl-paste", "-n"]),
        ]
    if data is not None:
        for write_cmd, _read_cmd in writers_readers:
            try:
                completed = subprocess.run(
                    write_cmd,
                    input=data,
                    capture_output=True,
                    timeout=0.4,
                    check=False,
                )
                if completed.returncode == 0:
                    return b""
            except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
                continue
        return None
    for _write_cmd, read_cmd in writers_readers:
        try:
            completed = subprocess.run(
                read_cmd,
                capture_output=True,
                timeout=0.4,
                check=False,
            )
            if completed.returncode == 0:
                return completed.stdout
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            continue
    return None


def copy_text_to_clipboards(text: str, app: Optional[Any] = None) -> None:
    """
    Копирует текст во все буферы, которые читает терминал:
    Textual (Ctrl+V в Input), OSC 52, CLIPBOARD и PRIMARY (Shift+Insert).
    """
    payload = text if text is not None else ""
    if app is not None:
        try:
            app.copy_to_clipboard(payload)
        except Exception:
            pass
        try:
            driver = getattr(app, "_driver", None)
            if driver is not None:
                import base64
                b64 = base64.b64encode(payload.encode("utf-8")).decode("ascii")
                driver.write(f"\x1b]52;p;{b64}\a")
        except Exception:
            pass
    try:
        pyperclip.copy(payload)
    except Exception:
        pass
    encoded = payload.encode("utf-8")
    _linux_clipboard_cmd("clipboard", encoded)
    _linux_clipboard_cmd("primary", encoded)


def paste_text_from_clipboards(app: Optional[Any] = None) -> str:
    """Сначала системный CLIPBOARD/PRIMARY, затем внутренний буфер Textual."""
    try:
        clip = pyperclip.paste() or ""
        if clip:
            return clip
    except Exception:
        pass
    for selection in ("clipboard", "primary"):
        raw = _linux_clipboard_cmd(selection)
        if raw:
            try:
                decoded = raw.decode("utf-8", errors="replace")
            except Exception:
                continue
            if decoded:
                return decoded
    if app is not None:
        return getattr(app, "clipboard", None) or ""
    return ""
