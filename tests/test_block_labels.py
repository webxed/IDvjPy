"""Метки буферов (`:name`) и пайп из конкретного блока (`|@label` / `|@N`).

Идея: пометить блок с дорогим выводом (`cat big.json`, `kubectl get -o json`)
и подбирать фильтр (`awk`/`jq`) без повторного запуска источника.
"""
from __future__ import annotations

from app import CommandRunner
from tests.conftest import last_info, submit, wait_command_done


async def test_name_labels_and_pipe_reuses_buffer(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "printf 'alpha\\nbeta\\ngamma\\n'")
        source = await wait_command_done(app)
        await submit(pilot, ":name buff")
        await pilot.pause()
        assert app._block_labels["buff"] is source
        assert source.label == "buff"
        # Метка видна в шапке; для рендера скобки экранированы (не разметка).
        assert "[buff]" in source._format_output()
        assert "\\[buff]" in source._format_output(display=True)

        # Пайп из буфера: источник повторно НЕ выполняется.
        await submit(pilot, "|@buff grep beta")
        piped = await wait_command_done(app)
        assert piped is not source
        assert piped.raw_stdout.strip() == "beta"

        # В историю — полный вызов, а не shorthand.
        history = app._read_file_history()
        assert any(line.startswith("printf") and line.endswith("| grep beta") for line in history)
        assert "|@buff grep beta" not in history


async def test_pipe_from_index_counts_blocks_back(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "printf 'alpha\\nbeta\\n'")
        await wait_command_done(app)
        await submit(pilot, "echo other")
        await wait_command_done(app)
        # `|@1` — один блок назад (printf), а не последний (`echo other`).
        await submit(pilot, "|@1 grep beta")
        piped = await wait_command_done(app)
        assert piped.raw_stdout.strip() == "beta"


async def test_name_reassign_moves_label(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "echo one")
        first = await wait_command_done(app)
        await submit(pilot, ":name buff")
        await pilot.pause()
        assert first.label == "buff"

        await submit(pilot, "echo two")
        second = await wait_command_done(app)
        await submit(pilot, ":name buff")
        await pilot.pause()
        assert app._block_labels["buff"] is second
        assert second.label == "buff"
        assert first.label == ""


async def test_name_lists_and_removes(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "seq 1 3")
        block = await wait_command_done(app)
        await submit(pilot, ":name alpha")
        await pilot.pause()

        await submit(pilot, ":name")
        assert "alpha" in last_info(app).text_content

        await submit(pilot, ":name alpha-")
        await pilot.pause()
        assert "alpha" not in app._block_labels
        assert block.label == ""

        await submit(pilot, ":name")
        assert "No labels yet" in last_info(app).text_content


async def test_name_dash_clears_all(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "echo one")
        await wait_command_done(app)
        await submit(pilot, ":name alpha")
        await submit(pilot, "echo two")
        await wait_command_done(app)
        await submit(pilot, ":name beta")
        await pilot.pause()
        assert set(app._block_labels) == {"alpha", "beta"}
        await submit(pilot, ":name -")
        await pilot.pause()
        assert app._block_labels == {}


async def test_pipe_unknown_label_reports(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "echo hi")
        await wait_command_done(app)
        await submit(pilot, "|@nope wc -l")
        assert "no labelled block 'nope'" in last_info(app).text_content


async def test_name_rejects_digit_and_bad_usage(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "echo hi")
        await wait_command_done(app)
        # Чисто цифровая метка запрещена: `|@3` однозначно значит «3-й блок назад».
        await submit(pilot, ":name 3")
        assert "Usage: :name" in last_info(app).text_content


async def test_name_without_finished_block_reports(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":name buff")
        assert "No finished command block" in last_info(app).text_content


async def test_clear_blocks_drops_labels(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "seq 1 3")
        await wait_command_done(app)
        await submit(pilot, ":name buff")
        await pilot.pause()
        assert "buff" in app._block_labels
        await submit(pilot, ":c")
        await pilot.pause()
        assert app._block_labels == {}
