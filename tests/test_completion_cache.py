"""Автодополнение пути: кэш листинга, ограничение, детерминированный fallback.

Аудит C4: `os.scandir` вместо listdir+isdir на каждую запись, кэш по mtime,
ограничение размера каталога (`FILE_COMPLETION_SCAN_LIMIT`) и завершение обхода
вверх при «быстром вводе» — большое дерево не должно морозить UI и не должно
перечитываться на каждое нажатие.
"""
from __future__ import annotations

import os

from app import CommandRunner


async def test_dir_listing_is_cached_until_mtime_changes(isolated_home, monkeypatch):
    calls = {"n": 0}
    real_scandir = os.scandir

    def counting_scandir(path):
        calls["n"] += 1
        return real_scandir(path)

    monkeypatch.setattr(os, "scandir", counting_scandir)
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as _pilot:
        before = calls["n"]
        first, _ = app._dir_listing(".")
        second, _ = app._dir_listing(".")
        assert calls["n"] - before == 1  # второй вызов — из кэша
        assert [name for name, _ in first] == [name for name, _ in second]


async def test_scan_limit_truncates(isolated_home, monkeypatch):
    monkeypatch.setattr(CommandRunner, "FILE_COMPLETION_SCAN_LIMIT", 5)
    for i in range(12):
        (isolated_home / f"f{i:02d}.txt").write_text("x", encoding="utf-8")
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as _pilot:
        entries, truncated = app._dir_listing(".")
        assert truncated is True
        assert len(entries) == 5


async def test_completion_candidates_are_capped(isolated_home, monkeypatch):
    monkeypatch.setattr(CommandRunner, "FILE_COMPLETION_SCAN_LIMIT", 5)
    for i in range(12):
        (isolated_home / f"f{i:02d}.txt").write_text("x", encoding="utf-8")
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as _pilot:
        candidates = app.get_completion_candidates("./")
        # `./` — сам токен-каталог (идёт первым), остальное ограничено сканом.
        listed = [c for c in candidates if c != "./"]
        assert len(listed) == 5


async def test_missing_parent_falls_back_deterministically(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as _pilot:
        # Родителя нет — обход вверх ограничен глубиной и не находит совпадений.
        assert app.get_completion_candidates("no/such/deep/dir/x") == []


async def test_directory_entries_marked_as_dirs(isolated_home):
    (isolated_home / "subdir").mkdir()
    (isolated_home / "note.md").write_text("x", encoding="utf-8")
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as _pilot:
        entries = dict(app._dir_listing(".")[0])
        assert entries["subdir"] is True
        assert entries["note.md"] is False
