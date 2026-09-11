#!/usr/bin/env python3
"""Смоук TUI: запустить команду под настоящим pty и проверить результат.

В CI нет терминала, а Textual требует настоящий tty — поэтому создаём pty
сами, задаём размер окна и читаем всё, что приложение отрисовало.

Пример (внутри образа демостенда):

    tui-smoke.py --expect IDvjPy_term -- /usr/local/bin/idvjpy-demo --demo short --demo-quit

Выход: 0 — команда завершилась успешно, отрисовала ожидаемый текст и без
traceback; иначе 1 (и последние строки вывода печатаются для диагностики).
"""
from __future__ import annotations

import argparse
import fcntl
import os
import pty
import re
import select
import signal
import struct
import subprocess
import sys
import termios
import time

ROWS, COLS = 40, 120
TAIL_LINES = 40


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a command under a pty and check its output.")
    parser.add_argument("--expect", action="append", default=[], help="substring that must appear")
    parser.add_argument("--timeout", type=float, default=120.0, help="seconds before giving up")
    parser.add_argument("--dump", default="", help="write raw output to this file")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="-- <cmd> [args...]")
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("no command given (use `-- <cmd> [args...]`)")
    args.command = command
    return args


def _child_setup() -> None:
    """Сделать pty управляющим терминалом ребёнка (fd 0 уже смотрит на slave)."""
    os.setsid()
    fcntl.ioctl(0, termios.TIOCSCTTY, 0)


def _read_until_exit(master: int, proc: subprocess.Popen, deadline: float) -> bytes:
    captured = bytearray()
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
            raise TimeoutError("command did not finish within the timeout")
        ready, _, _ = select.select([master], [], [], min(remaining, 0.5))
        if not ready:
            if proc.poll() is not None:
                # Дочерний процесс вышел: дочитываем остаток из буфера pty.
                while True:
                    ready, _, _ = select.select([master], [], [], 0.2)
                    if not ready:
                        break
                    try:
                        chunk = os.read(master, 65536)
                    except OSError:
                        break
                    if not chunk:
                        break
                    captured += chunk
                return bytes(captured)
            continue
        try:
            chunk = os.read(master, 65536)
        except OSError:  # EIO: slave закрыт, данных больше нет
            return bytes(captured)
        if not chunk:
            return bytes(captured)
        captured += chunk


def _plain(text: bytes) -> str:
    """Грубо снять ANSI, оставив читаемые хвосты для диагностики."""
    no_csi = re.sub(rb"\x1b\[[0-9;?]*[a-zA-Z]", b"", text)
    no_osc = re.sub(rb"\x1b\][^\x07\x1b]*(\x07|\x1b\\)", b"", no_csi)
    return no_osc.decode("utf-8", errors="replace")


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", ROWS, COLS, 0, 0))
    env = {**os.environ, "TERM": os.environ.get("TERM", "xterm-256color")}
    proc = subprocess.Popen(
        args.command,
        stdin=slave,
        stdout=slave,
        stderr=slave,
        env=env,
        preexec_fn=_child_setup,
        close_fds=True,
    )
    os.close(slave)

    try:
        output = _read_until_exit(master, proc, time.monotonic() + args.timeout)
    except TimeoutError as exc:
        print(f"tui-smoke: {exc}", file=sys.stderr)
        return 1
    finally:
        os.close(master)
    code = proc.wait()

    if args.dump:
        with open(args.dump, "wb") as handle:
            handle.write(output)
    text = _plain(output)
    print(f"tui-smoke: exit={code}, {len(output)} bytes rendered, size={ROWS}x{COLS}")

    failed = False
    if code != 0:
        print(f"tui-smoke: command exited with {code}", file=sys.stderr)
        failed = True
    if "Traceback" in text:
        print("tui-smoke: traceback in the rendered output", file=sys.stderr)
        failed = True
    for needle in args.expect:
        if needle not in text:
            print(f"tui-smoke: expected {needle!r} in the output", file=sys.stderr)
            failed = True
    if failed:
        tail = "\n".join(text.splitlines()[-TAIL_LINES:])
        print(f"tui-smoke: last {TAIL_LINES} lines:\n{tail}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
