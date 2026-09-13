"""`:log` / F7 — полный вывод блока в Line-API просмотрщике (фича full-output-viewer).

Проверяем: открытие модального экрана с полным выводом (без обрезки в 300 строк),
выбор блока (N назад / сфокусированный), прокрутку, краевые случаи и что
оптимизированная обрезка журнала по-прежнему оставляет хвост и считает скрытое.
"""

from app import CommandRunner
from output_viewer import OutputView, OutputViewerScreen
from tests.conftest import last_info, submit, wait_command_done


async def test_log_opens_full_output_without_truncation(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "seq 1 400")
        block = await wait_command_done(app)
        assert block._truncated  # журнал обрезал до 300 строк
        await submit(pilot, ":log")
        await pilot.pause()
        assert isinstance(app.screen, OutputViewerScreen)
        view = app.screen.query_one(OutputView)
        assert view.line_count == 400  # в просмотрщике — все строки
        assert "400 lines" in (app.screen.sub_title or "")
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, OutputViewerScreen)


async def test_log_n_back_selects_previous_block(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "seq 1 5")
        await wait_command_done(app)
        await submit(pilot, "seq 1 7")
        await wait_command_done(app)

        await submit(pilot, ":log")
        await pilot.pause()
        assert "7 lines" in (app.screen.sub_title or "")
        await pilot.press("escape")
        await pilot.pause()

        await submit(pilot, ":log 1")
        await pilot.pause()
        assert "5 lines" in (app.screen.sub_title or "")
        await pilot.press("escape")
        await pilot.pause()


async def test_f7_opens_output_viewer(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "seq 1 42")
        await wait_command_done(app)
        await pilot.press("f7")
        await pilot.pause()
        assert isinstance(app.screen, OutputViewerScreen)
        assert app.screen.query_one(OutputView).line_count == 42
        await pilot.press("q")
        await pilot.pause()
        assert not isinstance(app.screen, OutputViewerScreen)


async def test_log_viewer_scrolls_with_keys(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 20)) as pilot:
        await submit(pilot, "seq 1 400")
        await wait_command_done(app)
        await submit(pilot, ":log")
        await pilot.pause()
        view = app.screen.query_one(OutputView)
        assert view.scroll_offset.y == 0
        await pilot.press("pagedown")
        await pilot.pause()
        assert view.scroll_offset.y > 0


async def test_log_empty_output_reports(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "true")
        await wait_command_done(app)
        await submit(pilot, ":log")
        await pilot.pause()
        assert not isinstance(app.screen, OutputViewerScreen)
        assert "Output is empty" in last_info(app).text_content


async def test_log_without_blocks_reports(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":log")
        await pilot.pause()
        assert not isinstance(app.screen, OutputViewerScreen)
        assert "No command block to view" in last_info(app).text_content


async def test_log_too_far_back_reports(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "seq 1 3")
        await wait_command_done(app)
        await submit(pilot, ":log 9")
        await pilot.pause()
        assert not isinstance(app.screen, OutputViewerScreen)
        assert "is too far back" in last_info(app).text_content


async def test_log_bad_arg_reports_usage(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "seq 1 3")
        await wait_command_done(app)
        await submit(pilot, ":log nope")
        await pilot.pause()
        assert "Usage: :log" in last_info(app).text_content


async def test_log_shows_stderr_section(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "printf 'out\\n'; printf 'err\\n' 1>&2; exit 1")
        await wait_command_done(app)
        await submit(pilot, ":log")
        await pilot.pause()
        assert isinstance(app.screen, OutputViewerScreen)
        view = app.screen.query_one(OutputView)
        # out + пустая строка + STDERR: + err
        assert view.line_count == 4


async def test_log_masks_secret_hint(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "$$TOKEN=supersecret")
        await submit(pilot, "echo hi")
        await wait_command_done(app)
        await submit(pilot, ":log")
        await pilot.pause()
        assert "secrets visible" in (app.screen.sub_title or "")


async def test_truncate_keeps_tail_and_counts_hidden(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "seq 1 400")
        block = await wait_command_done(app)
        assert block._truncated
        shown = block._format_output()
        assert "100 lines truncated" in shown
        assert "F7 views full" in shown
        assert shown.rstrip().endswith("400")

        await submit(pilot, "seq 1 300")
        block2 = await wait_command_done(app)
        assert not block2._truncated
        assert "truncated" not in block2._format_output().lower()
