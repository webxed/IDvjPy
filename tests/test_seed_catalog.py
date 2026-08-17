"""Empty-database welcome lists every handbook seed."""
from seed_catalog import (
    SEED_HANDBOOKS_CORE,
    SEED_HANDBOOKS_OPS,
    format_empty_db_hint,
    seed_invoke,
)


def test_format_empty_db_hint_lists_core_ops_and_bundle():
    text = format_empty_db_hint("mytags.db")
    assert text.startswith("Empty command database (mytags.db).")
    assert seed_invoke("seed_ops.py") in text
    for script, desc in SEED_HANDBOOKS_CORE + SEED_HANDBOOKS_OPS:
        assert seed_invoke(script) in text
        assert desc in text
