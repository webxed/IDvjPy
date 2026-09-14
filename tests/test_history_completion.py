"""Подсказки из history_*.txt при наборе (в т.ч. строки, начинающиеся с `@` и `>`).

Раньше выпадающий список брал только session_history: команды `@ …` (запускаются
уже без префикса) и старые строки из файла в подсказках не появлялись.
"""
from __future__ import annotations

from app import CommandRunner
from history_store import append_history_file_line
from tests.conftest import input_widget


def _seed(app: CommandRunner, *lines: str) -> None:
    for line in lines:
        append_history_file_line(app.FILE_HISTORY, line)


async def test_history_completion_includes_at_and_tty(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        _seed(
            app,
            "kubectl get pods",
            "@ echo no-timeout-abc",
            "> echo tty-abc",
        )
        items = [it.insert for it in app.get_history_completions("abc")]
        assert "@ echo no-timeout-abc" in items
        assert "> echo tty-abc" in items
        assert "kubectl get pods" not in items
        # Свежие сверху.
        assert items.index("> echo tty-abc") < items.index("@ echo no-timeout-abc")

        kub = [it.insert for it in app.get_history_completions("kubectl")]
        assert "kubectl get pods" in kub


async def test_history_completion_appears_in_dropdown(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        _seed(app, "@ echo no-timeout-abc")
        inp = input_widget(app)
        inp.value = "@ ec"
        inp._show_completions()
        candidates = app._completion_list.all_candidates
        assert any("@ echo no-timeout-abc" in cand for cand in candidates)


async def test_history_completion_dedupes_command_candidates(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        _seed(app, "echo dup-check")
        items = app.get_history_completions("echo dup", exclude=["echo dup-check"])
        assert items == []


async def test_history_completion_disabled_by_setting(isolated_home):
    settings = isolated_home / "settings.yml"
    settings.write_text(
        settings.read_text(encoding="utf-8") + "history_completion: false\n",
        encoding="utf-8",
    )
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        _seed(app, "@ echo no-timeout-abc")
        assert app.history_completion is False
        assert app.get_history_completions("abc") == []


async def test_history_completion_skips_short_and_special_prefixes(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        _seed(app, "echo hello-world")
        assert app.get_history_completions("e") == []  # короткий ввод (< 2)
        assert app.get_history_completions(":llm") == []  # у `:` свои подсказки
        assert [it.insert for it in app.get_history_completions("hello")] == [
            "echo hello-world"
        ]
