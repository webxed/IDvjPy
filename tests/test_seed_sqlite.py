"""Справочник `sqlite` (`seed_sqlite.py`): SQL на живой базе библиотеки.

Проверяем три вещи: набор тегов и их наполнение, что меняют базу только tid 11-13
(остальные — чтение), и что `$DBFILE` приходит из приложения, а не угадывается.
"""
from __future__ import annotations

import os

import pytest

import database_v2 as database
import seed_catalog
import seed_ops
import seed_sqlite

# Команды, которые пишут в базу или файл: ровно они помечены «меняет» в сиде.
MUTATING_TIDS = (11, 12, 13)


def _sqlite_commands() -> list[tuple[str, str]]:
    tag_comment, commands = seed_sqlite.SEED_TAGS["sqlite"]
    assert tag_comment
    return commands


def test_seed_tags_shape():
    assert list(seed_sqlite.SEED_TAGS) == ["sqlvars", "sqlite", "sqlstat"]
    tag_comment, commands = seed_sqlite.SEED_TAGS["sqlite"]
    assert len(commands) == 16
    assert "11–13" in tag_comment  # в подписи видно, какие tid меняют базу


def test_run_seed_puts_tags_in_the_library(tmp_path):
    db = str(tmp_path / "sqlite.db")
    assert seed_sqlite.run_seed(db) == sum(
        len(commands) for _, commands in seed_sqlite.SEED_TAGS.values()
    )
    assert database.get_command_by_tid(db, "sqlite", 1)["command"].startswith(
        "command -v sqlite3"
    )
    assert database.get_command_by_tid(db, "sqlite", 2)["command"] == (
        'sqlite3 $DBFILE ".tables"'
    )
    assert "GROUP BY tag" in database.get_command_by_tid(db, "sqlite", 5)["command"]
    assert "EXPLAIN QUERY PLAN" in database.get_command_by_tid(db, "sqlite", 10)["command"]
    assert "DELETE FROM commands WHERE tag" in database.get_command_by_tid(db, "sqlite", 11)["command"]
    assert "VACUUM" in database.get_command_by_tid(db, "sqlite", 13)["command"]
    assert database.get_command_by_tid(db, "sqlvars", 1)["command"].startswith("echo db=")


def test_only_marked_tids_change_the_database():
    """Читающие команды не содержат DELETE/VACUUM, а меняющие — помечены."""
    for index, (command, comment) in enumerate(_sqlite_commands(), start=1):
        changes = ("DELETE" in command) or ("VACUUM" in command)
        assert changes == (index in MUTATING_TIDS), command
        if changes:
            assert "меняет" in comment, command


def test_every_command_uses_the_injected_path():
    """Путь к базе приходит только как `$DBFILE` — иначе разойдётся с каталогом данных."""
    for index, (command, _comment) in enumerate(_sqlite_commands(), start=1):
        if index == 1:
            continue  # проверка наличия CLI — без пути
        assert "$DBFILE" in command, command
        assert "mytags.db" not in command, command
        assert command.startswith("sqlite3"), command


def test_playbook_is_inspect_only_and_refers_to_existing_tids():
    chain, comment = seed_sqlite.SEED_TAGS["sqlstat"][1][0]
    assert "DELETE" not in chain and "VACUUM" not in chain
    assert "integrity_check" not in chain  # сама целостность — в sqlite[14]
    for token in ("!sqlite[5]", "!sqlite[8]", "!sqlite[14]"):
        assert token in chain
    assert comment


def test_seed_is_part_of_ops_and_catalog():
    names = [name for name, _ in seed_ops.MODULES]
    assert "sqlite" in names
    assert ("seed_sqlite.py", "SEED_SQLITE_COMMANDS.md") in seed_catalog.SEED_HANDBOOKS_OPS
    from seed_groups import group_for_tag

    assert group_for_tag("sqlite") == "sqlite"
    assert group_for_tag("sqlstat") == "sqlite"


def test_handbook_doc_exists_for_every_language():
    from md_viewer import REPO_ROOT, handbook_md_path

    for lang in ("ru", "en", "zh"):
        path = handbook_md_path("SEED_SQLITE_COMMANDS.md", lang)
        assert path is not None and path.is_file(), lang
    base = REPO_ROOT / "docs" / "SEED_SQLITE_COMMANDS.md"
    assert base.is_file()


@pytest.mark.slow
async def test_dbfile_variable_points_at_the_open_library(isolated_home):
    from app import CommandRunner

    app = CommandRunner()
    async with app.run_test(size=(120, 40)):
        assert app.local_env["DBFILE"] == os.path.abspath(app.db_file)


@pytest.mark.slow
async def test_own_dbfile_in_bashrc_wins(isolated_home):
    from app import CommandRunner

    own = str(isolated_home / "other.db")
    (isolated_home / ".bashrc_term_default").write_text(
        f"DBFILE={own}\n", encoding="utf-8"
    )
    app = CommandRunner()
    async with app.run_test(size=(120, 40)):
        assert app.local_env["DBFILE"] == own
