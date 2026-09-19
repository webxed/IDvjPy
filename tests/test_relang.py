"""`:relang` — перевод комментариев уже засеянной библиотеки (src/relang.py).

Проверяем главное обещание: канонические строки сидов переезжают на другой язык,
а пользовательские теги/команды и правленые руками комментарии остаются как есть.
"""
from __future__ import annotations

import asyncio
import time

import pytest

import database_v2 as database
from app import CommandRunner, InfoBlock
from relang import main as relang_main
from relang import relang_db
from tests.conftest import last_info, submit

# Канонический git-хэндбук: команда, встроенный (русский) и английский комментарий.
GIT_TAG_BASE = "git: статус, diff, ветки, remote, stash"
GIT_TAG_EN = "git: status, diff, branches, remote, stash"


def _seed_git(db: str, *, comment: str, tag_comment: str = GIT_TAG_BASE) -> None:
    database.init_db(db)
    tid = database.add_command(db, "git status", "git")
    database.set_command_comment(db, "git", tid, comment)
    database.set_tag_comment(db, "git", tag_comment)


def test_relang_translates_seeded_comments_to_ru(tmp_path):
    db = str(tmp_path / "mytags.db")
    _seed_git(db, comment="full status", tag_comment=GIT_TAG_EN)

    commands, tags = relang_db(db, "ru")

    assert commands == 1
    assert tags == 1
    assert database.get_command_comment(db, "git", 1) == "полный status"
    assert database.get_tag_comment(db, "git") == GIT_TAG_BASE


def test_relang_translates_base_russian_to_en(tmp_path):
    db = str(tmp_path / "mytags.db")
    _seed_git(db, comment="полный status")

    commands, tags = relang_db(db, "en")

    assert commands == 1
    assert tags == 1
    assert database.get_command_comment(db, "git", 1) == "full status"
    assert database.get_tag_comment(db, "git") == GIT_TAG_EN


def test_relang_keeps_user_tags_commands_and_edited_comments(tmp_path):
    db = str(tmp_path / "mytags.db")
    database.init_db(db)
    # Каноническая команда, но комментарий правили руками — не трогаем.
    tid = database.add_command(db, "git status", "git")
    database.set_command_comment(db, "git", tid, "моя правка")
    # Вторая каноническая строка — её перевести должны (значит, прогон был).
    tid = database.add_command(db, "git status -sb", "git")
    database.set_command_comment(db, "git", tid, "short status")
    # Пользовательский тег с командой: вне канонических сидов.
    database.add_command(db, "echo hi", "mytag")
    database.set_command_comment(db, "mytag", 1, "руками")
    database.set_tag_comment(db, "mytag", "мой тег")

    commands, _tags = relang_db(db, "ru")

    assert commands == 1  # только git[2]
    assert database.get_command_comment(db, "git", 1) == "моя правка"
    assert database.get_command_comment(db, "git", 2) == "короткий status"
    assert database.get_command_comment(db, "mytag", 1) == "руками"
    assert database.get_tag_comment(db, "mytag") == "мой тег"


def test_relang_snapshots_db_before_writing(tmp_path):
    db = str(tmp_path / "mytags.db")
    _seed_git(db, comment="full status")

    relang_db(db, "ru")

    backups = sorted((tmp_path / "backups").glob("mytags-pre-relang-*.db"))
    assert backups, "перед переводом не снят снимок БД"


def test_relang_linux_extra_comment_uses_tid_position(tmp_path):
    """У `logs` нет канонической команды в SEED_COMMANDS — позиция берётся из tid."""
    db = str(tmp_path / "mytags.db")
    database.init_db(db)
    tid = database.add_command(db, "ls -la /var/log", "logs")
    database.set_command_comment(db, "logs", tid, "Список файлов в /var/log")

    commands, tags = relang_db(db, "en")

    assert commands == 1
    assert tags == 1
    assert database.get_command_comment(db, "logs", 1) == "list files in /var/log"
    assert database.get_tag_comment(db, "logs") == "Working with logs"


def test_relang_second_run_is_a_noop(tmp_path):
    db = str(tmp_path / "mytags.db")
    _seed_git(db, comment="full status")

    relang_db(db, "ru")
    commands, tags = relang_db(db, "ru")

    assert (commands, tags) == (0, 0)


def test_relang_cli_translates_and_reports(tmp_path, capsys):
    db = str(tmp_path / "mytags.db")
    _seed_git(db, comment="full status")

    relang_main(["--lang", "ru", "--db", db])

    assert "→ ru" in capsys.readouterr().out
    assert database.get_command_comment(db, "git", 1) == "полный status"


def test_relang_cli_rejects_unknown_language(tmp_path):
    db = str(tmp_path / "mytags.db")
    _seed_git(db, comment="full status")

    with pytest.raises(SystemExit) as exc:
        relang_main(["--lang", "de", "--db", db])

    assert exc.value.code == 2


# --- `:relang` в TUI -------------------------------------------------------


async def _wait_info(app: CommandRunner, needle: str, timeout: float = 8.0) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        texts = [block.text_content for block in app.query(InfoBlock)]
        if any(needle in text for text in texts):
            return texts[-1]
        await asyncio.sleep(0.05)
    raise AssertionError(
        f"нет сообщения с {needle!r}; есть: {[b.text_content for b in app.query(InfoBlock)]}"
    )


async def test_relang_command_help_lists_languages(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":relang")
        text = last_info(app).text_content
        assert "Available: en, ru" in text
        assert ":relang <code>" in text


async def test_relang_command_rejects_unknown_code(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":relang de")
        assert "Unknown language: de" in last_info(app).text_content


async def test_relang_command_translates_the_database(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        _seed_git(app.db_file, comment="full status", tag_comment=GIT_TAG_EN)

        await submit(pilot, ":relang ru")
        text = await _wait_info(app, "→ ru")

        assert "command(s)" in text
        assert database.get_command_comment(app.db_file, "git", 1) == "полный status"
        assert database.get_tag_comment(app.db_file, "git") == GIT_TAG_BASE
