"""seed_k8s_chains.py кладёт фиксированные tid, плейбуки ссылаются на kpod/klog/…"""
from pathlib import Path

import database_v2 as database
from seed_k8s_chains import SEED_TAGS, run_seed


def test_seed_k8s_chains_tids_and_playbook_refs(tmp_path):
    db = str(tmp_path / "k8s_chains.db")
    n = run_seed(db)
    expected = sum(len(cmds) for _, cmds in SEED_TAGS.values())
    assert n == expected

    kpod = database.get_commands_by_tag(db, "kpod")
    assert kpod[1]["command"].startswith("kubectl get pods")
    assert "status.phase!=Running" in kpod[1]["command"]  # tid 2
    assert "describe pod $POD" in kpod[3]["command"]  # tid 4

    klog = database.get_commands_by_tag(db, "klog")
    assert "--previous" in klog[2]["command"]  # tid 3

    kev = database.get_commands_by_tag(db, "kev")
    assert "involvedObject.name=$POD" in kev[1]["command"]  # tid 2

    crash = database.get_command_by_tid(db, "kcrash", 1)
    assert "!kpod[2]" in crash["command"]
    assert "!kpod[4]" in crash["command"]
    assert "!klog[3]" in crash["command"]
    assert "!kev[2]" in crash["command"]

    net = database.get_command_by_tid(db, "knet", 1)
    assert "!ksvc[1]" in net["command"]
    assert "!kpod[3]" in net["command"]

    roll = database.get_command_by_tid(db, "kroll", 1)
    assert "!kdep[2]" in roll["command"]
    assert "!kdep[6]" in roll["command"]

    watch = database.get_command_by_tid(db, "kwatch", 1)
    assert "!kpod[1]" in watch["command"]
    assert "!kev[3]" in watch["command"]

    assert database.get_tag_comment(db, "kcrash")
    assert "CrashLoop" in database.get_command_comment(db, "kcrash", 1)


def test_seed_k8s_chains_does_not_touch_kube(tmp_path):
    db = str(tmp_path / "mixed.db")
    database.init_db(db)
    database.add_command(db, "kubectl get pods -n $NS", "kube")
    run_seed(db)
    kube = database.get_commands_by_tag(db, "kube")
    assert len(kube) == 1
    assert kube[0]["command"] == "kubectl get pods -n $NS"


def test_seed_k8s_chains_cli(tmp_path, monkeypatch):
    import seed_k8s_chains as seed

    db = str(tmp_path / "cli.db")
    monkeypatch.setattr(seed, "get_db_file", lambda: db)
    monkeypatch.setattr(
        seed.sys,
        "argv",
        ["seed_k8s_chains.py", "--seed", "--db", db],
    )
    seed.main()
    assert Path(db).exists()
    assert database.get_command_by_tid(db, "kpod", 1) is not None
