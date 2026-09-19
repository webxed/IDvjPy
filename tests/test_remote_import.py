"""`:import <url>` — библиотека тегов по ссылке, с планом и подтверждением.

Сеть в тестах не трогаем: `remote_source.fetch_text` подменяется, а сам транспорт
проверяется на фейковом `net.open_url`. Отдельно проверяем, что внешний импорт
не пишет в библиотеку без второго явного Enter и предупреждает про `run:auto`.
"""
from __future__ import annotations

import json
import time

import pytest

import db_transfer
import net
import remote_source
from app import CommandRunner, InfoBlock
from runbook import parse_directives
from tests.conftest import input_widget, last_info, submit

LIBRARY = {
    "version": "2.0",
    "schema_version": "v2",
    "tag_comments": {"ship": "корабельные команды"},
    "commands": [
        {"tag": "ship", "tid": 1, "command": "echo cargo", "comment": "груз"},
        {"tag": "ship", "tid": 2, "command": "echo deck"},
        {"tag": "port", "tid": 1, "command": "echo berth"},
    ],
}
LIBRARY_TEXT = json.dumps(LIBRARY, ensure_ascii=False)


class _FakeResponse:
    def __init__(self, chunks: list[bytes]):
        self._chunks = list(chunks)

    def read(self, size: int = -1) -> bytes:
        return self._chunks.pop(0) if self._chunks else b""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _patch_open_url(monkeypatch, chunks: list[bytes]) -> None:
    monkeypatch.setattr(net, "open_url", lambda *a, **k: _FakeResponse(chunks))


def _patch_fetch(monkeypatch, text: str, *, error: str = "") -> dict:
    """Подменить загрузку в TUI-тестах; возвращает счётчик вызовов."""
    calls: dict = {"n": 0}

    def fake(url, **kwargs):
        calls["n"] += 1
        calls["url"] = url
        if error:
            raise remote_source.RemoteError(error)
        return remote_source.FetchResult(url=url, text=text, size=len(text))

    monkeypatch.setattr(remote_source, "fetch_text", fake)
    return calls


async def _wait(pilot, predicate, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        await pilot.pause()
    return predicate()


def _all_info(app) -> str:
    """Текст всех InfoBlock: журнал идёт по блокам, план — не обязательно последний."""
    return "\n".join(block.text_content for block in app.query(InfoBlock))


# --- транспорт (без сети) ----------------------------------------------------


def test_looks_remote():
    assert remote_source.looks_remote("https://host/tags.json")
    assert remote_source.looks_remote("http://host/tags.json")
    assert not remote_source.looks_remote("tags.json")
    assert not remote_source.looks_remote("/tmp/tags.json")
    assert not remote_source.looks_remote("ftp://host/tags.json")


def test_fetch_requires_https(monkeypatch):
    _patch_open_url(monkeypatch, [b"{}"])
    with pytest.raises(remote_source.RemoteError, match="http:// is not encrypted"):
        remote_source.fetch_text("http://host/tags.json")
    with pytest.raises(remote_source.RemoteError, match="Unsupported URL scheme"):
        remote_source.fetch_text("ftp://host/tags.json")


def test_fetch_allows_insecure_when_asked(monkeypatch):
    _patch_open_url(monkeypatch, [b"{}"])
    result = remote_source.fetch_text("http://host/tags.json", allow_insecure=True)
    assert result.text == "{}" and result.size == 2


def test_fetch_reads_chunks_and_enforces_size(monkeypatch):
    _patch_open_url(monkeypatch, [b"a" * 10, b"b" * 10])
    assert remote_source.fetch_text("https://host/x.json", max_bytes=100).size == 20
    _patch_open_url(monkeypatch, [b"a" * 10, b"b" * 10])
    with pytest.raises(remote_source.RemoteError, match="too large"):
        remote_source.fetch_text("https://host/x.json", max_bytes=15)


def test_fetch_wraps_network_error_and_hides_password(monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("Tunnel connection failed: 407 Proxy Authentication Required")

    monkeypatch.setattr(net, "open_url", boom)
    with pytest.raises(remote_source.RemoteError) as excinfo:
        remote_source.fetch_text("https://u:p%40ss@host/x.json", environ={"PROXY_PASS": "p@ss"})
    text = str(excinfo.value)
    assert "Could not fetch https://host/x.json" in text  # userinfo не в журнале
    assert "407" in text and "$PROXY_USER" in text
    assert "p@ss" not in text


def test_fetch_strips_userinfo_in_result():
    assert remote_source.safe_url("https://alice:pw@host/x.json") == "https://host/x.json"


# --- план импорта ------------------------------------------------------------


def test_plan_counts_and_new_tags(tmp_path):
    db = str(tmp_path / "db.sqlite")
    plan = db_transfer.plan_import(db, LIBRARY, source="https://host/lib.json")
    assert plan.commands == 3
    assert plan.new_commands == 3
    assert plan.skipped == 0
    assert plan.new_tags == ("port", "ship")
    assert plan.source == "https://host/lib.json"
    assert not plan.has_run_steps


def test_plan_skip_existing_on_second_pass(tmp_path):
    db = str(tmp_path / "db.sqlite")
    db_transfer.import_payload(db, LIBRARY, skip_existing=True)
    plan = db_transfer.plan_import(
        db, LIBRARY, skip_existing=True, source="https://host/lib.json"
    )
    assert plan.new_commands == 0
    assert plan.skipped == 3
    assert plan.new_tags == ()
    assert plan.existing_tags == ("port", "ship")


def test_plan_reports_run_modes(tmp_path):
    db = str(tmp_path / "db.sqlite")
    payload = {
        "commands": [
            {"tag": "chain", "tid": 1, "command": "echo a", "comment": "run:manual первый"},
            {"tag": "chain", "tid": 2, "command": "echo b", "comment": "run:auto второй"},
            {"tag": "chain", "tid": 3, "command": "echo c", "comment": "run:pause=2"},
            {"tag": "chain", "tid": 4, "command": "echo d", "comment": "просто команда"},
        ]
    }
    plan = db_transfer.plan_import(db, payload)
    assert (plan.run_auto, plan.run_manual) == (2, 1)  # auto + pause(=auto), manual
    assert plan.has_run_steps


def test_run_mode_matches_runbook():
    """Грамматика директив — одна: разбор в db_transfer сверяем с runbook."""
    samples = [
        "",
        "просто комментарий",
        "run:manual подожди",
        "run:auto",
        "run:prompt набери",
        "run:pause=3",
        "run:continue run:auto",
        "run:manual run:pause=1",
    ]
    for comment in samples:
        spec, _ = parse_directives(comment)
        expected = spec.mode if any(
            token.startswith("run:") for token in comment.split()
        ) else None
        assert db_transfer.run_mode(comment) == expected, comment


# --- `:import <url>` в TUI ---------------------------------------------------


async def test_import_url_previews_and_asks_confirmation(isolated_home, monkeypatch):
    calls = _patch_fetch(monkeypatch, LIBRARY_TEXT)
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ":import https://host/lib.json")
        assert await _wait(pilot, lambda: "Import preview" in _all_info(app))
        text = _all_info(app)
        assert "would add 3 command(s) of 3, skip 0" in text
        assert "new tags: port, ship" in text
        # Подсказка о подтверждении — последним блоком, перед вводом.
        assert "Enter — import" in last_info(app).text_content
        # Подтверждение — командой во вводе, а не скрытым состоянием.
        assert input_widget(app).value == ":import https://host/lib.json --yes"
        # И ничего ещё не импортировано.
        rows = app._library()
        assert all(row["tag"] != "ship" for row in rows)
        assert calls["n"] == 1


async def test_import_url_yes_applies(isolated_home, monkeypatch):
    _patch_fetch(monkeypatch, LIBRARY_TEXT)
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ":import https://host/lib.json --yes")
        assert await _wait(pilot, lambda: "Imported 3 command(s)" in last_info(app).text_content)
        tags = {row["tag"] for row in app._library()}
        assert {"ship", "port"} <= tags
        assert app._mask_secrets("x") == "x"


async def test_import_url_dry_does_not_draft(isolated_home, monkeypatch):
    _patch_fetch(monkeypatch, LIBRARY_TEXT)
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ":import --dry https://host/lib.json")
        assert await _wait(pilot, lambda: "Import preview" in last_info(app).text_content)
        assert input_widget(app).value == ""
        assert all(row["tag"] != "ship" for row in app._library())


async def test_import_uses_library_url_setting(isolated_home, monkeypatch):
    settings = isolated_home / "settings.yml"
    settings.write_text(
        settings.read_text(encoding="utf-8")
        + "\nlibrary_url: https://team.example/idvjpy.json\n",
        encoding="utf-8",
    )
    calls = _patch_fetch(monkeypatch, LIBRARY_TEXT)
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        assert app.library_url == "https://team.example/idvjpy.json"
        await submit(pilot, ":import")
        assert await _wait(pilot, lambda: "Import preview" in _all_info(app))
        assert calls["url"] == "https://team.example/idvjpy.json"
        assert "Import preview — https://team.example/idvjpy.json" in _all_info(app)


async def test_import_without_source_reports_usage(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ":import")
        assert "No import source" in last_info(app).text_content
        await submit(pilot, ":import --nope")
        assert "Usage: :import" in last_info(app).text_content


async def test_import_url_error_is_reported(isolated_home, monkeypatch):
    _patch_fetch(monkeypatch, "", error="Could not fetch https://host/x.json: timed out")
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ":import https://host/x.json")
        assert await _wait(pilot, lambda: "timed out" in last_info(app).text_content)
        assert input_widget(app).value == ""


async def test_import_refuses_payload_with_live_secret(isolated_home, monkeypatch):
    """Значение живого `$$`-секрета не должно приезжать извне в библиотеку."""
    secret = "s3cr3t-value"
    payload = {
        "commands": [{"tag": "leak", "tid": 1, "command": f"echo {secret}"}],
    }
    _patch_fetch(monkeypatch, json.dumps(payload))
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, f"$$TOKEN={secret}")
        await submit(pilot, ":import --dry https://host/lib.json")
        assert await _wait(pilot, lambda: "Refused" in last_info(app).text_content)
        assert all(row["tag"] != "leak" for row in app._library())


async def test_import_url_warns_about_run_directives(isolated_home, monkeypatch):
    payload = {
        "commands": [
            {"tag": "chain", "tid": 1, "command": "echo x", "comment": "run:auto"},
            {"tag": "chain", "tid": 2, "command": "echo y", "comment": "run:manual"},
        ]
    }
    _patch_fetch(monkeypatch, json.dumps(payload))
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ":import --dry https://host/lib.json")
        assert await _wait(pilot, lambda: "run: directives" in last_info(app).text_content)
        text = last_info(app).text_content
        assert "1 step(s) run without confirmation" in text
        assert "1 manual/prompt" in text


async def test_import_local_file_preview(isolated_home):
    """`--dry` работает и для локального файла; без флага — импорт сразу."""
    path = isolated_home / "ship.json"
    path.write_text(json.dumps({
        "tag_filter": "ship",
        "commands": [{"tag": "ship", "tid": 1, "command": "echo cargo"}],
    }), encoding="utf-8")
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, f":import --dry {path}")
        assert "Import preview" in last_info(app).text_content
        assert all(row["tag"] != "ship" for row in app._library())
        await submit(pilot, f":import {path}")
        assert "Imported 1 command(s)" in last_info(app).text_content
        assert any(row["tag"] == "ship" for row in app._library())
