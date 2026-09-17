"""Поиск по markdown-файлам (`:rg`) — Obsidian-vault или любой каталог с `.md`.

Бэкенд: **ripgrep** (`rg`), если есть в `PATH` — быстро и уважает `.gitignore`;
иначе встроенный обход на Python (тот же результат, медленнее). Результат —
фрагменты строк с путём и номером строки; приложение делает их кликабельными
для встроенного md-просмотрщика.

Паттерн — регулярное выражение (как у `rg`), «умный регистр»: если в паттерне
нет заглавных букв, регистр игнорируется.
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field

DEFAULT_GLOB = "*.md"
DEFAULT_LIMIT = 200
RG_TIMEOUT = 20.0
MAX_LINE_CHARS = 300
# Каталоги, которые не обходим встроенным сканером (в т.ч. служебные Obsidian).
SKIP_DIRS = {
    ".git", ".obsidian", ".trash", ".venv", "venv", "node_modules",
    "__pycache__", ".idea", ".vscode", ".hg", ".svn",
}


@dataclass(frozen=True)
class MdMatch:
    """Одно совпадение: путь для показа/открытия, строка и её текст."""

    path: str        # относительно base, если получилось
    abs_path: str    # абсолютный путь для открытия
    line: int        # номер строки (1-based)
    text: str        # фрагмент строки (обрезан по MAX_LINE_CHARS)


@dataclass
class MdSearchResult:
    matches: list[MdMatch] = field(default_factory=list)
    files: int = 0
    backend: str = "python"
    truncated: bool = False
    base: str = ""


def rg_available() -> bool:
    """Есть ли ripgrep в PATH."""
    return shutil.which("rg") is not None


def install_hint() -> str:
    """Подсказка по установке ripgrep (когда его нет)."""
    return (
        "ripgrep (rg) not found — using the built-in scanner. Faster with rg: "
        "apt install ripgrep | dnf install ripgrep | brew install ripgrep | "
        "pacman -S ripgrep | cargo install ripgrep"
    )


def _smart_case_flags(pattern: str) -> int:
    """Нет заглавных в паттерне → игнорировать регистр (как rg --smart-case)."""
    return 0 if any(ch.isupper() for ch in pattern) else re.IGNORECASE


def _display_path(abs_path: str, base: str) -> str:
    """Путь относительно base, если он внутри неё; иначе абсолютный."""
    try:
        rel = os.path.relpath(abs_path, base)
    except ValueError:
        return abs_path
    return abs_path if rel.startswith("..") else rel


def search(
    pattern: str,
    base: str,
    glob: str = DEFAULT_GLOB,
    limit: int = DEFAULT_LIMIT,
    use_rg: bool | None = None,
) -> MdSearchResult:
    """Найти паттерн в markdown-файлах под `base`.

    `use_rg=None` — ripgrep, если доступен, иначе встроенный сканер.
    Бросает ValueError при некорректном регулярном выражении.
    """
    if use_rg is None:
        use_rg = rg_available()
    if use_rg:
        return _search_rg(pattern, base, glob, limit)
    return _search_python(pattern, base, glob, limit)


def _search_rg(pattern: str, base: str, glob: str, limit: int) -> MdSearchResult:
    """Поиск через ripgrep (`--json` — надёжный разбор путей с любыми символами)."""
    result = MdSearchResult(backend="rg", base=base)
    cmd = [
        "rg", "--json", "--smart-case", "--color=never",
        "--max-columns", str(MAX_LINE_CHARS), "--max-columns-preview",
        "-g", glob, "--", pattern, base,
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.DEVNULL,
            timeout=RG_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        # rg отвалился (не найден / таймаут) — считаем встроенным сканером.
        return _search_python(pattern, base, glob, limit)
    if proc.returncode == 2:
        detail = (proc.stderr or "").strip().splitlines()
        raise ValueError(detail[0] if detail else "ripgrep error")
    seen_files: set[str] = set()
    parse_errors = 0
    for raw in proc.stdout.splitlines():
        if not raw:
            continue
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            parse_errors += 1
            continue
        if event.get("type") != "match":
            continue
        data = event.get("data") or {}
        path = ((data.get("path") or {}).get("text")) or ""
        line_no = int(data.get("line_number") or 0)
        text = ((data.get("lines") or {}).get("text")) or ""
        if not path:
            continue
        abs_path = path if os.path.isabs(path) else os.path.abspath(path)
        seen_files.add(abs_path)
        result.matches.append(
            MdMatch(
                path=_display_path(abs_path, base),
                abs_path=abs_path,
                line=line_no,
                text=text.rstrip("\n")[:MAX_LINE_CHARS],
            )
        )
        if len(result.matches) > limit:
            result.truncated = True
            break
    if parse_errors and not result.matches:
        raise ValueError("ripgrep produced unreadable output")
    result.files = len(seen_files)
    return result


def _search_python(pattern: str, base: str, glob: str, limit: int) -> MdSearchResult:
    """Встроенный обход дерева (fallback, когда ripgrep недоступен)."""
    try:
        rx = re.compile(pattern, _smart_case_flags(pattern))
    except re.error as e:
        raise ValueError(f"invalid pattern: {e}") from e
    result = MdSearchResult(backend="python", base=base)
    seen_files: set[str] = set()
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for name in sorted(files):
            if not fnmatch.fnmatch(name, glob):
                continue
            abs_path = os.path.join(root, name)
            try:
                with open(abs_path, encoding="utf-8", errors="replace") as handle:
                    for number, line in enumerate(handle, 1):
                        if not rx.search(line):
                            continue
                        seen_files.add(abs_path)
                        result.matches.append(
                            MdMatch(
                                path=_display_path(abs_path, base),
                                abs_path=abs_path,
                                line=number,
                                text=line.rstrip("\n")[:MAX_LINE_CHARS],
                            )
                        )
                        if len(result.matches) > limit:
                            result.truncated = True
                            result.files = len(seen_files)
                            return result
            except OSError:
                continue
    result.files = len(seen_files)
    return result
