"""Сравнение локальной версии приложения с GitHub main (webxed/IDvjPy).

HTTP и прокси-логин живут в общем сетевом слое `src/net.py` (там же их берёт
`:import <url>`); здесь — только логика сравнения версий и разбор `src/app.py`.
"""
from __future__ import annotations

import os
import re
import urllib.request
from collections.abc import Mapping
from pathlib import Path

from net import format_fetch_error
from net import open_url as _open_url

GITHUB_REPO = "https://github.com/webxed/IDvjPy"
GITHUB_MAIN_APP_PY = (
    "https://raw.githubusercontent.com/webxed/IDvjPy/main/src/app.py"
)
RE_VERSION_ASSIGN = re.compile(
    r'^    VERSION = ["\'](v?\d+\.\d+(?:\.\d+)?)["\']',
    re.MULTILINE,
)
RE_VERSION_TOKEN = re.compile(r"v?(\d+)\.(\d+)(?:\.(\d+))?")

KIND_AVAILABLE = "available"
KIND_CURRENT = "current"
KIND_AHEAD = "ahead"











def format_update_fetch_error(exc: BaseException, environ: Mapping[str, str]) -> str:
    """Текст журнала при неудачном запросе к GitHub; подсказка, если прокси требует логин."""
    return format_fetch_error(exc, environ, subject="Could not check updates")




def parse_version_tuple(text: str) -> tuple[int, ...] | None:
    """Преобразовать ``v1.24`` / ``1.24.0`` в сравнимый кортеж или None."""
    match = RE_VERSION_TOKEN.search((text or "").strip())
    if not match:
        return None
    parts = [int(group) for group in match.groups() if group is not None]
    return tuple(parts)


def parse_version_from_source(source: str) -> str | None:
    """Прочитать ``CommandRunner.VERSION`` из текста ``src/app.py``."""
    match = RE_VERSION_ASSIGN.search(source or "")
    if not match:
        return None
    return match.group(1)


def compare_versions(local: str, remote: str) -> int:
    """-1, если local < remote; 0, если равны; 1, если local > remote.

    Вызывает ValueError, если любая из сторон не является версией.
    """
    left = parse_version_tuple(local)
    right = parse_version_tuple(remote)
    if left is None or right is None:
        raise ValueError(f"Cannot compare versions: {local!r} vs {remote!r}")
    if len(left) < len(right):
        left = left + (0,) * (len(right) - len(left))
    elif len(right) < len(left):
        right = right + (0,) * (len(left) - len(right))
    if left < right:
        return -1
    if left > right:
        return 1
    return 0


def repo_root(start: str | os.PathLike[str] | None = None) -> Path | None:
    """Каталог git-копии приложения (там лежит `app.py` и `.git`).

    `update_check.py` живёт в `<repo>/src/`, поэтому корень — на уровень выше.
    `None` — если исходники не в git (распакованный архив, установка пакетом):
    `git pull` там не сработает, и подсказка остаётся со ссылкой на GitHub.
    Путь считается от самого модуля, а не от cwd: приложение часто запускают
    по алиасу из другого каталога.
    """
    module = Path(start) if start is not None else Path(__file__).resolve()
    root = module.parent.parent
    if not (root / "src" / "app.py").exists():
        return None
    if not (root / ".git").exists():
        return None
    return root


def _shell_path(path: str) -> str:
    """Путь для вставки в команду: кавычим только если без них не разобрать.

    Двойные кавычки, а не одинарные: их понимают и bash, и cmd.exe.
    """
    if re.fullmatch(r"[A-Za-z0-9_@%+=:,./\\-]+", path):
        return path
    return '"' + path.replace('"', '\\"') + '"'


def update_hint(repo_dir: Path | str | None = None) -> str:
    """Готовая команда обновления — с каталогом, чтобы не искать его руками."""
    if repo_dir is None:
        return f"git pull {GITHUB_REPO}"
    return f"git -C {_shell_path(str(repo_dir))} pull"


def format_update_status(
    local: str, remote: str, repo_dir: Path | str | None = None
) -> tuple[str, str]:
    """Человекочитаемый статус и вид: available / current / ahead.

    `repo_dir` — каталог обновляемой копии (по умолчанию `repo_root()`), чтобы в
    подсказке стояла команда целиком: её можно вставить в shell как есть.
    """
    cmp = compare_versions(local, remote)
    if cmp < 0:
        target = repo_dir if repo_dir is not None else repo_root()
        return (
            f"Update available: {remote} (this is {local}). {update_hint(target)}",
            KIND_AVAILABLE,
        )
    if cmp > 0:
        return (
            f"This is {local}; GitHub main is {remote} (local is ahead).",
            KIND_AHEAD,
        )
    return (f"Up to date ({local}).", KIND_CURRENT)


def fetch_remote_version(
    url: str = GITHUB_MAIN_APP_PY,
    timeout: float = 5.0,
    user_agent: str = "IDvjPy-term",
    environ: Mapping[str, str] | None = None,
) -> str:
    """Скачать ``src/app.py`` с GitHub main и вернуть его VERSION.

    Если заданы ``PROXY_USER`` (и необязательный ``PROXY_PASS``) и есть URL
    прокси (``HTTPS_PROXY`` / ``HTTP_PROXY``), учётные данные подставляются,
    чтобы прокси с аутентификацией (407) завершил HTTPS CONNECT.
    """
    env = os.environ if environ is None else environ
    request = urllib.request.Request(
        url,
        headers={"User-Agent": user_agent},
    )
    with _open_url(request, timeout, env) as response:
        source = response.read().decode("utf-8", errors="replace")
    version = parse_version_from_source(source)
    if not version:
        raise ValueError("Could not find VERSION in GitHub src/app.py")
    return version
