from __future__ import annotations

import json
import sqlite3

import pytest

import database_v2 as database
import db_transfer


def test_metadata_migrates_existing_tags_table(tmp_path):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE tags (tag TEXT PRIMARY KEY, comment TEXT)")
    conn.execute("INSERT INTO tags VALUES ('git', 'Git commands')")
    conn.commit()
    conn.close()

    database.init_db(str(path))
    assert database.get_tag_comment(str(path), "git") == "Git commands"
    assert database.get_tag_metadata(str(path), "git") == {}


def test_metadata_validation_and_storage(tmp_path):
    path = str(tmp_path / "tags.db")
    database.init_db(path)
    metadata = {"risk": "medium", "utilities": ["git"], "os": ["linux"], "interactive": False, "topic": "inspection", "example": "git status"}
    database.set_tag_metadata(path, "git", metadata)
    assert database.get_tag_metadata(path, "git") == metadata
    with pytest.raises(ValueError, match="risk"):
        database.set_tag_metadata(path, "git", {"risk": "extreme"})
    with pytest.raises(ValueError, match="unknown"):
        database.set_tag_metadata(path, "git", {"secret": "not allowed"})


def test_metadata_transfer_round_trip_and_old_payload(tmp_path):
    source = str(tmp_path / "source.db")
    target = str(tmp_path / "target.db")
    database.init_db(source)
    database.add_command(source, "git status", "git")
    database.set_tag_comment(source, "git", "Git")
    metadata = {"risk": "low", "utilities": ["git"]}
    database.set_tag_metadata(source, "git", metadata)
    export = tmp_path / "export.json"
    db_transfer.export_json(source, str(export), tag="git")
    payload = json.loads(export.read_text(encoding="utf-8"))
    assert payload["tag_metadata"] == {"git": metadata}
    db_transfer.import_payload(target, payload)
    assert database.get_tag_metadata(target, "git") == metadata
    db_transfer.import_payload(target, {"commands": [{"tag": "old", "command": "true"}]})
    assert database.get_tag_metadata(target, "old") == {}


def test_metadata_import_rejects_invalid_object(tmp_path):
    with pytest.raises(ValueError, match="risk"):
        db_transfer.import_payload(str(tmp_path / "db.sqlite"), {
            "commands": [], "tag_metadata": {"git": {"risk": "unknown"}}
        })
