"""Метки буферов (`:name`) и пайп из конкретного блока (`|@label` / `|@N`).

Идея: пометить блок с дорогим выводом (`cat big.json`, `kubectl get -o json`)
и подбирать фильтр (`awk`/`jq`) без повторного запуска источника.
"""
from __future__ import annotations

import os

from textual.widgets import Input

from app import CommandRunner
from block_label import BlockLabelScreen
from session_mailbox import drain_inbox, inbox_path
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


async def test_f8_dialog_sets_label_and_pipe_works(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "printf 'alpha\\nbeta\\n'")
        block = await wait_command_done(app)
        await pilot.press("f8")
        await pilot.pause()
        assert isinstance(app.screen, BlockLabelScreen)
        field = app.screen.query_one("#label-input", Input)
        field.value = "buff"
        await pilot.press("enter")
        await pilot.pause()
        assert not isinstance(app.screen, BlockLabelScreen)
        assert app._block_labels.get("buff") is block
        assert block.label == "buff"

        # Метка, поставленная диалогом, работает в пайпе.
        await submit(pilot, "|@buff grep beta")
        piped = await wait_command_done(app)
        assert piped.raw_stdout.strip() == "beta"


async def test_f8_dialog_escape_cancels(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "echo hi")
        block = await wait_command_done(app)
        await pilot.press("f8")
        await pilot.pause()
        assert isinstance(app.screen, BlockLabelScreen)
        app.screen.query_one("#label-input", Input).value = "tmp"
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, BlockLabelScreen)
        assert block.label == ""
        assert app._block_labels == {}


async def test_f8_dialog_prefills_and_empty_removes(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "echo hi")
        block = await wait_command_done(app)
        await submit(pilot, ":name buff")
        await pilot.pause()
        assert block.label == "buff"

        await pilot.press("f8")
        await pilot.pause()
        field = app.screen.query_one("#label-input", Input)
        assert field.value == "buff"  # предзаполнено текущей меткой
        field.value = ""
        await pilot.press("enter")
        await pilot.pause()
        assert block.label == ""
        assert "buff" not in app._block_labels


async def test_f8_dialog_invalid_label_reports(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "echo hi")
        await wait_command_done(app)
        await pilot.press("f8")
        await pilot.pause()
        app.screen.query_one("#label-input", Input).value = "3"
        await pilot.press("enter")
        await pilot.pause()
        assert app._block_labels == {}
        assert "Invalid label" in last_info(app).text_content


async def test_f8_dialog_without_block_reports(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("f8")
        assert "No finished command block" in last_info(app).text_content


async def test_send_materializes_pipe_label(isolated_home):
    """`:send` раскрывает `|@label` в полный вызов — в чужой сессии метки нет."""
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "printf 'alpha\\nbeta\\n'")
        await wait_command_done(app)
        await submit(pilot, ":name buff")
        await pilot.pause()

        await submit(pilot, ":send beta |@buff grep beta")
        await pilot.pause()
        messages = drain_inbox(inbox_path(str(isolated_home), "beta"))
        assert len(messages) == 1
        command = messages[0]["command"]
        assert command.startswith("printf")
        assert command.endswith("| grep beta")
        assert "|@buff" not in command


async def test_send_unknown_pipe_label_aborts(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "echo hi")
        await wait_command_done(app)
        await submit(pilot, ":send beta |@nope grep x")
        await pilot.pause()
        assert not os.path.exists(inbox_path(str(isolated_home), "beta"))
        assert "no labelled block 'nope'" in last_info(app).text_content
