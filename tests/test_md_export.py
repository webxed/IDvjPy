"""Экспорт библиотеки в Markdown: `:export * [file.md]` (фича md-export)."""
import pytest

pytestmark = pytest.mark.slow

import database_v2 as database
from app import CommandRunner
from tests.conftest import last_info, submit


def _seed(db) -> None:
    database.init_db(str(db))
    database.add_command(str(db), "kubectl get pods", "kube")
    database.add_command(str(db), "kubectl get svc", "kube")
    database.add_command(str(db), "echo done", "mine")
    database.set_tag_comment(str(db), "kube", "k8s команды")
    database.set_command_comment(str(db), "mine", 1, "проверка")


def test_db_markdown_catalog(isolated_home):
    db = isolated_home / "lib.db"
    _seed(db)
    out = isolated_home / "catalog.md"
    n = database.export_all_to_markdown(str(db), str(out))
    assert n == 3
    text = out.read_text(encoding="utf-8")
    assert text.startswith("# Command library")
    assert "## kube — k8s команды" in text
    assert "- `kubectl get pods`" in text
    assert "## mine" in text
    assert "- `echo done`  — проверка" in text


def test_db_markdown_empty(isolated_home):
    db = isolated_home / "empty.db"
    database.init_db(str(db))
    out = isolated_home / "empty.md"
    assert database.export_all_to_markdown(str(db), str(out)) == 0
    assert "_Empty library" in out.read_text(encoding="utf-8")


async def test_colon_export_star_writes_markdown(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "#kube kubectl get pods")
        await submit(pilot, "#mine echo done")
        await submit(pilot, ":export * out.md")
        assert "Exported 2 command(s) to out.md (Markdown catalog)" in last_info(app).text_content
        text = (isolated_home / "out.md").read_text(encoding="utf-8")
        assert "## kube" in text
        assert "## mine" in text
        assert "- `echo done`" in text


async def test_export_star_usage(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":export")
        assert "Usage: :export" in last_info(app).text_content
