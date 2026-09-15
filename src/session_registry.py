"""Реестр активных сессий: ``session_<имя>.pid`` в data-каталоге.

Сессии — это отдельные процессы (окна ``:new``), общего демона нет, поэтому
«сессия работает» определяется по pid-файлу: процесс жив — имя занято, мёртв —
файл устарел, и имя можно переиспользовать (такой файл подчищается).

Зачем это нужно: `:new` без имени (кнопка «New session» / ``Ctrl+N``) берёт
наименьшее свободное ``sN`` **среди работающих** сессий. Если считать по файлам
``history_*.txt`` / ``.bashrc_term_*`` (см. `app.list_session_names`), то они
остаются от закрытых сессий и нумерация уползает вверх: s2, s3, s4 … на каждое
нажатие, хотя работает по-прежнему одна сессия.

Пользователь вправе осознанно запустить одноимённую сессию (``:new s2``):
реестр только фиксирует факт, он ничего не запрещает и не блокирует.
"""
from __future__ import annotations

import os
from collections.abc import Iterable

REGISTRY_PREFIX = "session_"
REGISTRY_SUFFIX = ".pid"

# Автоимена для `:new`: s2, s3, … (s1 не занимаем — им был бы «default»).
SESSION_PREFIX = "s"
SESSION_START = 2


def registry_file_for(session: str) -> str:
    """Имя pid-файла сессии (без каталога)."""
    return f"{REGISTRY_PREFIX}{session}{REGISTRY_SUFFIX}"


def registry_path(data_dir: str, session: str) -> str:
    """Полный путь к pid-файлу сессии."""
    return os.path.join(data_dir, registry_file_for(session))


def read_pid(path: str) -> int | None:
    """pid из файла; ``None`` — файла нет, он пуст или битый."""
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read(64).strip()
    except OSError:
        return None
    try:
        pid = int(text)
    except ValueError:
        return None
    return pid if pid > 0 else None


def pid_alive(pid: int) -> bool:
    """Жив ли процесс с таким pid."""
    if pid <= 0:
        return False
    if os.name == "nt":  # pragma: no cover — проверяется только на POSIX
        return _pid_alive_windows(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # процесс есть, просто чужой
    except OSError:
        return False
    return True


def _pid_alive_windows(pid: int) -> bool:  # pragma: no cover — не на POSIX
    """Windows: OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION) как проверка жизни."""
    import ctypes

    process_query_limited_information = 0x1000
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        return False
    kernel32.CloseHandle(handle)
    return True


def register(data_dir: str, session: str, pid: int | None = None) -> bool:
    """Записать pid-файл сессии (0600). Сбой не должен ломать приложение.

    ``pid`` — тот, кого считаем владельцем имени: сам процесс приложения, а при
    запуске нового окна — pid только что поднятого терминала (окно перезапишет
    файл своим pid при старте). ``None``/невалидный pid — пишем свой.
    """
    path = registry_path(data_dir, session)
    value = os.getpid() if not pid or pid <= 0 else pid
    try:
        os.makedirs(data_dir, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    except OSError:
        return False
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(f"{value}\n")
    except OSError:
        return False
    return True


def unregister(data_dir: str, session: str, pid: int | None = None) -> bool:
    """Убрать pid-файл сессии.

    ``pid`` — какой процесс имеет право снять регистрацию: если файл уже
    переписан другим процессом (имя успели переиспользовать), чужую запись не
    трогаем.
    """
    path = registry_path(data_dir, session)
    if pid is not None and read_pid(path) not in (None, pid):
        return False
    try:
        os.unlink(path)
    except OSError:
        return False
    return True


def active_sessions(data_dir: str) -> list[str]:
    """Имена работающих сессий (устаревшие pid-файлы подчищаются)."""
    try:
        entries = os.listdir(data_dir)
    except OSError:
        return []
    names: list[str] = []
    for entry in entries:
        if not (entry.startswith(REGISTRY_PREFIX) and entry.endswith(REGISTRY_SUFFIX)):
            continue
        session = entry[len(REGISTRY_PREFIX) : -len(REGISTRY_SUFFIX)]
        if not session:
            continue
        path = os.path.join(data_dir, entry)
        if pid_alive(read_pid(path) or 0):
            names.append(session)
            continue
        try:
            os.unlink(path)  # сессия закрылась жёстко — файл остался
        except OSError:
            pass
    return sorted(names)


def free_session_name(data_dir: str, *, taken: Iterable[str] = ()) -> str:
    """Наименьшее свободное автоимя (``s2``, ``s3``, …) среди активных сессий.

    ``taken`` — имена, которые надо считать занятыми независимо от реестра
    (например, сессия этого же процесса).
    """
    used = set(active_sessions(data_dir)) | {str(name) for name in taken}
    number = SESSION_START
    while f"{SESSION_PREFIX}{number}" in used:
        number += 1
    return f"{SESSION_PREFIX}{number}"
