"""Empty-database welcome lists every handbook seed."""
from seed_catalog import (
    SEED_HANDBOOKS_CORE,
    SEED_HANDBOOKS_OPS,
    format_empty_db_hint,
    seed_invoke,
)
from seed_groups import group_for_tag, group_tags, handbook_groups, known_group_names


def test_format_empty_db_hint_lists_core_ops_and_bundle():
    text = format_empty_db_hint("mytags.db")
    assert "Empty command database" in text
    assert "(mytags.db)" in text
    assert seed_invoke("seed_ops.py") in text
    assert "open_handbook_md" in text
    assert "insert_seed_command" in text
    assert "insert_seed_command('seed_ops.py')" in text
    assert ":md файл.md" in text
    assert ":welcome" in text
    assert "backups/" in text
    assert ":backup" in text
    for script, desc, doc in SEED_HANDBOOKS_CORE + SEED_HANDBOOKS_OPS:
        assert seed_invoke(script) in text
        assert desc in text
        assert doc in text
        assert f"open_handbook_md('{doc}')" in text
        assert f"insert_seed_command('{script}')" in text


def test_format_library_overview_groups_handbook_and_custom():
    from seed_catalog import format_library_overview

    text = format_library_overview(["proc", "kpod", "mine", "hls"])
    assert "Разделы" in text
    assert ":welcome" in text
    assert "linux" in text
    assert "proc" in text
    assert "k8s" in text
    assert "kpod" in text
    assert "helm" in text
    assert "hls" in text
    assert "свои" in text
    assert "mine" in text
    assert "file" not in text
    assert "Empty command database" not in text
    assert format_library_overview([]) == ""


def test_handbook_groups_cover_core_and_ops():
    groups = handbook_groups()
    assert "linux" in groups
    assert "proc" in groups["linux"]
    assert "k8s" in groups
    assert "kpod" in groups["k8s"]
    assert "git" in groups
    assert "helm" in groups
    assert "hls" in groups["helm"]
    assert "ansible" in groups
    assert group_tags("nonesuch") is None
    assert group_for_tag("hls") == "helm"
    assert group_for_tag("custom") is None
    names = known_group_names()
    assert names == sorted(groups)
    assert "linux" in names and "sysstat" in names


def test_handbook_md_path_resolves_repo_docs():
    from md_viewer import handbook_md_path

    path = handbook_md_path("SEED_LINUX_COMMANDS.md")
    assert path is not None
    assert path.name == "SEED_LINUX_COMMANDS.md"
    assert path.is_file()
    assert handbook_md_path("../etc/passwd") is None
    assert handbook_md_path("nope.txt") is None
    assert handbook_md_path("") is None
