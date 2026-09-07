"""Потокобезопасный файл истории `history_<instance>.txt`.

Запись/чтение хвоста под portalocker-локом и компактирование старого
префикса. Вынесено из src/app.py; CommandRunner импортирует эти функции.
"""
from __future__ import annotations

import os
import time

import portalocker


class FileLockTimeoutError(Exception):
    """Raised when file lock cannot be acquired within timeout."""
    pass


def acquire_file_lock(file_obj, timeout_sec: int = 5, *, shared: bool = False) -> None:
    """
    Acquire lock on file with timeout (cross-platform).

    Uses portalocker for cross-platform file locking support:
    - Linux/Unix: fcntl.flock()
    - Windows: msvcrt.locking() or Win32 file locking

    Args:
        file_obj: Open file object (must be opened in a mode that allows locking)
        timeout_sec: Maximum time to wait for lock (default: 5 seconds). 0 = one try.
        shared: True for a shared read lock (several readers, blocks writers).

    Raises:
        FileLockTimeoutError: If lock cannot be acquired within timeout
        IOError: If locking operation fails
    """
    flags = portalocker.LOCK_SH if shared else portalocker.LOCK_EX
    flags |= portalocker.LOCK_NB
    start_time = time.time()

    while True:
        try:
            portalocker.lock(file_obj, flags)
            return
        except portalocker.exceptions.LockException:
            elapsed = time.time() - start_time
            if elapsed >= timeout_sec:
                raise FileLockTimeoutError(
                    f"Could not acquire file lock after {timeout_sec} seconds"
                ) from None
            time.sleep(0.1)
        except Exception as e:
            raise OSError(f"Failed to acquire file lock: {e}") from None


def release_file_lock(file_obj) -> None:
    """
    Release exclusive lock on file (cross-platform).

    Args:
        file_obj: Open file object
    """
    try:
        portalocker.unlock(file_obj)
    except Exception:
        pass  # Lock was already released or file was closed


def _stat_key_from_stat(st) -> tuple[int, int]:
    """Ключ кэша history.txt: mtime_ns + size (видно записи других процессов)."""
    mtime_ns = getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000))
    return (int(mtime_ns), int(st.st_size))


def history_file_stat_key(path: str) -> tuple[int, int] | None:
    try:
        return _stat_key_from_stat(os.stat(path))
    except OSError:
        return None


def _read_last_history_line(file_obj, encoding: str, tail: int = 8192) -> str | None:
    """Последняя непустая строка; file_obj открыт в бинарном режиме."""
    file_obj.seek(0, os.SEEK_END)
    size = file_obj.tell()
    if size <= 0:
        return None
    file_obj.seek(max(0, size - tail), os.SEEK_SET)
    data = file_obj.read()
    text = data.decode(encoding, errors="replace")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return lines[-1] if lines else None


def read_history_file_lines(
    path: str,
    encoding: str = "utf-8",
) -> tuple[list[str], tuple[int, int] | None]:
    """
    Читает history.txt. Shared-lock, если свободен; иначе читает без lock,
    чтобы подсказки не ждали писателя.
    """
    try:
        f = open(path, encoding=encoding)
    except FileNotFoundError:
        return [], None
    except OSError:
        return [], None
    with f:
        locked = False
        try:
            acquire_file_lock(f, timeout_sec=0, shared=True)
            locked = True
        except (OSError, FileLockTimeoutError):
            locked = False
        try:
            lines = [line.strip() for line in f if line.strip()]
            key = _stat_key_from_stat(os.fstat(f.fileno()))
            return lines, key
        finally:
            if locked:
                release_file_lock(f)


def append_history_file_line(
    path: str,
    command: str,
    encoding: str = "utf-8",
    lock_timeout: int = 5,
) -> bool:
    """
    Дописывает команду в history.txt, если она не совпадает с последней строкой.

    Проверка последней строки и запись — под одним exclusive flock,
    чтобы несколько экземпляров не гонялись за хвостом файла.
    """
    command = (command or "").strip()
    if not command:
        return False
    try:
        with open(path, "ab+") as f:
            locked = False
            try:
                acquire_file_lock(f, lock_timeout)
                locked = True
            except FileLockTimeoutError:
                locked = False
            try:
                last = _read_last_history_line(f, encoding)
                if last == command:
                    return False
                f.seek(0, os.SEEK_END)
                f.write(f"{command}\n".encode(encoding))
                f.flush()
                return True
            finally:
                if locked:
                    release_file_lock(f)
    except OSError:
        return False


DEFAULT_HISTORY_KEEP = 500
HISTORY_COMPACT_HYSTERESIS = 2


def compact_history_lines(lines: list[str], keep: int) -> list[str]:
    """Unique the old prefix; keep the last ``keep`` lines verbatim.

    In the prefix, last occurrence wins. A line that already appears in the
    recent tail is dropped from the prefix so Up/Down does not repeat it.
    ``keep <= 0`` leaves the list unchanged (compaction disabled).
    """
    cleaned = [str(line).strip() for line in lines if str(line).strip()]
    if keep <= 0 or len(cleaned) <= keep:
        return cleaned
    tail = cleaned[-keep:]
    prefix = cleaned[:-keep]
    in_tail = set(tail)
    seen = set()
    kept_rev: list[str] = []
    for line in reversed(prefix):
        if line in in_tail or line in seen:
            continue
        seen.add(line)
        kept_rev.append(line)
    return list(reversed(kept_rev)) + tail


def compact_history_file(
    path: str,
    keep: int,
    encoding: str = "utf-8",
    lock_timeout: int = 5,
    *,
    force: bool = False,
    hysteresis: int = HISTORY_COMPACT_HYSTERESIS,
) -> tuple[int, int, bool]:
    """Rewrite history.txt under an exclusive lock.

    Auto mode (``force=False``) runs only when ``len(lines) > keep * hysteresis``.
    Returns ``(before, after, changed)``. On lock/IO failure: ``(0, 0, False)``.
    """
    try:
        f = open(path, "r+", encoding=encoding)
    except FileNotFoundError:
        return 0, 0, False
    except OSError:
        return 0, 0, False
    with f:
        locked = False
        try:
            acquire_file_lock(f, lock_timeout)
            locked = True
        except (OSError, FileLockTimeoutError):
            return 0, 0, False
        try:
            lines = [line.strip() for line in f if line.strip()]
            before = len(lines)
            if keep <= 0:
                return before, before, False
            if not force and before <= keep * max(1, int(hysteresis)):
                return before, before, False
            compacted = compact_history_lines(lines, keep)
            after = len(compacted)
            if compacted == lines:
                return before, after, False
            f.seek(0)
            f.truncate()
            f.write("".join(f"{line}\n" for line in compacted))
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
            return before, after, True
        finally:
            if locked:
                release_file_lock(f)
