"""--seed copies a live SQLite DB into backups/ before replacing tags."""
import database_v2 as database
import seed_git
import seed_lib
import seed_ops


def setup_function() -> None:
    seed_lib.reset_seed_backup_cache()


def test_seed_backs_up_live_db_before_replace(tmp_path):
    db = str(tmp_path / "mytags.db")
    database.init_db(db)
    database.add_command(db, "echo keep-me", "mine")
    database.add_command(db, "git status --porcelain", "git")

    seed_git.run_seed(db)

    snaps = list((tmp_path / "backups").glob("mytags-pre-git-*.db"))
    assert len(snaps) == 1
    snap = str(snaps[0])
    assert database.get_command_by_tid(snap, "mine", 1)["command"] == "echo keep-me"
    assert "porcelain" in database.get_command_by_tid(snap, "git", 1)["command"]

    assert database.get_command_by_tid(db, "mine", 1)["command"] == "echo keep-me"
    assert database.get_command_by_tid(db, "git", 1)["command"] == "git status"


def test_seed_skips_backup_when_db_empty(tmp_path):
    db = str(tmp_path / "empty.db")
    seed_git.run_seed(db)
    backup_dir = tmp_path / "backups"
    assert not backup_dir.exists() or not list(backup_dir.glob("*.db"))


def test_seed_ops_writes_one_backup(tmp_path):
    db = str(tmp_path / "ops.db")
    database.init_db(db)
    database.add_command(db, "echo custom", "mine")
    seed_ops.run_seed(db)
    snaps = list((tmp_path / "backups").glob("ops-pre-ops-*.db"))
    assert len(snaps) == 1
    assert database.get_command_by_tid(str(snaps[0]), "mine", 1)["command"] == "echo custom"
    assert database.get_command_by_tid(db, "mine", 1)["command"] == "echo custom"
    assert not list((tmp_path / "backups").glob("ops-pre-docker-*.db"))
    assert not list((tmp_path / "backups").glob("ops-pre-seed-*.db"))


def test_manual_backup_ignores_seed_once_cache(tmp_path):
    db = str(tmp_path / "mytags.db")
    database.init_db(db)
    database.add_command(db, "echo keep-me", "mine")
    seed_git.run_seed(db)
    dest = seed_lib.backup_sqlite(db, "manual", quiet=True)
    assert dest is not None
    assert dest.name.startswith("mytags-manual-")
    assert database.get_command_by_tid(str(dest), "mine", 1)["command"] == "echo keep-me"
    pre = list((tmp_path / "backups").glob("mytags-pre-git-*.db"))
    manual = list((tmp_path / "backups").glob("mytags-manual-*.db"))
    assert len(pre) == 1
    assert len(manual) == 1
