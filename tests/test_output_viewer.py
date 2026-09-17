"""`:log` / F7 — полный вывод блока в Line-API просмотрщике (фича full-output-viewer).

Проверяем: открытие модального экрана с полным выводом (без обрезки в 300 строк),
выбор блока (N назад / сфокусированный), прокрутку, краевые случаи и что
оптимизированная обрезка журнала по-прежнему оставляет хвост и считает скрытое.
"""

from textual.widgets import Input

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


async def test_log_viewer_search_jumps(isolated_home):
    """`/` — поиск по тексту: Enter прыгает на совпадение, Esc — закрыть поиск."""
    app = CommandRunner()
    async with app.run_test(size=(100, 20)) as pilot:
        await submit(pilot, "seq -f 'hit-%03g' 1 200")
        await wait_command_done(app)
        await submit(pilot, ":log")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, OutputViewerScreen)
        view = screen.query_one(OutputView)
        search = screen.query_one("#output-search", Input)
        assert not search.display

        await pilot.press("slash")
        await pilot.pause()
        assert search.display and search.has_focus

        search.value = "hit-150"
        await pilot.press("enter")
        await pilot.pause()
        assert view.match_row is not None
        assert view._lines[view.match_row] == "hit-150"
        assert "line 150/200" in (screen.sub_title or "")

        # Esc закрывает только поле поиска; экран живёт дальше.
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, OutputViewerScreen)
        assert not search.display

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, OutputViewerScreen)


async def test_log_viewer_search_highlights_the_whole_row(isolated_home):
    """Строка совпадения подсвечивается целиком (фон + bold), а не только текст.

    Регрессия: стиль `--hit` накладывался через `Strip.apply_style`, а он в
    Rich/Textual сливается как «применяемый + стиль сегмента» — цвета сегмента
    (фон чётной/нечётной строки) побеждали, и от `--hit` оставался только
    `bold`: фоновая подсветка строки не появлялась никогда.
    """
    app = CommandRunner()
    async with app.run_test(size=(100, 20)) as pilot:
        await submit(pilot, "printf 'alpha\\nhit-line\\ngamma\\n'")
        await wait_command_done(app)
        await submit(pilot, ":log")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, OutputViewerScreen)
        view = screen.query_one(OutputView)
        search = screen.query_one("#output-search", Input)

        await pilot.press("slash")
        await pilot.pause()
        search.value = "hit"
        await pilot.press("enter")
        await pilot.pause()
        row = view.match_row
        assert row is not None

        hit_bg = view.get_component_rich_style("outputview--hit").bgcolor
        plain_bg = view.get_component_rich_style("outputview--even").bgcolor
        assert hit_bg is not None and hit_bg != plain_bg

        # render_line ждёт y относительно окна; здесь прокрутки нет (строка у верха).
        y = row - int(view.scroll_offset.y)
        matched = view.render_line(y)
        assert matched.cell_length == int(view.size.width)  # на всю ширину
        style = next(seg.style for seg in matched if seg.text.strip())
        assert style is not None
        assert style.bgcolor == hit_bg, "фон строки совпадения не подсвечен"
        assert style.bold is True

        # Соседняя строка осталась обычной.
        other = view.render_line(y + 1)
        other_style = next(seg.style for seg in other if seg.text.strip())
        assert other_style is not None and other_style.bgcolor != hit_bg


async def test_log_viewer_search_next_and_prev(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 20)) as pilot:
        await submit(pilot, "printf 'hit-one\\nhit-two\\nhit-three\\n'")
        await wait_command_done(app)
        await submit(pilot, ":log")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, OutputViewerScreen)
        view = screen.query_one(OutputView)
        search = screen.query_one("#output-search", Input)

        await pilot.press("slash")
        await pilot.pause()
        search.value = "hit"
        await pilot.press("enter")
        await pilot.pause()
        first = view.match_row
        assert first is not None

        await pilot.press("n")
        await pilot.pause()
        second = view.match_row
        assert second is not None and second != first

        # Shift+N в реальном терминале приходит как заглавная `N`.
        await pilot.press("N")
        await pilot.pause()
        assert view.match_row == first

        # ... а `shift+n` — для терминалов с modifyOtherKeys: та же команда prev,
        # от первой строки уходит по кругу на последнюю.
        await pilot.press("shift+n")
        await pilot.pause()
        assert view.match_row == 2


async def test_log_viewer_filter_keeps_only_matches(isolated_home):
    """`f` — на экране только строки с совпадениями; `f` / Esc возвращают всё.

    Номера строк при этом остаются **исходными** (как в блоке), а не порядковыми
    в отборе.
    """
    app = CommandRunner()
    async with app.run_test(size=(100, 20)) as pilot:
        await submit(pilot, "seq -f 'row-%03g' 1 30")
        await wait_command_done(app)
        await submit(pilot, ":log")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, OutputViewerScreen)
        view = screen.query_one(OutputView)
        search = screen.query_one("#output-search", Input)
        assert view.line_count == 30

        await pilot.press("slash")
        await pilot.pause()
        search.value = "row-01"
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("escape")  # убрать поле, оставить поиск
        await pilot.pause()
        assert view.match_row == 9  # row-010
        assert "line 10/30" in (screen.sub_title or "")

        await pilot.press("f")
        await pilot.pause()
        assert view.filtered
        assert view.visible_count == 10  # row-010 … row-019
        assert view.line_count == 30  # всего строк не изменилось
        assert all("row-01" in line for line in view._lines)
        assert "matches 10/30" in (screen.sub_title or "")
        row = view.match_row
        assert row is not None and view._lines[row] == "row-010"
        assert view.source_line(row) == 10  # номер в исходном выводе
        assert "line 10" in (screen.sub_title or "")

        # `n` идёт по отобранным строкам.
        await pilot.press("n")
        await pilot.pause()
        assert view._lines[view.match_row] == "row-011"

        # Esc снимает фильтр (поле уже закрыто) и возвращает весь вывод,
        # место при этом не теряется.
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, OutputViewerScreen)
        assert not view.filtered
        assert view.visible_count == 30
        assert view._lines[view.match_row] == "row-011"

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, OutputViewerScreen)


async def test_log_viewer_filter_second_press_returns_all(isolated_home):
    """Повторный `f` — снова весь вывод (и место совпадения сохраняется)."""
    app = CommandRunner()
    async with app.run_test(size=(100, 20)) as pilot:
        await submit(pilot, "printf 'alpha\\nhit-one\\nbeta\\nhit-two\\n'")
        await wait_command_done(app)
        await submit(pilot, ":log")
        await pilot.pause()
        screen = app.screen
        view = screen.query_one(OutputView)
        search = screen.query_one("#output-search", Input)

        await pilot.press("slash")
        await pilot.pause()
        search.value = "hit"
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("f")
        await pilot.pause()
        assert view.filtered and view.visible_count == 2
        assert view._lines == ["hit-one", "hit-two"]

        await pilot.press("f")
        await pilot.pause()
        assert not view.filtered
        assert view.visible_count == 4
        row = view.match_row
        assert row is not None
        assert view._lines[row] == "hit-one"


async def test_log_viewer_filter_needs_a_search(isolated_home):
    """`f` без поиска ничего не фильтрует и говорит, чего не хватает."""
    app = CommandRunner()
    async with app.run_test(size=(100, 20)) as pilot:
        await submit(pilot, "seq 1 12")
        await wait_command_done(app)
        await submit(pilot, ":log")
        await pilot.pause()
        screen = app.screen
        view = screen.query_one(OutputView)

        await pilot.press("f")
        await pilot.pause()
        assert not view.filtered
        assert view.visible_count == view.line_count == 12
        assert "needs a search" in (screen.sub_title or "")


async def test_log_viewer_filter_drops_when_new_pattern_has_no_match(isolated_home):
    """Новый образец без совпадений: фильтр снимается, список остаётся полным."""
    app = CommandRunner()
    async with app.run_test(size=(100, 20)) as pilot:
        await submit(pilot, "printf 'ala\\nbeta\\nhit-one\\nhit-two\\n'")
        await wait_command_done(app)
        await submit(pilot, ":log")
        await pilot.pause()
        screen = app.screen
        view = screen.query_one(OutputView)
        search = screen.query_one("#output-search", Input)

        await pilot.press("slash")
        await pilot.pause()
        search.value = "hit"
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("f")
        await pilot.pause()
        assert view.filtered and view.visible_count == 2

        # Новый образец без совпадений — пустой экран был бы хуже полного списка.
        await pilot.press("slash")
        await pilot.pause()
        search.value = "zzz-not-here"
        await pilot.press("enter")
        await pilot.pause()
        assert not view.filtered
        assert view.visible_count == view.line_count == 4
        assert "No match" in (screen.sub_title or "")


async def test_log_viewer_search_reports_no_match(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 20)) as pilot:
        await submit(pilot, "seq 1 20")
        await wait_command_done(app)
        await submit(pilot, ":log")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, OutputViewerScreen)
        view = screen.query_one(OutputView)
        search = screen.query_one("#output-search", Input)

        await pilot.press("slash")
        await pilot.pause()
        search.value = "zzz-not-here"
        await pilot.press("enter")
        await pilot.pause()
        assert view.match_row is None
        assert "No match" in (screen.sub_title or "")


async def test_log_viewer_y_without_path_reports(isolated_home):
    """`y` в `:log` (вывод блока, не файл) — явная ошибка, а не тишина."""
    app = CommandRunner()
    async with app.run_test(size=(100, 20)) as pilot:
        await submit(pilot, "seq 3")
        await wait_command_done(app)
        await submit(pilot, ":log")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, OutputViewerScreen)
        await pilot.press("y")
        await pilot.pause()
        assert "No file path" in (screen.sub_title or "")


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
