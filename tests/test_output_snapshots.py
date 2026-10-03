from __future__ import annotations

import json

from app import CommandRunner
from output_snapshots import (
    MAX_SNAPSHOT_BYTES,
    MAX_SNAPSHOTS,
    SNAPSHOT_FILE,
    delete_snapshot,
    load_snapshots,
    save_snapshot,
)
from tests.conftest import last_info, submit, wait_command_done


def test_snapshot_round_trip_private_and_replace(tmp_path):
    assert save_snapshot(str(tmp_path), "baseline", "a\nb\n", created="now") is None
    assert save_snapshot(str(tmp_path), "baseline", "updated\n", created="later") is None
    rows, error = load_snapshots(str(tmp_path))
    assert error == ""
    assert rows == [{"name": "baseline", "created": "later", "text": "updated\n", "truncated": False}]
    assert (tmp_path / SNAPSHOT_FILE).stat().st_mode & 0o777 == 0o600
    assert delete_snapshot(str(tmp_path), "baseline") is None
    assert not (tmp_path / SNAPSHOT_FILE).exists()


def test_snapshot_text_is_truncated_and_count_is_bounded(tmp_path):
    assert save_snapshot(str(tmp_path), "large", "é" * (MAX_SNAPSHOT_BYTES // 2 + 10), created="now") is None
    rows, error = load_snapshots(str(tmp_path))
    assert error == ""
    assert len(rows[0]["text"].encode("utf-8")) <= MAX_SNAPSHOT_BYTES
    assert rows[0]["truncated"] is True
    for index in range(1, MAX_SNAPSHOTS):
        assert save_snapshot(str(tmp_path), f"s{index}", "x", created="now") is None
    assert save_snapshot(str(tmp_path), "overflow", "x", created="now") is not None


def test_snapshot_rejects_corrupt_or_oversized_store(tmp_path):
    path = tmp_path / SNAPSHOT_FILE
    path.write_text("not json", encoding="utf-8")
    rows, error = load_snapshots(str(tmp_path))
    assert rows == []
    assert "output_snapshots.json" in error
    oversized = [
        {"name": f"s{index}", "created": "now", "text": "x" * MAX_SNAPSHOT_BYTES, "truncated": False}
        for index in range(MAX_SNAPSHOTS)
    ]
    path.write_text(json.dumps(oversized), encoding="utf-8")
    rows, error = load_snapshots(str(tmp_path))
    assert rows == []
    assert "exceeds" in error


async def test_snapshot_command_saves_and_diffs(isolated_home, tmp_path):
    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        app._data_dir = str(tmp_path)
        await submit(pilot, "printf 'before\\n'")
        await wait_command_done(app, timeout=8.0)
        await submit(pilot, ":snapshot save before")
        assert "snapshot saved" in last_info(app).text_content.lower()
        await submit(pilot, "printf 'after\\n'")
        await wait_command_done(app, timeout=8.0)
        await submit(pilot, ":snapshot diff before")
        text = last_info(app).text_content
        assert "Snapshot diff" in text
        assert "before" in text
        assert "after" in text


async def test_snapshot_only_persists_masked_stdout(isolated_home, tmp_path):
    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        app._data_dir = str(tmp_path)
        app.local_env["SNAP_SECRET"] = "never-persist-this"
        app._secret_names.add("SNAP_SECRET")
        await submit(pilot, "printf '%s\\n' never-persist-this")
        await wait_command_done(app, timeout=8.0)
        await submit(pilot, ":snapshot save protected")
        saved = (tmp_path / SNAPSHOT_FILE).read_text(encoding="utf-8")
        assert "never-persist-this" not in saved
        assert "[secret]" in saved or "***" in saved
