"""Listing and restoring exact SQLite database snapshots."""
from __future__ import annotations

import pytest

import database_v2 as database
import seed_lib
from app import CommandLineInput, CommandRunner
from tests.conftest import info_texts, submit


def _make_db(path, command: str) -> str:
    db = str(path)
    database.init_db(db)
    database.add_command(db, command, "demo")
    return db


def test_list_sqlite_backups_newest_first(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db = _make_db(tmp_path / "library.db", "echo live")
    older = seed_lib.backup_sqlite(db, "older", quiet=True)
    newer = seed_lib.backup_sqlite(db, "newer", quiet=True)
    assert older is not None and newer is not None
    backups = seed_lib.list_sqlite_backups(db)
    assert set(backups) == {older, newer}
    assert backups[0] == newer


def test_restore_sqlite_backup_saves_live_database_first(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db = _make_db(tmp_path / "library.db", "echo current")
    selected = seed_lib.backup_sqlite(db, "saved", quiet=True)
    assert selected is not None
    database.add_command(db, "echo later", "demo")

    pre_restore = seed_lib.restore_sqlite_backup(db, selected.name)

    assert pre_restore is not None and pre_restore.exists()
    assert database.get_command_by_tid(db, "demo", 2) is None
    preserved = database.get_command_by_tid(str(pre_restore), "demo", 2)
    assert preserved is not None and preserved["command"] == "echo later"
    restored = database.get_command_by_tid(db, "demo", 1)
    assert restored is not None and restored["command"] == "echo current"


def test_restore_rejects_path_outside_backup_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db = _make_db(tmp_path / "library.db", "echo current")
    outside = _make_db(tmp_path / "outside.db", "echo external")
    with pytest.raises(ValueError, match="inside the configured backup directory"):
        seed_lib.restore_sqlite_backup(db, outside)


async def test_backup_list_and_restore_require_second_enter(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "#demo echo baseline")
        await submit(pilot, ":backup")
        await submit(pilot, "#demo echo later")
        await submit(pilot, ":backup list")
        listing = "\n".join(info_texts(app))
        assert "SQLite backups (newest first)" in listing
        assert "-manual-" in listing

        await submit(pilot, ":backup restore 1")
        assert "Current database will first be saved" in info_texts(app)[-1]
        assert input_value(app) == ":backup restore-yes " + input_value(app).split()[-1]
        assert database.get_command_by_tid(app.db_file, "demo", 2) is not None

        await submit(pilot, input_value(app))
        assert "Database restored from" in info_texts(app)[-1]
        assert database.get_command_by_tid(app.db_file, "demo", 2) is None


def input_value(app: CommandRunner) -> str:
    return app.query_one("#command-input", CommandLineInput).value or ""
