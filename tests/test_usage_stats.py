"""Счётчики запусков и `:stats` (фича usage-metrics)."""
import pytest

pytestmark = pytest.mark.slow

import database_v2 as database
from app import CommandRunner
from tests.conftest import confirm_input, last_info, submit, wait_command_done


def _seed(db) -> None:
    database.init_db(str(db))
    database.add_command(str(db), "kubectl get pods", "kube")
    database.add_command(str(db), "kubectl get svc", "kube")
    database.add_command(str(db), "echo never", "mine")


def test_db_bump_and_stats(isolated_home):
    db = isolated_home / "usage.db"
    _seed(db)
    assert database.bump_command_usage(str(db), "kubectl get pods") == 1
    assert database.bump_command_usage(str(db), "kubectl get pods") == 1
    assert database.bump_command_usage(str(db), "missing") == 0
    s = database.usage_stats(str(db))
    assert s["live"] == 3
    assert s["tags"] == 2
    assert s["never_run"] == 2  # svc + echo never
    assert s["top"][0]["command"] == "kubectl get pods"
    assert s["top"][0]["use_count"] == 2
    kube = next(t for t in s["per_tag"] if t["tag"] == "kube")
    assert kube["runs"] == 2
    assert kube["live"] == 2
    assert kube["last_used"]  # строка времени проставлена


def test_db_schema_migration_adds_columns(isolated_home):
    """Старая БД без колонок use_count/last_used апгрейдится init_db."""
    import sqlite3

    db = isolated_home / "legacy.db"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE commands (id INTEGER PRIMARY KEY AUTOINCREMENT, tag TEXT NOT NULL, "
        "tid INTEGER NOT NULL, command TEXT NOT NULL, timestamp DATETIME NOT NULL, "
        "deleted INTEGER DEFAULT 0, comment TEXT DEFAULT '', UNIQUE(tag, tid))"
    )
    conn.commit()
    conn.close()
    database.init_db(str(db))
    conn = sqlite3.connect(str(db))
    cols = [r[1] for r in conn.execute("PRAGMA table_info(commands)").fetchall()]
    conn.close()
    assert "use_count" in cols
    assert "last_used" in cols


async def test_stats_counts_real_runs(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        await submit(pilot, "#kube echo used-cmd")
        await submit(pilot, "#mine echo other")
        # Первый запуск: echo used-cmd.
        await submit(pilot, "echo used-cmd")
        await wait_command_done(app, timeout=8.0)
        # Второй запуск через !1 (глобальный id — тоже считается).
        await submit(pilot, "!1")
        await confirm_input(pilot, app)
        await submit(pilot, ":stats")
        text = last_info(app).text_content
        assert "echo used-cmd" in text
        assert "2×" in text
        assert "never run" in text
        assert "echo other" not in text  # в топ не попала


async def test_stats_empty_db(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":stats")
        text = last_info(app).text_content
        assert "Library stats:" in text
        assert "(empty database" in text


async def test_bang_completion_orders_by_usage(isolated_home):
    """Часто используемая команда идёт первой в списке !tag."""
    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        await submit(pilot, "#kube echo hot")
        await submit(pilot, "#kube echo cold")
        await submit(pilot, "echo hot")
        await wait_command_done(app, timeout=8.0)
        await submit(pilot, "echo hot")
        await wait_command_done(app, timeout=8.0)
        items, _ = app.get_bang_completions("!kube", 5)
        # display: '<id> kube[tid]  echo hot' первым.
        assert "echo hot" in items[0].display
