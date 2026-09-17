"""Ключ `history_queries`: вызовы каких `:`-команд остаются в истории.

Такие вызовы (`:llm …`, `:cht …`, `:run …`, `:send …`) пишутся в
`history_<instance>.txt` для ↑ / `:h`, но не подсказываются в completion:
это запросы и навигация, а не команды для повтора. Список — в settings.yml
(раньше был зашит в код).
"""
from __future__ import annotations

import pytest

from app import DEFAULT_HISTORY_QUERIES, CommandRunner, parse_history_queries
from tests.conftest import submit


def _with_settings(isolated_home, extra: str) -> None:
    settings = isolated_home / "settings.yml"
    settings.write_text(
        settings.read_text(encoding="utf-8") + extra, encoding="utf-8"
    )


# --- разбор ключа -------------------------------------------------------------


def test_parse_history_queries_forms():
    assert parse_history_queries(["llm", "md"]) == frozenset({"llm", "md"})
    assert parse_history_queries("llm, :run  md") == frozenset({"llm", "md", "run"})
    assert parse_history_queries("llm md") == frozenset({"llm", "md"})
    assert parse_history_queries(["md, run", "llm"]) == frozenset({"md", "run", "llm"})
    # Явное «выключено»: пусто, false, null.
    assert parse_history_queries([]) == frozenset()
    assert parse_history_queries(None) == frozenset()
    assert parse_history_queries(False) == frozenset()
    # Непонятное значение — как по умолчанию (ключ есть, но не список и не строка).
    assert parse_history_queries(True) == frozenset(DEFAULT_HISTORY_QUERIES)
    assert parse_history_queries(42) == frozenset(DEFAULT_HISTORY_QUERIES)
    # Пустые элементы и пустые строки в списке ничего не добавляют.
    assert parse_history_queries(["", None, "  ", ","]) == frozenset()


def test_default_list_is_the_previous_behaviour():
    assert set(DEFAULT_HISTORY_QUERIES) == {"llm", "cht", "rg", "md", "run", "send", "send!"}


def test_is_history_only_query_needs_arguments(isolated_home):
    app = CommandRunner()
    assert app._is_history_only_query(":llm вопрос")
    assert app._is_history_only_query("  :run chain.yml --step  ")
    assert app._is_history_only_query(":send! s2 echo hi")  # имя команды — до пробела
    assert app._is_history_only_query(":send s2 echo hi")
    # Без аргументов и для чужих команд — нет.
    assert not app._is_history_only_query(":llm")
    assert not app._is_history_only_query(":md")
    assert not app._is_history_only_query(":stats")
    assert not app._is_history_only_query("echo hi")
    assert not app._is_history_only_query("")


@pytest.mark.slow
async def test_queries_are_recorded_but_not_suggested(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":llm offline привет")
        await submit(pilot, ":stats")
        await pilot.pause()
        history = app._read_file_history()
        assert ":llm offline привет" in history
        assert ":stats" not in history  # обычные `:`-команды в историю не пишутся

        # ↑ по истории достаёт строку, но в подсказках её нет.
        app.session_history.append(":llm offline привет")
        assert ":llm offline привет" not in app.get_completion_candidates(":l")


@pytest.mark.slow
async def test_setting_narrows_recorded_queries(isolated_home):
    _with_settings(isolated_home, "history_queries: [rg]\n")
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        assert app.history_queries == frozenset({"rg"})
        await submit(pilot, ":llm offline привет")
        await submit(pilot, ":rg нет-такого-текста")
        await pilot.pause()
        history = app._read_file_history()
        assert ":rg нет-такого-текста" in history
        assert ":llm offline привет" not in history


@pytest.mark.slow
async def test_setting_can_turn_queries_off(isolated_home):
    _with_settings(isolated_home, "history_queries: []\n")
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        assert app.history_queries == frozenset()
        await submit(pilot, ":llm offline привет")
        await pilot.pause()
        assert ":llm offline привет" not in app._read_file_history()
        # И строка снова подсказывается: исключать больше нечего.
        app.session_history.append(":llm offline привет")
        assert ":llm offline привет" in app.get_completion_candidates(":l")


@pytest.mark.slow
async def test_missing_key_keeps_default_after_restart(isolated_home):
    """Без ключа в settings.yml набор — прежний (`:run …` пишется в историю)."""
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        assert app.history_queries == frozenset(DEFAULT_HISTORY_QUERIES)
        await submit(pilot, ":run nosuch-tag --dry")
        await pilot.pause()
        assert ":run nosuch-tag --dry" in app._read_file_history()
