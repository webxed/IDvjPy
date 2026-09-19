"""CLI `backup_db.py`: тонкая оболочка над `src/db_transfer.py`.

Раньше у CLI была своя SQL-обвязка и своя JSON-схема (`schema_version: v2` при
другом наборе полей), и ни одного теста. Здесь проверяем round-trip, режимы,
адресный CSV, `list`, `backup`/`restore` и что глобальные `id` не переносятся.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import backup_db
import database_v2 as database


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Рабочий каталог с settings.yml и базой — как у CLI (пути от cwd)."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "settings.yml").write_text(
        "database_tags_file: mytags.db\nbackup_dir: backups\n", encoding="utf-8"
    )
    db = tmp_path / "mytags.db"
    database.init_db(str(db))
    database.add_command(str(db), "kubectl get pods", "kube")
    database.add_command(str(db), "echo done", "mine")
    database.set_tag_comment(str(db), "kube", "k8s команды")
    return tmp_path


def test_export_import_round_trip(data_dir, capsys):
    assert backup_db.main(["export", "backup.json"]) == 0
    out = capsys.readouterr().out
    assert "Exported 2 commands" in out
    path = data_dir / "backups" / "backup.json"
    assert path.is_file()

    database.delete_commands_by_tag(str(data_dir / "mytags.db"), "kube")
    assert backup_db.main(["import", "backup.json"]) == 0
    out = capsys.readouterr().out
    assert "Imported: 1" in out  # kube вернулся, mine уже был (skip_existing)
    rows = database.get_commands_by_tag(str(data_dir / "mytags.db"), "kube")
    assert [row["command"] for row in rows] == ["kubectl get pods"]


def test_export_tag_filter_and_list(data_dir, capsys):
    assert backup_db.main(["export", "kube.json", "--tag", "kube"]) == 0
    payload = json.loads((data_dir / "backups" / "kube.json").read_text(encoding="utf-8"))
    assert payload["tag_filter"] == "kube"
    assert payload["total_commands"] == 1

    assert backup_db.main(["list", "--show-comments"]) == 0
    out = capsys.readouterr().out
    assert "  [kube] 1 commands - k8s команды" in out
    assert "  [mine] 1 commands" in out
    assert "Total: 2 commands" in out


def test_import_replace_mode_and_keep_tids(data_dir, capsys):
    assert backup_db.main(["export", "kube.json", "--tag", "kube"]) == 0
    capsys.readouterr()
    assert backup_db.main(["import", "kube.json", "--mode", "replace", "--keep-tids"]) == 0
    out = capsys.readouterr().out
    assert "Imported: 1" in out
    db = data_dir / "mytags.db"
    assert database.get_all_tags(str(db)) == ["kube"]
    assert database.get_commands_by_tag(str(db), "kube")[0]["tid"] == 1


def test_missing_file_reports_error(data_dir, capsys):
    assert backup_db.main(["import", "nope.json"]) == 1
    assert "File not found: nope.json" in capsys.readouterr().err


def test_csv_round_trip_is_addressable(data_dir, capsys):
    assert backup_db.main(["export-csv", "commands.csv"]) == 0
    csv_path = data_dir / "backups" / "commands.csv"
    lines = csv_path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "tag;tid;command;comment"
    lines[1] = "kube;1;kubectl get pods -A;новая правка"
    csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert backup_db.main(["import-csv", "commands.csv"]) == 0
    out = capsys.readouterr().out
    assert "Updated:  2" in out
    rows = database.get_commands_by_tag(str(data_dir / "mytags.db"), "kube")
    assert rows[0]["command"] == "kubectl get pods -A"
    assert len(rows) == 1


def test_tags_csv_round_trip(data_dir, capsys):
    assert backup_db.main(["export-tags-csv", "tags.csv"]) == 0
    tags_csv = data_dir / "backups" / "tags.csv"
    tags_csv.write_text("tag;comment\nkube;переписан\n", encoding="utf-8")
    assert backup_db.main(["import-tags-csv", "tags.csv"]) == 0
    assert "1 tag comment(s)" in capsys.readouterr().out
    assert database.get_tag_comment(str(data_dir / "mytags.db"), "kube") == "переписан"


def test_backup_makes_snapshot_and_transfers(data_dir, capsys):
    assert backup_db.main(["backup"]) == 0
    out = capsys.readouterr().out
    assert "SQLite snapshot:" in out and "JSON:" in out
    backups = sorted(p.name for p in (data_dir / "backups").iterdir())
    assert any(name.endswith(".db") for name in backups)
    assert any(name.endswith(".json") for name in backups)
    assert any(name.startswith("commands_") for name in backups)
    assert any(name.startswith("tags_") for name in backups)


def test_backup_refuses_empty_database(data_dir, capsys, monkeypatch):
    monkeypatch.chdir(data_dir)
    (data_dir / "mytags.db").unlink()
    (data_dir / "empty.db").write_text("", encoding="utf-8")
    database.init_db(str(data_dir / "empty.db"))
    assert backup_db.main(["backup", "--db", "empty.db"]) == 1
    assert "Nothing to backup" in capsys.readouterr().err


def test_restore_snapshots_before_and_imports(data_dir, capsys):
    assert backup_db.main(["export", "kube.json", "--tag", "kube"]) == 0
    capsys.readouterr()
    database.delete_commands_by_tag(str(data_dir / "mytags.db"), "kube")

    assert backup_db.main(["restore", "kube.json"]) == 0
    out = capsys.readouterr().out
    assert "Snapshot before restore:" in out
    assert "Imported: 1" in out
    db = data_dir / "mytags.db"
    assert any("kubectl get pods" in row["command"] for row in database.get_commands_by_tag(str(db), "kube"))
    assert any(p.suffix == ".db" for p in (data_dir / "backups").iterdir())


def test_restore_accepts_csv_by_header(data_dir, capsys):
    assert backup_db.main(["export-tags-csv", "tags.csv"]) == 0
    capsys.readouterr()
    assert backup_db.main(["restore", "tags.csv"]) == 0
    assert "Updated:  1" in capsys.readouterr().out


def test_restore_rejects_unknown_extension(data_dir, capsys):
    bad = data_dir / "file.txt"
    bad.write_text("nope", encoding="utf-8")
    assert backup_db.main(["restore", str(bad)]) == 1
    assert "unsupported file type" in capsys.readouterr().err


def test_import_does_not_take_global_ids(data_dir, capsys):
    """Чужой `id` из файла не может затереть другую строку (было так у CLI)."""
    foreign = data_dir / "foreign.json"
    foreign.write_text(
        json.dumps({
            "tag_filter": "big",
            "commands": [{"id": 1, "tag": "big", "tid": 1, "command": "echo hijack"}],
        }),
        encoding="utf-8",
    )
    assert backup_db.main(["import", str(foreign)]) == 0
    db = data_dir / "mytags.db"
    assert database.get_command_by_global_id(str(db), 1)["command"] == "kubectl get pods"
    assert database.get_commands_by_tag(str(db), "big")[0]["command"] == "echo hijack"


def test_help_lists_every_command(capsys):
    with pytest.raises(SystemExit):
        backup_db.main(["--help"])
    out = capsys.readouterr().out
    for command in (
        "export", "import", "export-csv", "import-csv",
        "export-tags-csv", "import-tags-csv", "list", "backup", "restore",
    ):
        assert command in out


def test_shell_wrapper_is_thin():
    """`backup_db.sh` не содержит своей логики — только вызов CLI."""
    body = Path("backup_db.sh").read_text(encoding="utf-8")
    assert "backup_db.py backup" in body
    assert "backup_db.py restore" in body
    assert "export-csv" not in body, "обёртка не должна повторять команды CLI"
