"""Выбор пользовательского data-каталога IDvjPy_term (кросс-платформенно).

Здесь лежат настройки/БД/история при pip-установке. Приоритет:

1. ``--data-dir <path>`` (явный аргумент запуска);
2. ``$IDVJPY_DATA_DIR`` (удобно для тестов и портативных установок);
3. «портативный режим»: если в текущем каталоге уже есть ``settings.yml``
   (запуск из репозитория или старой раскладки) — работаем от текущего каталога;
4. платформенный каталог по умолчанию:
   - Linux:  ``$XDG_CONFIG_HOME/idvjpy`` или ``~/.config/idvjpy``;
   - macOS:  ``~/Library/Application Support/IDvjPy``;
   - Windows: ``%APPDATA%/IDvjPy``.

Модуль не зависит от Textual и может использоваться лаунчером до импорта TUI.
"""
import os
import sys

APP_DIR_LINUX = "idvjpy"
APP_DIR_OTHER = "IDvjPy"
MARKER_FILE = "settings.yml"


def platform_default_dir() -> str:
    """Платформенный каталог данных по умолчанию (без создания)."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.abspath(os.path.join(base, APP_DIR_OTHER))
    if sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
        return os.path.abspath(os.path.join(base, APP_DIR_OTHER))
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.abspath(os.path.join(base, APP_DIR_LINUX))


def cwd_is_portable(cwd: str | None = None) -> bool:
    """Текущий каталог уже хранит данные приложения (settings.yml рядом)."""
    directory = os.path.abspath(cwd or os.getcwd())
    return os.path.isfile(os.path.join(directory, MARKER_FILE))


def resolve_data_dir(explicit: str | None = None) -> str:
    """Итоговый data-каталог по приоритету explicit → env → portable → platform."""
    if explicit and str(explicit).strip():
        return os.path.abspath(os.path.expanduser(str(explicit).strip()))
    env = os.environ.get("IDVJPY_DATA_DIR")
    if env and str(env).strip():
        return os.path.abspath(os.path.expanduser(str(env).strip()))
    if cwd_is_portable():
        return os.path.abspath(os.getcwd())
    return platform_default_dir()


def ensure_data_dir(directory: str) -> str:
    """Создаёт data-каталог (если нужно) и возвращает его абсолютный путь."""
    directory = os.path.abspath(directory)
    try:
        os.makedirs(directory, exist_ok=True)
    except OSError:
        pass  # Не критично: файлы создадутся с ошибками с понятными сообщениями
    return directory
