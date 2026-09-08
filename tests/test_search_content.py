"""Подстрочный поиск по содержимому команд: `?text` (фича content-search).

Точное имя тега по-прежнему открывает список команд тега (`?tag`);
неизвестное имя из 2+ символов ищется по тексту команд и комментариев
по всем тегам. Символы LIKE (% _) ищутся буквально.
"""
import pytest

pytestmark = pytest.mark.slow

import database_v2 as database
from app import CommandRunner
from tests.conftest import confirm_input, last_info, submit


def _seed(db_path) -> None:
    database.init_db(str(db_path))
    database.add_command(str(db_path), "kubectl get pods -o wide", "kube")
    database.add_command(str(db_path), "kubectl get svc -o wide", "kube")
    database.add_command(str(db_path), "ls -la", "file")
    database.add_command(str(db_path), "echo 100% done", "mine")


def test_db_search_finds_substring(isolated_home):
    db = isolated_home / "search.db"
    _seed(db)
    rows, total = database.search_commands_by_content(str(db), "wide")
    assert total == 2
    cmds = {r["command"] for r in rows}
    assert cmds == {"kubectl get pods -o wide", "kubectl get svc -o wide"}
    # Поиск по комментарию тоже работает.
    database.set_command_comment(str(db), "file", 1, "список каталога")
    rows, total = database.search_commands_by_content(str(db), "каталога")
    assert total == 1
    assert rows[0]["tag"] == "file"


def test_db_search_like_metachars_are_literal(isolated_home):
    db = isolated_home / "search.db"
    _seed(db)
    rows, total = database.search_commands_by_content(str(db), "100%")
    assert total == 1
    assert rows[0]["command"] == "echo 100% done"
    # '_' как литерал, не wildcard: ничего не должно найтись по "w_de".
    _, total = database.search_commands_by_content(str(db), "w_de")
    assert total == 0
    _, total = database.search_commands_by_content(str(db), "ls_la")
    assert total == 0


def test_db_search_deleted_rows_skipped(isolated_home):
    db = isolated_home / "search.db"
    _seed(db)
    database.delete_command_by_tid(str(db), "kube", 1)
    _, total = database.search_commands_by_content(str(db), "pods")
    assert total == 0


async def test_question_text_searches_content(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "#kube kubectl get pods -o wide")
        await submit(pilot, "#kube kubectl get svc -o wide")
        await submit(pilot, "?pods")
        text = last_info(app).text_content
        assert "Search 'pods' in commands (1)" in text
        assert "kubectl get pods -o wide" in text
        assert "kubectl get svc" not in text


async def test_question_exact_tag_still_lists(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "#kube kubectl get pods")
        await submit(pilot, "?kube")
        text = last_info(app).text_content
        assert "Commands for tag 'kube'" in text
        assert "kubectl get pods" in text


async def test_question_short_unknown_is_explicit_error(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        # 1 символ — не тег и не поиск: явная ошибка.
        await submit(pilot, "?z")
        text = last_info(app).text_content
        assert "Tag 'z' not found" in text
        assert "2+ characters" in text
        # 2+ символов — это поиск по содержимому; пусто → явный ответ.
        await submit(pilot, "?qqqq")
        assert "Search 'qqqq': no matches" in last_info(app).text_content


async def test_search_result_runs_by_global_id(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "#mine echo found-me")
        await submit(pilot, "?found-me")
        # После поиска last_query_results заполнен: !1 запускает найденное.
        assert 1 in app.last_query_results
        await submit(pilot, "!1")
        block = await confirm_input(pilot, app)
        assert block.raw_stdout == "found-me"
