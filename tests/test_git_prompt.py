"""Ветка git для приглашения строки ввода (`src/git_prompt.py`).

Подпроцессов нет: `.git` ищется подъёмом вверх, ветка читается из `HEAD`.
Проверяем то, что встречается на практике: обычный репозиторий, вложенный каталог,
`.git`-файл worktree/submodule, отделённый HEAD, отсутствие репозитория и кэш
(после `git switch` подсказка не должна остаться старой).
"""
from __future__ import annotations

import os
from pathlib import Path

from git_prompt import (
    MAX_BRANCH_LEN,
    branch_label,
    find_git_dir,
    format_prompt_branch,
    read_head,
)


def _repo(tmp_path: Path, branch: str = "main", name: str = "proj") -> Path:
    """Каталог с `.git/HEAD` (содержимое git для наших целей не нужно)."""
    root = tmp_path / name
    (root / ".git").mkdir(parents=True)
    (root / ".git" / "HEAD").write_text(f"ref: refs/heads/{branch}\n", encoding="utf-8")
    return root


def test_find_git_dir_up_the_tree(tmp_path):
    root = _repo(tmp_path)
    nested = root / "a" / "b"
    nested.mkdir(parents=True)
    assert find_git_dir(str(root)) == str(root / ".git")
    assert find_git_dir(str(nested)) == str(root / ".git")


def test_find_git_dir_is_none_outside_a_repo(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    assert find_git_dir(str(plain)) is None


def test_find_git_dir_supports_worktree_gitdir_file(tmp_path):
    """`.git`-файл (worktree/submodule): `gitdir: <путь>`, в том числе относительный."""
    gitdir = tmp_path / ".git" / "worktrees" / "wt"
    gitdir.mkdir(parents=True)
    (gitdir / "HEAD").write_text("ref: refs/heads/feature/x\n", encoding="utf-8")
    worktree = tmp_path / "wt"
    worktree.mkdir()
    (worktree / ".git").write_text(
        f"gitdir: {os.path.relpath(gitdir, worktree)}\n", encoding="utf-8"
    )
    assert find_git_dir(str(worktree)) == str(gitdir)
    assert branch_label(str(worktree)) == "feature/x"


def test_branch_label_reads_head(tmp_path):
    root = _repo(tmp_path, branch="feature/long-name")
    assert branch_label(str(root)) == "feature/long-name"
    # Вложенный каталог — тот же репозиторий.
    sub = root / "src"
    sub.mkdir()
    assert branch_label(str(sub)) == "feature/long-name"
    # Пустой / битый `.git` — пусто, без исключений.
    (root / ".git" / "HEAD").write_text("", encoding="utf-8")
    assert read_head(str(root / ".git")) == ""


def test_branch_label_detached_head_is_a_short_sha(tmp_path):
    root = _repo(tmp_path)
    (root / ".git" / "HEAD").write_text("1a2b3c4d5e6f" * 2 + "\n", encoding="utf-8")
    assert branch_label(str(root)) == "@1a2b3c4"


def test_branch_label_not_a_repo(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    assert branch_label(str(plain)) == ""
    assert format_prompt_branch(str(plain)) == ""


def test_cache_follows_a_branch_switch(tmp_path):
    """Кэш — по `HEAD` (mtime+размер): после переключения ветки подсказка меняется."""
    root = _repo(tmp_path, branch="main")
    head = root / ".git" / "HEAD"
    assert branch_label(str(root)) == "main"
    head.write_text("ref: refs/heads/develop-2\n", encoding="utf-8")
    os.utime(head, ns=(9_000_000_000, 9_000_000_000))
    assert branch_label(str(root)) == "develop-2"


def test_format_prompt_branch_truncates_the_tail(tmp_path):
    """Длинное имя режется по хвосту: середина ветки ничего не говорит."""
    root = _repo(tmp_path, branch="feature/very-long-branch-name")
    shown = format_prompt_branch(str(root))
    assert shown.startswith("(…") and shown.endswith("-name)")
    assert len(shown) <= MAX_BRANCH_LEN + 2
    # Короткое имя — как есть, без обрезки.
    assert format_prompt_branch(str(root), max_len=60) == "(feature/very-long-branch-name)"
