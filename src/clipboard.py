"""Буфер обмена: CLIPBOARD, PRIMARY, Textual/OSC 52.

Модуль разделён на две части по стоимости вызова:

* ``copy_internal`` — внутренний буфер Textual и OSC 52: дешёвые операции,
  их можно звать прямо из обработчика клавиш/мыши;
* ``copy_system`` / ``read_system`` — ``pyperclip`` и внешние программы
  (``xclip``/``xsel``/``wl-copy``/``wl-paste``) с таймаутом: блокирующие
  вызовы, которые приложение выполняет в фоновом потоке, чтобы не морозить
  event loop Textual.

Совместимые ``copy_text_to_clipboards`` / ``paste_text_from_clipboards``
остаются синхронными (обе части подряд) для не-UI вызовов и тестов.
"""
from __future__ import annotations

import subprocess
from typing import Any

import pyperclip


def _linux_clipboard_cmd(selection: str, data: bytes | None = None) -> bytes | None:
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


def copy_internal(text: str, app: Any | None = None) -> None:
    """Внутренний буфер Textual и OSC 52 — без subprocess, можно в event loop."""
    payload = text if text is not None else ""
    if app is None:
        return
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


def copy_system(text: str) -> None:
    """CLIPBOARD и PRIMARY через pyperclip и X11/Wayland-программы.

    Блокирует (subprocess с таймаутом) — вызывать вне event loop.
    """
    payload = text if text is not None else ""
    try:
        pyperclip.copy(payload)
    except Exception:
        pass
    encoded = payload.encode("utf-8")
    _linux_clipboard_cmd("clipboard", encoded)
    _linux_clipboard_cmd("primary", encoded)


def read_system() -> str:
    """Прочитать CLIPBOARD/PRIMARY. Блокирует — вызывать вне event loop."""
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
    return ""


def copy_text_to_clipboards(text: str, app: Any | None = None) -> None:
    """
    Копирует текст во все буферы, которые читает терминал:
    Textual (Ctrl+V в Input), OSC 52, CLIPBOARD и PRIMARY (Shift+Insert).

    Синхронная форма: и внутренний буфер, и системные backend-ы подряд. Для
    UI-обработчиков предпочтительнее ``copy_internal`` + фоновый ``copy_system``.
    """
    copy_internal(text, app)
    copy_system(text)


def paste_text_from_clipboards(app: Any | None = None) -> str:
    """Сначала системный CLIPBOARD/PRIMARY, затем внутренний буфер Textual.

    Синхронная форма: блокирует на системных backend-ах. Для UI-обработчиков
    предпочтительнее фоновый ``read_system`` с fallback на ``app.clipboard``.
    """
    text = read_system()
    if text:
        return text
    if app is not None:
        return getattr(app, "clipboard", None) or ""
    return ""
