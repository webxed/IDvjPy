"""`:mv` — перенос команды между тегами и переименование тега (фича tag-move)."""
import pytest

pytestmark = pytest.mark.slow

import database_v2 as database
from app import CommandRunner
from tests.conftest import last_info, submit


def _seed(db) -> None:
    database.init_db(str(db))
    database.add_command(str(db), "kubectl get pods -o wide", "kube")
    database.add_command(str(db), "kubectl get svc", "kube")
    database.add_command(str(db), "echo keep", "mine")
    database.set_tag_comment(str(db), "kube", "k8s команды")


def test_db_move_command_to_new_tag(isolated_home):
    db = isolated_home / "mv.db"
    _seed(db)
    # Перенос в существующий тег — новый tid в конце.
    database.add_command(str(db), "echo target1", "mine")
    result = database.move_command_by_tid(str(db), "kube", 1, "mine")
    assert result is not None
    new_tid, gid = result
    assert new_tid == 3  # mine уже имеет tid 1,2
    row = database.get_command_by_global_id(str(db), gid)
    assert row["command"] == "kubectl get pods -o wide"
    rows = database.get_commands_by_tag(str(db), "kube")
    assert [r["tid"] for r in rows] == [2]


def test_db_move_missing_command_returns_none(isolated_home):
    db = isolated_home / "mv.db"
    _seed(db)
    assert database.move_command_by_tid(str(db), "kube", 42, "mine") is None


def test_db_rename_tag_moves_comment(isolated_home):
    db = isolated_home / "mv.db"
    _seed(db)
    n = database.rename_tag(str(db), "kube", "k8s")
    assert n == 2
    assert database.get_commands_by_tag(str(db), "kube") == []
    assert len(database.get_commands_by_tag(str(db), "k8s")) == 2
    assert database.get_tag_comment(str(db), "k8s") == "k8s команды"
    with pytest.raises(ValueError):
        database.rename_tag(str(db), "mine", "k8s")
    assert database.rename_tag(str(db), "missing", "other") == 0


async def test_colon_mv_moves_command(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "#kube kubectl get pods")
        await submit(pilot, "#mine echo stay")
        await submit(pilot, ":mv kube[1] mine")
        text = last_info(app).text_content
        assert "Moved <1> kube[1] → mine[2]" in text
        # Тега kube больше нет: ?kube уходит в поиск по содержимому (не список тега).
        await submit(pilot, "?kube")
        assert "Search 'kube'" in last_info(app).text_content
        await submit(pilot, "?mine")
        assert "Commands for tag 'mine'" in last_info(app).text_content
        assert "kubectl get pods" in last_info(app).text_content
        assert "echo stay" in last_info(app).text_content


async def test_colon_mv_renames_tag(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "#kube kubectl get pods")
        await submit(pilot, ":mv kube k8s")
        assert "Renamed tag 'kube' → 'k8s' (1 command(s))." in last_info(app).text_content
        await submit(pilot, "?k8s")
        assert "Commands for tag 'k8s'" in last_info(app).text_content
        assert "kubectl get pods" in last_info(app).text_content
        # Старого тега нет: ?kube — поиск по содержимому (без ошибки).
        await submit(pilot, "?kube")
        assert "Search 'kube'" in last_info(app).text_content


async def test_colon_mv_errors_are_explicit(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "#kube kubectl get pods")
        await submit(pilot, ":mv")
        assert "Usage: :mv" in last_info(app).text_content
        await submit(pilot, ":mv kube[1] 9bad")
        assert "invalid destination tag '9bad'" in last_info(app).text_content
        await submit(pilot, ":mv nope[1] mine")
        assert "Command nope[1] not found" in last_info(app).text_content
        await submit(pilot, ":mv kube kube")
        assert "already 'kube'" in last_info(app).text_content
        await submit(pilot, ":mv ghost target")
        assert "tag 'ghost' not found" in last_info(app).text_content
