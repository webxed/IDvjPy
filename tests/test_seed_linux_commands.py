"""seed_linux_commands.py: канонические tid и комментарии."""
import database_v2 as database
from seed_linux_commands import apply_comments, run_seed


def test_seed_linux_commands_sets_comments(tmp_path):
    db = str(tmp_path / "linux.db")
    n = run_seed(db)
    assert n == 10 + 11 + 9 + 19
    row = database.get_command_by_tid(db, "proc", 1)
    assert row["command"] == "ps aux"
    assert database.get_command_comment(db, "proc", 1) == "list processes"
    assert database.get_command_comment(db, "kube", 7) == "pods in namespace $NS"
    assert database.get_tag_comment(db, "file") == "Files and directories"


def test_apply_comments_fills_empty_keeps_extras(tmp_path):
    db = str(tmp_path / "live.db")
    database.init_db(db)
    database.add_command(db, "ps aux", "proc")
    database.add_command(db, "ll /var/log/", "logs")
    n = apply_comments(db)
    assert n >= 2
    assert database.get_command_comment(db, "proc", 1) == "list processes"
    assert database.get_command_comment(db, "logs", 1) == "list files in /var/log"
    database.set_command_comment(db, "proc", 1, "уже было")
    apply_comments(db, only_empty=True)
    assert database.get_command_comment(db, "proc", 1) == "уже было"
