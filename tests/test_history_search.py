"""History command search across the session history and the live tag library."""
from __future__ import annotations

import database_v2 as database
from app import CommandRunner
from tests.conftest import info_texts, submit


async def test_history_tags_search_finds_command_and_comment(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        command_tid = database.add_command(app.db_file, "git status --short", "git")
        comment_tid = database.add_command(app.db_file, "sqlite3 library.db", "db")
        database.set_command_comment(app.db_file, "db", comment_tid, "inspect live library")

        await submit(pilot, ":h tags /git")
        output = "\n".join(info_texts(app))
        assert "Library /git  1/1" in output
        assert "git[1]" in output
        assert "git status --short" in output

        await submit(pilot, ":h tags /inspect live")
        output = "\n".join(info_texts(app))
        assert "Library /inspect live  1/1" in output
        assert "db[1]" in output
        assert "inspect live library" in output
        assert command_tid == 1


async def test_history_tags_search_requires_slash_query(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await submit(pilot, ":h tags")
        assert "Usage: :h tags /text" in "\n".join(info_texts(app))


async def test_history_tags_search_reports_no_matches(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await submit(pilot, ":h tags /missing-entry")
        assert "Library: no matches for /missing-entry" in "\n".join(info_texts(app))
