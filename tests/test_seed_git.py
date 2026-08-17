"""seed_git.py: фиксированные tid и плейбуки gstat/gsync."""
from pathlib import Path

import database_v2 as database
from seed_git import SEED_TAGS, run_seed


def test_seed_git_tids_and_playbooks(tmp_path):
    db = str(tmp_path / "git.db")
    n = run_seed(db)
    expected = sum(len(cmds) for _, cmds in SEED_TAGS.values())
    assert n == expected

    rows = database.get_commands_by_tag(db, "git")
    assert rows[0]["command"] == "git status"
    assert rows[1]["command"] == "git status -sb"
    assert "--no-pager" in rows[2]["command"]
    assert "fetch --all --prune" in rows[17]["command"]  # tid 18
    assert "reflog" in rows[35]["command"]  # tid 36

    gstat = database.get_command_by_tid(db, "gstat", 1)
    assert "!git[2]" in gstat["command"]
    assert "!git[11]" in gstat["command"]
    assert "!git[6]" in gstat["command"]

    gsync = database.get_command_by_tid(db, "gsync", 1)
    assert "!git[18]" in gsync["command"]

    gdiff = database.get_command_by_tid(db, "gdiff", 1)
    assert "!git[3]" in gdiff["command"]
    assert "!git[4]" in gdiff["command"]

    gundo = database.get_command_by_tid(db, "gundo", 1)
    assert "!git[36]" in gundo["command"]
    assert "reset" not in gundo["command"]

    assert database.get_tag_comment(db, "git")
    assert "короткий status" in database.get_command_comment(db, "git", 2)


def test_seed_git_does_not_touch_linux_or_k8s(tmp_path):
    db = str(tmp_path / "mixed.db")
    database.init_db(db)
    database.add_command(db, "ps aux", "proc")
    database.add_command(db, "kubectl get pods -n $NS", "kpod")
    run_seed(db)
    assert database.get_command_by_tid(db, "proc", 1)["command"] == "ps aux"
    assert "kubectl get pods" in database.get_command_by_tid(db, "kpod", 1)["command"]


def test_seed_git_cli(tmp_path, monkeypatch):
    import seed_git as seed

    db = str(tmp_path / "cli.db")
    monkeypatch.setattr(
        seed.sys,
        "argv",
        ["seed_git.py", "--seed", "--db", db],
    )
    seed.main()
    assert Path(db).exists()
    assert database.get_command_by_tid(db, "git", 1) is not None
