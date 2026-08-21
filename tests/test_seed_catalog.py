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
    assert text.startswith("Empty command database (mytags.db).")
    assert seed_invoke("seed_ops.py") in text
    for script, desc in SEED_HANDBOOKS_CORE + SEED_HANDBOOKS_OPS:
        assert seed_invoke(script) in text
        assert desc in text


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
