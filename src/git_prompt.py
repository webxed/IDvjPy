"""Ветка git для приглашения строки ввода (`.git` вверх от cwd).

Приглашение показывает cwd серым, как в терминале; если каталог лежит внутри
репозитория, рядом появляется `(ветка)` — как `__git_ps1` в bash. Подпроцессов
нет: `.git` ищется подъёмом вверх, ветка читается прямо из `HEAD`. Это дёшево —
приглашение обновляется на каждом `cd`, на ресайзе и после каждой команды
(`git switch` меняет ветку без смены каталога, и подсказка не должна врать).

Разбираем руками то, что встречается: `.git`-каталог, `.git`-файл (worktree и
submodule — `gitdir: /path/…`), отделённый HEAD (вместо имени короткий SHA:
`(@1a2b3c4)`), отсутствие репозитория (пусто — в приглашении ничего не
добавляется). Голый репозиторий сюда не попадает: `.git` ищется как обычный
каталог/файл от cwd, а не по `$GIT_DIR`.
"""
from __future__ import annotations

import os

# Хвост длинного имени ветки: `feature/very-long-name` → `(…/very-long-name)`
MAX_BRANCH_LEN = 24
SHORT_SHA = 7
# Кэш читается на каждое обновление приглашения: ключ — файл `HEAD`,
# значение — (mtime_ns, размер) и уже разобранная ветка.
_CACHE_MAX = 64
_cache: dict[str, tuple[tuple[int, int], str]] = {}


def find_git_dir(start: str) -> str | None:
    """Ближайший `.git` вверх от `start`: каталог репозитория или gitdir worktree."""
    current = os.path.abspath(start)
    while True:
        candidate = os.path.join(current, ".git")
        if os.path.isdir(candidate):
            return candidate
        if os.path.isfile(candidate):
            return _gitdir_from_file(candidate, current)
        parent = os.path.dirname(current)
        if parent == current:  # дошли до корня файловой системы
            return None
        current = parent


def _gitdir_from_file(path: str, directory: str) -> str | None:
    """`.git`-файл worktree/submodule: `gitdir: <путь>` (может быть относительным)."""
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            raw = handle.readline().strip()
    except OSError:
        return None
    if not raw.startswith("gitdir:"):
        return None
    target = raw[len("gitdir:"):].strip()
    if not target:
        return None
    if not os.path.isabs(target):
        target = os.path.join(directory, target)
    target = os.path.normpath(target)
    return target if os.path.isdir(target) else None


def read_head(git_dir: str) -> str:
    """Ветка из `HEAD`: `ref: refs/heads/main` → `main`; отделённый HEAD → короткий SHA."""
    head_path = os.path.join(git_dir, "HEAD")
    try:
        stat = os.stat(head_path)
    except OSError:
        return ""
    key = (stat.st_mtime_ns, stat.st_size)
    cached = _cache.get(head_path)
    if cached is not None and cached[0] == key:
        return cached[1]
    label = _parse_head(head_path)
    if len(_cache) >= _CACHE_MAX:
        _cache.pop(next(iter(_cache)))
    _cache[head_path] = (key, label)
    return label


def _parse_head(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            raw = handle.read(4096).strip()
    except OSError:
        return ""
    if not raw:
        return ""
    if raw.startswith("ref:"):
        ref = raw[len("ref:"):].strip()
        if ref.startswith("refs/heads/"):
            return ref[len("refs/heads/"):]
        # Не ветка (напр. ссылка в чужой namespace) — отдаём последний компонент.
        return ref.rsplit("/", 1)[-1] if ref else ""
    # Отделённый HEAD — в `HEAD` лежит сам коммит; как у git, короткий SHA.
    if len(raw) >= SHORT_SHA and all(ch in "0123456789abcdef" for ch in raw.lower()):
        return f"@{raw[:SHORT_SHA]}"
    return ""


def branch_label(path: str) -> str:
    """Ветка репозитория, в котором лежит `path` (`""` — не репозиторий)."""
    git_dir = find_git_dir(path)
    if git_dir is None:
        return ""
    return read_head(git_dir)


def format_prompt_branch(path: str, max_len: int = MAX_BRANCH_LEN) -> str:
    """`(main)` для приглашения; `""` — не репозиторий.

    Длинное имя режется по хвосту (`(…/very-long-name)`): где ты — видно по концу
    строки, середина ветки не несёт информации.
    """
    label = branch_label(path)
    if not label:
        return ""
    return f"({_shorten(label, max_len)})"


def _shorten(label: str, max_len: int) -> str:
    if max_len <= 1 or len(label) <= max_len:
        return label
    return "…" + label[-(max_len - 1):]
