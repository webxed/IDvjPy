"""Дополнение имён системных команд из ``$PATH``.

Используется автодополнением TUI в позиции имени команды (``gi<Tab>`` → ``git``)
при включённом флаге ``system_command_completion: true`` в settings.yml.

Видны только настоящие исполняемые файлы: alias'ы и функции shell живут внутри
оболочки и дочернему процессу недоступны, поэтому подсказать их приложение не
может. Скан ``$PATH`` кэшируется по строке окружения и прогревается в фоне, чтобы
не блокировать event loop (см. ``CommandRunner._warm_system_command_cache``).
"""
import os
import threading
import time

# Кэш полного списка имён: строка `$PATH` → (имена, отпечаток каталогов, время проверки).
_cache: dict[str, tuple[list[str], tuple, float]] = {}
_cache_lock = threading.Lock()
# Не даём кэшу расти без предела: строк `$PATH` за сессию — единицы.
_CACHE_LIMIT = 4
# Как часто перепроверять отпечаток каталогов: чаще — лишние `stat` на каждое
# нажатие, реже — установленная команда дольше не видна в подсказках.
_REVALIDATE_SEC = 10.0

# Windows: базовый набор суффиксов, если `PATHEXT` не задан.
_WINDOWS_EXTENSIONS = (".exe", ".bat", ".cmd", ".com")


def _windows_extensions() -> tuple[str, ...]:
    """Суффиксы исполняемых файлов из ``PATHEXT`` (нижний регистр)."""
    raw = os.environ.get("PATHEXT", "")
    exts = tuple(part.strip().lower() for part in raw.split(";") if part.strip())
    return exts or _WINDOWS_EXTENSIONS


def _scan(path_env: str) -> list[str]:
    """Отсортированные уникальные имена исполняемых файлов из ``$PATH``."""
    names: list[str] = []
    seen: set[str] = set()
    windows = os.name == "nt"
    exts = _windows_extensions() if windows else ()
    separator = ";" if windows else os.pathsep
    for directory in path_env.split(separator):
        # Пустой компонент PATH означает текущий каталог (POSIX и cmd.exe).
        directory = directory or os.curdir
        try:
            entries = os.scandir(directory)
        except OSError:
            continue
        try:
            for entry in sorted(
                entries, key=lambda candidate: (candidate.name.casefold(), candidate.name)
            ):
                try:
                    if not entry.is_file():
                        continue
                    name = entry.name
                    if windows:
                        lower = name.lower()
                        for ext in exts:
                            if lower.endswith(ext):
                                name = name[: -len(ext)]
                                break
                        else:
                            # Не исполняемый по PATHEXT — пропускаем.
                            continue
                    elif not os.access(entry.path, os.X_OK):
                        continue
                except OSError:
                    continue
                seen_name = name.casefold() if windows else name
                if not name or seen_name in seen:
                    continue
                seen.add(seen_name)
                names.append(name)
        finally:
            entries.close()
    return sorted(names)


def _path_signature(path_env: str) -> tuple:
    """Отпечаток каталогов `$PATH`: mtime каждого компонента (без чтения файлов).

    `stat` дешёвый, но всё равно I/O: его вызывает только фоновой прогрев
    (`_all_names`), а не `cached_system_command_candidates` из UI.
    """
    signature: list[tuple[str, int]] = []
    for directory in path_env.split(os.pathsep):
        # Пустой компонент PATH означает текущий каталог (POSIX и cmd.exe).
        target = directory or os.curdir
        try:
            stamp = os.stat(target).st_mtime_ns
        except OSError:
            stamp = -1
        signature.append((target, stamp))
    return tuple(signature)


def _all_names(path_env: str, *, force: bool = False) -> list[str]:
    """Имена из ``$PATH`` с кэшем по строке окружения.

    Кэш переживает установку программы: после `_REVALIDATE_SEC` отпечаток
    каталогов проверяется заново, и изменённый `$PATH`-каталог сканируется ещё
    раз (новый исполняемый файл не требует перезапуска приложения).
    """
    now = time.monotonic()
    with _cache_lock:
        entry = _cache.get(path_env)
    if entry is not None and not force:
        names, signature, checked_at = entry
        if now - checked_at < _REVALIDATE_SEC:
            return names
        if _path_signature(path_env) == signature:
            with _cache_lock:
                _cache[path_env] = (names, signature, now)
            return names
    names = _scan(path_env)
    signature = _path_signature(path_env)
    with _cache_lock:
        if len(_cache) >= _CACHE_LIMIT:
            _cache.clear()
        _cache[path_env] = (names, signature, now)
    return names


def _path_env(path_env: str | None) -> str:
    """Вернуть явный или текущий ``$PATH`` для ключа кэша."""
    return os.environ.get("PATH", "") if path_env is None else path_env


def _matches_prefix(name: str, prefix: str) -> bool:
    """Сопоставление имени как его выполняет целевая платформа."""
    if os.name == "nt":
        return name.casefold().startswith(prefix.casefold())
    return name.startswith(prefix)


def system_command_candidates(
    prefix: str, *, path_env: str | None = None, limit: int = 20
) -> list[str]:
    """Синхронно просканировать ``$PATH`` и вернуть команды с ``prefix``.

    API предназначен для worker-а и модульных вызовов. TUI должен применять
    ``cached_system_command_candidates``, чтобы файловый I/O не попал в event loop.
    """
    path_env = _path_env(path_env)
    if limit <= 0:
        return []
    return [
        name for name in _all_names(path_env) if _matches_prefix(name, prefix)
    ][:limit]


def cached_system_command_candidates(
    prefix: str, *, path_env: str | None = None, limit: int = 20
) -> list[str] | None:
    """Вернуть кандидаты из готового кэша либо ``None`` без файлового I/O.

    ``None`` возвращается и для устаревшего кэша: вызывающий запускает фоновой
    прогрев, который дешёво сверит отпечаток каталогов или пересканирует их.
    """
    path_env = _path_env(path_env)
    if limit <= 0:
        return []
    with _cache_lock:
        entry = _cache.get(path_env)
    if entry is None:
        return None
    names, _signature, checked_at = entry
    if time.monotonic() - checked_at >= _REVALIDATE_SEC:
        return None
    return [name for name in names if _matches_prefix(name, prefix)][:limit]


def warm_system_command_cache(path_env: str | None = None) -> None:
    """Синхронно прогреть кэш; вызывать только из фонового worker-а."""
    _all_names(_path_env(path_env))


def clear_cache() -> None:
    """Сбросить кэш имён (тесты и смена `$PATH` в пределах сессии)."""
    with _cache_lock:
        _cache.clear()
