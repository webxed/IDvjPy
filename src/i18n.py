"""Локализация текстов приложения (UI-сообщения, подсказки, справка).

Ключи определяются в ``src/locales/en.yml`` — это **источник правды**; другие
языки (``src/locales/<lang>.yml``) могут быть неполными, недостающее падает на
``en``, а неизвестный ключ возвращается как есть (никогда не печатаем пустоту).

Язык выбирается в порядке: ``--lang`` → ``$IDVJPY_LANG`` → ``settings.yml:
language`` → ``en``. Значение ``auto`` в любом из этих мест разворачивается из
системной локали (``$LC_ALL`` → ``$LC_MESSAGES`` → ``$LANG``).

Значения — строки с разметкой Textual (``[bold]…[/]``) там, где она нужна
шаблону; подстановки — через ``str.format`` (``{name}``). Команды приложения,
имена тегов и ключи настроек не переводятся: язык влияет только на текст.
"""
from __future__ import annotations

import os
import re
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - dependency is in requirements.txt
    yaml = None  # type: ignore[assignment]

LOCALES_DIR = Path(__file__).resolve().parent / "locales"
HELP_DIR_NAME = "help"
DEFAULT_LANG = "en"
AUTO_LANG = "auto"

# Двухбуквенный (или с регионом) код: `ru`, `ru_RU`, `ru-RU.UTF-8` → `ru`.
_RE_LANG_CODE = re.compile(r"^[a-z]{2,8}$")

_lock = threading.RLock()
_lang = DEFAULT_LANG
_catalog: dict[str, Any] = {}
_text_cache: dict[tuple[str, str], str] = {}


def available_languages() -> list[str]:
    """Языки, для которых есть каталог в ``src/locales`` (хотя бы ``en``).

    Язык считается доступным, если есть ``locales/<lang>.yml`` или каталог
    ``locales/<lang>/`` с частями каталога.
    """
    if not LOCALES_DIR.is_dir():
        return [DEFAULT_LANG]
    names = {path.stem for path in LOCALES_DIR.glob("*.yml")}
    names.update(path.name for path in LOCALES_DIR.iterdir() if path.is_dir())
    names.discard(HELP_DIR_NAME)
    return sorted(names) or [DEFAULT_LANG]


def normalize_language(raw: Any) -> str | None:
    """``ru`` / ``ru_RU`` / ``ru-RU.UTF-8`` → ``ru``.

    ``auto`` возвращается как есть; пустое, мусор или язык без каталога → None.
    """
    text = str(raw or "").strip()
    if not text:
        return None
    if text.lower() == AUTO_LANG:
        return AUTO_LANG
    head = re.split(r"[._@-]", text, maxsplit=1)[0].strip().lower()
    if not head or not _RE_LANG_CODE.match(head):
        return None
    return head if head in available_languages() else None


def _from_system_locale() -> str:
    for name in ("LC_ALL", "LC_MESSAGES", "LANG"):
        lang = normalize_language(os.environ.get(name))
        if lang and lang != AUTO_LANG:
            return lang
    return DEFAULT_LANG


def resolve_language(cli: Any = None, settings: Any = None) -> str:
    """Выбранный язык: CLI → ``$IDVJPY_LANG`` → settings → системная локаль (auto)."""
    candidates = [cli, os.environ.get("IDVJPY_LANG"), settings]
    for raw in candidates:
        if str(raw or "").strip().lower() == AUTO_LANG:
            return _from_system_locale()
    for raw in candidates:
        lang = normalize_language(raw)
        if lang:
            return lang
    return DEFAULT_LANG


def _deep_merge(base: dict[str, Any], extra: Mapping[str, Any]) -> dict[str, Any]:
    for key, value in extra.items():
        if isinstance(value, Mapping) and isinstance(base.get(key), dict):
            base[key] = _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _load_yaml(path: Path) -> dict[str, Any]:
    if yaml is None or not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        # Битый файл локали — не падаем: ключи подставит `en` (или сам ключ).
        return {}
    return data if isinstance(data, dict) else {}


def _load_catalog(lang: str) -> dict[str, Any]:
    """``locales/<lang>.yml`` + части ``locales/<lang>/*.yml`` (по возрастанию имени)."""
    data = _load_yaml(LOCALES_DIR / f"{lang}.yml")
    parts = LOCALES_DIR / lang
    if parts.is_dir():
        for path in sorted(parts.glob("*.yml")):
            data = _deep_merge(data, _load_yaml(path))
    return data


def set_language(lang: str) -> str:
    """Сменить язык (неизвестный → ``en``). Возвращает применённый код."""
    global _lang, _catalog
    chosen = normalize_language(lang)
    if not chosen or chosen == AUTO_LANG:
        chosen = DEFAULT_LANG
    with _lock:
        merged = dict(_load_catalog(DEFAULT_LANG))
        if chosen != DEFAULT_LANG:
            merged = _deep_merge(merged, _load_catalog(chosen))
        _lang = chosen
        _catalog = merged
        _text_cache.clear()
    return _lang


def current_language() -> str:
    return _lang


def catalog() -> Mapping[str, Any]:
    with _lock:
        return dict(_catalog)


def _lookup(key: str) -> Any:
    node: Any = catalog()
    for part in (key or "").split("."):
        if not isinstance(node, Mapping) or part not in node:
            return None
        node = node[part]
    return node


def t(key: str, **fmt: Any) -> str:
    """Текст по ключу; нет ключа — сам ключ (диагностика видна, пустоты нет)."""
    value = _lookup(key)
    if value is None:
        return key
    text = str(value)
    if not fmt:
        return text
    try:
        return text.format(**fmt)
    except (KeyError, IndexError, ValueError):
        return text


def tlist(key: str) -> tuple[str, ...]:
    """Список строк по ключу (например, строки справки заставки)."""
    value = _lookup(key)
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value)
    return ()


def text(name: str) -> str:
    """Большой текст из ``locales/help/<lang>/<name>.txt`` (с откатом на ``en``).

    Так живёт справка `:?` — длинные многострочные документы, которым тесно в
    YAML-каталоге. Пустой результат — файла нет ни для языка, ни для ``en``.
    """
    with _lock:
        lang = _lang
        cached = _text_cache.get((lang, name))
    if cached is not None:
        return cached
    base = LOCALES_DIR / HELP_DIR_NAME
    value = ""
    for candidate in (base / lang / f"{name}.txt", base / DEFAULT_LANG / f"{name}.txt"):
        try:
            if candidate.is_file():
                value = candidate.read_text(encoding="utf-8")
                break
        except (OSError, UnicodeDecodeError):
            # Битая справка языка — пробуем `en` (следующий кандидат).
            continue
    with _lock:
        _text_cache[(lang, name)] = value
    return value


# Каталог по умолчанию грузим сразу, чтобы `t()` работал до `on_mount` приложения.
set_language(DEFAULT_LANG)
