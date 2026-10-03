"""Аудит библиотеки хранит метаданные операций, но не содержимое библиотеки."""
from __future__ import annotations

import json
import os

import db_transfer
import library_audit


def test_record_event_contains_only_metadata_and_private_file(tmp_path):
    error = library_audit.record_event(
        str(tmp_path), "import", tags=["git", "db", "git"], count=3
    )
    assert error is None
    path = tmp_path / library_audit.AUDIT_FILE
    event = json.loads(path.read_text(encoding="utf-8"))
    assert set(event) == {"timestamp", "action", "count", "tags"}
    assert event["action"] == "import"
    assert event["count"] == 3
    assert event["tags"] == ["db", "git"]
    assert not os.name == "posix" or path.stat().st_mode & 0o777 == 0o600


def test_content_and_source_url_are_not_recorded(tmp_path):
    command = "curl https://example.test/?token=hidden"
    comment = "user supplied comment"
    assert library_audit.record_event(str(tmp_path), "save", tags=["demo"], count=1) is None
    raw = (tmp_path / library_audit.AUDIT_FILE).read_text(encoding="utf-8")
    assert command not in raw
    assert comment not in raw
    assert "https://" not in raw
    assert "hidden" not in raw


def test_read_events_limits_and_skips_malformed_lines(tmp_path):
    path = tmp_path / library_audit.AUDIT_FILE
    path.write_text(
        "not json\n"
        + json.dumps({"timestamp": "t", "action": "save", "count": 1, "tags": ["demo"]})
        + "\n",
        encoding="utf-8",
    )
    events, error = library_audit.read_events(str(tmp_path), 1)
    assert error == ""
    assert events == [{"timestamp": "t", "action": "save", "count": 1, "tags": ["demo"]}]


def test_invalid_action_and_control_tag_are_rejected(tmp_path):
    assert library_audit.record_event(str(tmp_path), "unknown", tags=[], count=1)
    assert library_audit.record_event(str(tmp_path), "save", tags=["git\nforged"], count=1)
    assert not (tmp_path / library_audit.AUDIT_FILE).exists()


def test_import_payload_records_only_aggregate_metadata(tmp_path):
    db = str(tmp_path / "mytags.db")
    payload = {
        "commands": [{"tag": "demo", "tid": 1, "command": "echo private-command", "comment": "private-comment"}],
        "tag_comments": {"demo": "private-tag-comment"},
    }
    result = db_transfer.import_payload(db, payload)
    assert result.imported == 1
    raw = (tmp_path / library_audit.AUDIT_FILE).read_text(encoding="utf-8")
    event = json.loads(raw)
    assert event["action"] == "import" and event["count"] == 1
    assert event["tags"] == ["demo"]
    for private in ("private-command", "private-comment", "private-tag-comment"):
        assert private not in raw
