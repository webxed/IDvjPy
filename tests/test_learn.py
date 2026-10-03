"""The :learn exercises inspect completed blocks but never execute commands."""
from __future__ import annotations

import pytest

import learn
from app import CommandBlock, CommandRunner
from tests.conftest import last_info, submit, wait_command_done


def _lesson(name: str) -> learn.Lesson:
    lesson = learn.get_lesson(name)
    assert lesson is not None
    return lesson


@pytest.mark.parametrize(
    ("lesson", "command", "accepted"),
    [
        ("git-status", "git status", True),
        ("git-status", "git status -sb", True),
        ("git-status", "git status && rm -rf /tmp/x", False),
        ("git-status", "git status /tmp", False),
        ("listening-ports", "ss -tlnp", True),
        ("listening-ports", "ss -tlnp | cat", False),
        ("listening-ports", "lsof -iTCP -sTCP:LISTEN -P -n", True),
        ("sqlite-select", "sqlite3 -readonly $DBFILE 'SELECT tag FROM commands LIMIT 10;'", True),
        ("sqlite-select", "sqlite3 -readonly $DBFILE 'SELECT tag FROM commands; DELETE FROM commands;'", False),
        ("sqlite-select", "sqlite3 $DBFILE 'SELECT tag FROM commands'", False),
    ],
)
def test_check_recognizes_only_expected_read_only_command_shapes(lesson, command, accepted):
    block = CommandBlock("test", "", "", 0, source_command=command)
    block.pending = False
    result = learn.check(_lesson(lesson), block)
    assert ("passed" in result.lower()) is accepted


def test_check_rejects_pending_and_failed_blocks():
    lesson = _lesson("git-status")
    pending = CommandBlock("test", "", "", 0, source_command="git status")
    assert "still running" in learn.check(lesson, pending).lower()
    failed = CommandBlock("test", "", "", 128, source_command="git status")
    failed.pending = False
    assert "128" in learn.check(lesson, failed)


async def test_check_uses_latest_new_block_even_when_an_older_new_block_is_pending(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":learn git-status")
        old_pending = CommandBlock("pending", "", "", 0, source_command="git status")
        app.add_block(old_pending)
        await submit(pilot, "true")
        await wait_command_done(app)
        await submit(pilot, ":learn check")
        assert "not the recognized task command" in last_info(app).text_content.lower()
        assert len(list(app.query(CommandBlock))) == 2


async def test_check_does_not_launch_or_repeat_a_command(isolated_home, monkeypatch):
    app = CommandRunner()
    def fail_if_run(*_args, **_kwargs):
        raise AssertionError(":learn check must not execute commands")
    monkeypatch.setattr(app, "run_command", fail_if_run)
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":learn git-status")
        await submit(pilot, ":learn check")
        assert "no finished command" in last_info(app).text_content.lower()
        assert not app.query(CommandBlock)
