"""Локализованные шаблоны личных файлов: ``settings.yml`` и ``llm_providers.yml``.

Шаблоны лежат по каталогам языка: ``src/settings/<lang>.yml`` и
``src/llm_providers/<lang>.yml`` — ключи одинаковы, комментарии переведены (у
провайдеров LLM язык файла задаёт ещё ``answer_language`` и текст офлайн-заглушки).
При первом запуске в новом data-каталоге приложение копирует файл языка, выбранного
**в режиме auto** — ``--lang`` → ``$IDVJPY_LANG`` → системная локаль
(``$LC_ALL``/``$LC_MESSAGES``/``$LANG``) → ``en`` (см. ``detect_language``).

Языка без файла не бывает: ``*_example_path`` откатывается на ``en``, а если нет и
его — возвращает ``None`` (вызывающий решает, что писать вместо шаблона).

Ключ ``language`` в шаблонах настроек остаётся ``auto``: интерфейс и дальше следует
системной локали; сменить — ``:lang <код>``.
"""
from __future__ import annotations

import os
from pathlib import Path

_HERE = Path(__file__).resolve().parent
SETTINGS_DIR = _HERE / "settings"
LLM_PROVIDERS_DIR = _HERE / "llm_providers"
DEFAULT_EXAMPLE_LANG = "en"


def available_languages(directory: Path) -> list[str]:
    """Языки, для которых есть шаблон в каталоге."""
    if not directory.is_dir():
        return []
    return sorted(path.stem for path in directory.glob("*.yml"))


def _example_path(directory: Path, lang: str | None) -> str | None:
    code = (lang or "").strip() or DEFAULT_EXAMPLE_LANG
    candidate = directory / f"{code}.yml"
    if not candidate.is_file():
        candidate = directory / f"{DEFAULT_EXAMPLE_LANG}.yml"
    return str(candidate) if candidate.is_file() else None


def available_settings_languages() -> list[str]:
    """Языки шаблонов ``settings.yml`` (``src/settings/<lang>.yml``)."""
    return available_languages(SETTINGS_DIR)


def available_llm_providers_languages() -> list[str]:
    """Языки шаблонов ``llm_providers.yml`` (``src/llm_providers/<lang>.yml``)."""
    return available_languages(LLM_PROVIDERS_DIR)


def settings_example_path(lang: str | None = None) -> str | None:
    """Путь к шаблону настроек языка; нет языка/файла — ``en``; нет и его — ``None``."""
    return _example_path(SETTINGS_DIR, lang)


def llm_providers_example_path(lang: str | None = None) -> str | None:
    """Путь к шаблону провайдеров языка; нет языка/файла — ``en``; нет и его — ``None``."""
    return _example_path(LLM_PROVIDERS_DIR, lang)


def detect_language(explicit: str | None = None) -> str:
    """Язык шаблонов: явный (``--lang`` / ``$IDVJPY_LANG``) → системная локаль → ``en``.

    ``explicit`` — уже известный явный выбор (``--lang``); ``$IDVJPY_LANG``
    читается здесь же. Без явного значения используется системная локаль — то же
    поведение, что у ``language: auto``.
    """
    try:
        from i18n import resolve_language
    except ImportError:  # запуск без src/ в sys.path
        return DEFAULT_EXAMPLE_LANG
    raw = (explicit or os.environ.get("IDVJPY_LANG") or "").strip()
    code = resolve_language(raw or "auto", None)
    return code if code in available_settings_languages() else DEFAULT_EXAMPLE_LANG
