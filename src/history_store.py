"""Потокобезопасный файл истории `history_<instance>.txt`.

Запись/чтение хвоста под portalocker-локом и компактирование старого
префикса. Вынесено из src/app.py; CommandRunner импортирует эти функции.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass

import portalocker


class FileLockTimeoutError(Exception):
    """Возбуждается, когда блокировку файла не удаётся взять за отведённое время."""
    pass


def acquire_file_lock(file_obj, timeout_sec: int = 5, *, shared: bool = False) -> None:
    """
    Взять блокировку файла с таймаутом (кроссплатформенно).

    Использует portalocker для кроссплатформенной блокировки файлов:
    - Linux/Unix: fcntl.flock()
    - Windows: msvcrt.locking() или блокировка файлов Win32

    Аргументы:
        file_obj: открытый файловый объект (должен быть открыт в режиме, допускающем блокировку)
        timeout_sec: максимум ожидания блокировки в секундах (по умолчанию 5). 0 = одна попытка.
        shared: True для разделяемой блокировки чтения (несколько читателей, блокирует писателей).

    Исключения:
        FileLockTimeoutError: блокировку не удалось взять за таймаут
        IOError: сбой операции блокировки
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
    Снять эксклюзивную блокировку файла (кроссплатформенно).

    Аргументы:
        file_obj: открытый файловый объект
    """
    try:
        portalocker.unlock(file_obj)
    except Exception:
        pass  # Блокировка уже снята или файл закрыт


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
                return False
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


@dataclass(frozen=True)
class AppendResult:
    """Итог батч-дописи: сколько строк добавлено и что помешало (если помешало)."""

    added: int = 0
    error: str = ""


def append_history_file_lines(
    path: str,
    commands: list[str] | tuple[str, ...],
    encoding: str = "utf-8",
    lock_timeout: int = 5,
) -> AppendResult:
    """Дописать пачку команд одним exclusive flock; вернуть число добавленных.

    Импорт чужой истории — это хвост из тысяч строк: блокировку берём **один раз**
    (а не как `append_history_file_line` на каждую строку). Пустые строки и строки,
    которые уже есть в файле, не пишутся — повторный импорт того же файла ничего не
    добавит (порядок уже имеющихся строк не меняется).

    Неудача возвращается явно (`AppendResult.error`): без блокировки пачку не пишем
    (иначе разъедется проверка дублей в двух сессиях), а ошибка записи не должна
    выглядеть как «0 новых строк».
    """
    try:
        with open(path, "ab+") as f:
            try:
                acquire_file_lock(f, lock_timeout)
            except FileLockTimeoutError as exc:
                return AppendResult(0, f"history file is locked ({exc})")
            try:
                f.seek(0)
                data = f.read().decode(encoding, errors="replace")
                existing = {line.strip() for line in data.splitlines() if line.strip()}
                added = 0
                for raw in commands:
                    command = (raw or "").strip()
                    if not command or command in existing:
                        continue
                    f.write(f"{command}\n".encode(encoding))
                    existing.add(command)
                    added += 1
                if added:
                    f.flush()
                return AppendResult(added)
            finally:
                release_file_lock(f)
    except OSError as exc:
        return AppendResult(0, str(exc))


def remove_history_file_line(
    path: str,
    command: str,
    encoding: str = "utf-8",
    lock_timeout: int = 5,
) -> bool:
    """
    Удаляет последнее вхождение строки из history-файла (откат опечаток).

    Используется, когда команда упала с `command not found` — такая строка
    не должна оставаться в истории для повтора по ↑. Перезапись под
    exclusive flock, как append/compact.
    """
    target = (command or "").strip()
    if not target:
        return False
    try:
        with open(path, "r+", encoding=encoding) as f:
            locked = False
            try:
                acquire_file_lock(f, lock_timeout)
                locked = True
            except FileLockTimeoutError:
                return False
            try:
                lines = [line.rstrip("\n") for line in f]
                index = -1
                for i in range(len(lines) - 1, -1, -1):
                    if lines[i].strip() == target:
                        index = i
                        break
                if index < 0:
                    return False
                del lines[index]
                f.seek(0)
                f.truncate()
                if lines:
                    f.write("\n".join(lines) + "\n")
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
    """Уникализировать старый префикс; последние ``keep`` строк сохранить как есть.

    В префиксе побеждает последнее вхождение. Строка, которая уже есть в
    недавнем хвосте, убирается из префикса, чтобы ↑/↓ её не повторял.
    ``keep <= 0`` оставляет список без изменений (компакт выключен).
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
    """Перезаписать history.txt под эксклюзивной блокировкой.

    Авторежим (``force=False``) срабатывает только при ``len(lines) > keep * hysteresis``.
    Возвращает ``(before, after, changed)``. При сбое блокировки/IO: ``(0, 0, False)``.
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
