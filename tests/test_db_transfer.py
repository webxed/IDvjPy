"""Перенос библиотеки: `src/db_transfer.py` — один код для TUI и CLI.

Проверяем оба исторических вида JSON (старый TUI писал меньше полей, CLI —
больше, а `schema_version` был одинаковым), безопасный импорт без переноса
глобальных `id`, режимы merge/replace, адресный CSV по tid и Markdown-каталог.
"""
from __future__ import annotations

import json

import database_v2 as database
import db_transfer


def _seed(db) -> None:
    database.init_db(str(db))
    database.add_command(str(db), "kubectl get pods", "kube")
    database.add_command(str(db), "kubectl get svc", "kube")
    database.add_command(str(db), "echo done", "mine")
    database.set_tag_comment(str(db), "kube", "k8s команды")
    database.set_command_comment(str(db), "mine", 1, "проверка")


def test_export_json_is_canonical(tmp_path):
    db = tmp_path / "db.sqlite"
    _seed(db)
    out = tmp_path / "out.json"
    assert db_transfer.export_json(str(db), str(out)) == 3
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["version"] == db_transfer.JSON_VERSION
    assert payload["schema_version"] == db_transfer.JSON_SCHEMA_VERSION
    assert payload["total_commands"] == 3
    assert payload["total_tags"] == 1
    assert payload["tag_comments"] == {"kube": "k8s команды"}
    assert payload["export_date"]
    row = payload["commands"][0]
    assert set(row) == {"id", "tag", "tid", "command", "timestamp", "deleted", "comment"}


def test_export_json_single_tag(tmp_path):
    db = tmp_path / "db.sqlite"
    _seed(db)
    out = tmp_path / "kube.json"
    assert db_transfer.export_json(str(db), str(out), tag="kube") == 2
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["tag_filter"] == "kube"
    assert {row["tag"] for row in payload["commands"]} == {"kube"}


def test_import_reads_old_tui_payload(tmp_path):
    """Старый вид (без id/timestamp/export_date) читается: поля необязательны."""
    db = tmp_path / "db.sqlite"
    database.init_db(str(db))
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps({
        "version": "2.0",
        "schema_version": "v2",
        "tag_filter": "ship",
        "tag_comments": {"ship": "про корабль"},
        "commands": [
            {"tag": "ship", "tid": 1, "command": "echo cargo", "comment": "груз"},
            {"tag": "ship", "tid": 2, "command": "echo deck"},
        ],
    }, ensure_ascii=False), encoding="utf-8")
    payload = db_transfer.read_json(str(path))
    assert db_transfer.payload_tag(payload) == "ship"
    result = db_transfer.import_json(str(db), str(path), only_tag="ship")
    assert (result.imported, result.skipped) == (2, 0)
    rows = database.get_commands_by_tag(str(db), "ship")
    assert [row["command"] for row in rows] == ["echo cargo", "echo deck"]
    assert rows[0]["comment"] == "груз"
    assert database.get_tag_comment(str(db), "ship") == "про корабль"


def test_import_never_grafts_global_ids(tmp_path):
    """Глобальные id из файла не переносятся — иначе чужая строка затирается."""
    db = tmp_path / "db.sqlite"
    _seed(db)
    existing = database.get_command_by_global_id(str(db), 1)
    assert existing is not None
    path = tmp_path / "foreign.json"
    path.write_text(json.dumps({
        "tag_filter": "big",
        "commands": [{"id": 1, "tag": "big", "tid": 1, "command": "echo hijack"}],
    }), encoding="utf-8")
    result = db_transfer.import_json(str(db), str(path), only_tag="big")
    assert result.imported == 1
    # Строка с id=1 уцелела, а не превратилась в echo hijack.
    assert database.get_command_by_global_id(str(db), 1)["command"] == "kubectl get pods"


def test_import_skip_existing_is_idempotent(tmp_path):
    db = tmp_path / "db.sqlite"
    _seed(db)
    out = tmp_path / "kube.json"
    db_transfer.export_json(str(db), str(out), tag="kube")
    first = db_transfer.import_json(str(db), str(out), only_tag="kube")
    assert first.imported == 2  # новые tid
    second = db_transfer.import_json(
        str(db), str(out), only_tag="kube", preserve_tid=True, skip_existing=True
    )
    assert (second.imported, second.skipped) == (0, 2)


def test_import_replace_clears_library(tmp_path):
    db = tmp_path / "db.sqlite"
    _seed(db)
    out = tmp_path / "kube.json"
    db_transfer.export_json(str(db), str(out), tag="kube")
    result = db_transfer.import_json(str(db), str(out), mode="replace", only_tag="kube")
    assert result.imported == 2
    assert database.get_all_tags(str(db)) == ["kube"]
    assert len(database.get_commands_by_tag(str(db), "kube")) == 2


def test_import_skips_soft_deleted_rows(tmp_path):
    db = tmp_path / "db.sqlite"
    _seed(db)
    database.delete_command_by_tid(str(db), "kube", 1)
    out = tmp_path / "kube.json"
    db_transfer.export_json(str(db), str(out), tag="kube", include_deleted=True)
    result = db_transfer.import_json(str(db), str(out), only_tag="kube")
    assert result.skipped == 1
    assert result.imported == 1


def test_commands_csv_round_trip_is_addressable(tmp_path):
    """CSV-импорт адресует строку парой (тег, tid): существующая правится, новой — insert."""
    db = tmp_path / "db.sqlite"
    _seed(db)
    csv_path = tmp_path / "commands.csv"
    assert db_transfer.export_commands_csv(str(db), str(csv_path)) == 3
    text = csv_path.read_text(encoding="utf-8").splitlines()
    assert text[0] == "tag;tid;command;comment"
    text[1] = "kube;1;kubectl get pods -A;правка"
    csv_path.write_text("\n".join(text) + "\n", encoding="utf-8")
    result = db_transfer.import_commands_csv(str(db), str(csv_path))
    assert (result.updated, result.imported) == (3, 0)
    rows = database.get_commands_by_tag(str(db), "kube")
    assert rows[0]["command"] == "kubectl get pods -A"
    assert rows[0]["comment"] == "правка"
    assert len(rows) == 2  # новых строк не появилось


def test_tags_csv_round_trip(tmp_path):
    db = tmp_path / "db.sqlite"
    _seed(db)
    csv_path = tmp_path / "tags.csv"
    assert db_transfer.export_tags_csv(str(db), str(csv_path)) == 1
    csv_path.write_text("tag;comment\nkube;новый текст\n", encoding="utf-8")
    result = db_transfer.import_tags_csv(str(db), str(csv_path))
    assert result.updated == 1
    assert database.get_tag_comment(str(db), "kube") == "новый текст"


def test_csv_schema_detects_tags_and_commands(tmp_path):
    commands = tmp_path / "c.csv"
    tags = tmp_path / "t.csv"
    commands.write_text("tag;tid;command;comment\nkube;1;ls;\n", encoding="utf-8")
    tags.write_text("tag;comment\nkube;текст\n", encoding="utf-8")
    assert db_transfer.csv_schema(str(commands)) == "commands"
    assert db_transfer.csv_schema(str(tags)) == "tags"


def test_markdown_catalog(tmp_path):
    db = tmp_path / "db.sqlite"
    _seed(db)
    out = tmp_path / "library.md"
    assert db_transfer.export_markdown(str(db), str(out)) == 3
    body = out.read_text(encoding="utf-8")
    assert "## kube — k8s команды" in body
    assert "- `echo done`  — проверка" in body


def test_library_overview(tmp_path):
    db = tmp_path / "db.sqlite"
    _seed(db)
    assert db_transfer.library_overview(str(db)) == [
        ("kube", 2, "k8s команды"),
        ("mine", 1, ""),
    ]


def test_export_and_import_paths(tmp_path):
    backups = tmp_path / "backups"
    assert db_transfer.export_path("out.json", str(backups)) == str(backups / "out.json")
    assert db_transfer.export_path("./here.json", str(backups)) == "here.json"
    # Импорт ищет относительное имя в backups/, а указанный существующий путь — как есть.
    (backups / "x.json").write_text("{}", encoding="utf-8")
    assert db_transfer.import_path("x.json", str(backups)) == str(backups / "x.json")
    local = tmp_path / "local.json"
    local.write_text("{}", encoding="utf-8")
    assert db_transfer.import_path(str(local), str(backups)) == str(local)
