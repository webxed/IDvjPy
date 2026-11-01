"""База по умолчанию — в каталоге данных пользователя, а не рядом с исходниками.

Сид/CLI запускают из любого каталога (часто из репозитория), но путь к базе
должен совпадать с тем, что читает TUI: `data_dirs.resolve_data_dir()` →
`mytags.db` (или имя из `settings.yml` этого каталога). Явный `--db` главнее.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import backup_db
import data_dirs
import seed_lib
import seed_linux_commands


@pytest.fixture
def user_dir(tmp_path, monkeypatch):
    """Подменить системный каталог данных и убрать env/portable-режим."""
    monkeypatch.delenv("IDVJPY_DATA_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    home = tmp_path / "userdir"
    monkeypatch.setattr(data_dirs, "platform_default_dir", lambda: str(home))
    return home


def test_default_is_user_data_dir(user_dir):
    assert seed_lib.get_db_file() == str(user_dir / "mytags.db")
    assert user_dir.is_dir(), "каталог данных должен быть создан"


def test_env_dir_wins(user_dir, tmp_path, monkeypatch):
    env_dir = tmp_path / "custom"
    monkeypatch.setenv("IDVJPY_DATA_DIR", str(env_dir))
    assert seed_lib.get_db_file() == str(env_dir / "mytags.db")


def test_portable_cwd_with_settings_still_wins(user_dir, tmp_path):
    (tmp_path / "settings.yml").write_text(
        "database_tags_file: mytags.db\n", encoding="utf-8"
    )
    assert seed_lib.get_db_file() == str(tmp_path / "mytags.db")


def test_relative_name_from_data_dir_settings(user_dir):
    user_dir.mkdir()
    (user_dir / "settings.yml").write_text(
        "database_tags_file: library.db\n", encoding="utf-8"
    )
    assert seed_lib.get_db_file() == str(user_dir / "library.db")


def test_absolute_name_from_settings_is_kept(user_dir, tmp_path):
    target = tmp_path / "elsewhere.db"
    user_dir.mkdir()
    (user_dir / "settings.yml").write_text(
        f"database_tags_file: {target.as_posix()}\n", encoding="utf-8"
    )
    assert Path(seed_lib.get_db_file()) == target


def test_linux_seed_uses_same_resolution(user_dir):
    assert seed_linux_commands.get_db_file() == seed_lib.get_db_file()


def test_backup_cli_uses_data_dir(user_dir):
    assert backup_db._db_file(None) == str(user_dir / "mytags.db")


def test_language_and_backup_dir_from_data_dir_settings(user_dir, monkeypatch):
    user_dir.mkdir()
    (user_dir / "settings.yml").write_text(
        "database_tags_file: mytags.db\nlanguage: ru\nbackup_dir: snaps\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("IDVJPY_LANG", raising=False)
    seed_lib.reset_seed_text_cache()

    db_file = seed_lib.get_db_file()
    assert seed_lib.resolve_seed_language(db_file) == "ru"
    assert seed_lib.backup_dir_for(db_file) == user_dir / "snaps"


def test_seed_cli_default_and_explicit_db(user_dir, tmp_path, monkeypatch):
    seen: list[str] = []
    monkeypatch.setattr(seed_lib, "run_seed", lambda db, tags, **kw: seen.append(db) or 0)
    tags = {"t": ("comment", [("echo hi", "")])}

    seed_lib.seed_cli(
        description="fake", seed_help="seed", seed_tags=tags, argv=["seed_fake.py", "--seed"]
    )
    explicit = str(tmp_path / "explicit.db")
    seed_lib.seed_cli(
        description="fake",
        seed_help="seed",
        seed_tags=tags,
        argv=["seed_fake.py", "--seed", "--db", explicit],
    )

    assert seen == [str(user_dir / "mytags.db"), explicit]
