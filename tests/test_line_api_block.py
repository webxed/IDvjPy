"""Line-API блоки журнала: включаются ключом ``line_api_blocks`` / IDVJPY_LINE_BLOCKS.

Проверяем, что при включённом флаге журнал использует ``CommandLineBlock`` и
сохраняет штатное поведение: вывод, высота (перенос как у Static), построчный
курсор и сворачивание.
"""
from __future__ import annotations

from textual import events
from textual.widgets import Static

from app import CommandLineBlock, CommandRunner, InfoBlock
from tests.conftest import last_info, submit, wait_command_done


def _enable_line_api(monkeypatch) -> None:
    monkeypatch.setenv("IDVJPY_LINE_BLOCKS", "1")


def _first_text_bg(block: Static) -> str:
    """Фон текстового сегмента после применения CSS (как в кадре)."""
    from textual.geometry import Region

    width, height = int(block.size.width), int(block.size.height)
    for strip in block.render_lines(Region(0, 0, width, height)):
        for segment in strip:
            if segment.text.strip():
                style = segment.style
                return str(style.bgcolor) if style else ""
    return ""


async def _drag(pilot, widget, start, end) -> None:
    """Протяжка мышью (публичный Pilot умеет только click)."""
    await pilot._post_mouse_events([events.MouseDown], widget, offset=start)
    await pilot._post_mouse_events([events.MouseMove], widget, offset=end)
    await pilot._post_mouse_events([events.MouseUp], widget, offset=end)
    await pilot.pause()


def _row_bgs(block: Static, y: int) -> list[str]:
    return [
        str(segment.style.bgcolor) if segment.style is not None else ""
        for segment in block.render_line(y)
    ]


async def test_line_api_block_used_when_enabled(isolated_home, monkeypatch):
    _enable_line_api(monkeypatch)
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert app._line_api_blocks is True
        await submit(pilot, "echo line-api-hello")
        block = await wait_command_done(app)
        assert isinstance(block, CommandLineBlock)
        assert "line-api-hello" in block.text_content
        # Строки построены (кэш не пуст), высота — их число.
        width = int(block.size.width)
        block._ensure_strips(width)
        assert block._strips
        assert block.get_content_height(block.size, block.size, width) == len(block._strips)


async def test_line_api_block_disabled_by_default(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert app._line_api_blocks is False
        await submit(pilot, "echo plain-block")
        block = await wait_command_done(app)
        assert not isinstance(block, CommandLineBlock)


async def test_line_api_block_render_line_has_output(isolated_home, monkeypatch):
    _enable_line_api(monkeypatch)
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await submit(pilot, "printf 'alpha\\nbeta\\ngamma\\n'")
        block = await wait_command_done(app)
        assert isinstance(block, CommandLineBlock)
        width = int(block.size.width)
        height = block.get_content_height(block.size, block.size, width)
        rendered = "\n".join(block.render_line(y).text for y in range(height))
        assert "alpha" in rendered
        assert "beta" in rendered
        assert "gamma" in rendered


async def test_line_api_block_height_matches_static(isolated_home, monkeypatch):
    """Перенос строк должен совпадать с обычным Static (та же ширина/высота)."""
    _enable_line_api(monkeypatch)
    app = CommandRunner()
    async with app.run_test(size=(60, 24)) as pilot:
        await submit(pilot, "seq -f 'row-%02g' 1 30")
        block = await wait_command_done(app)
        assert isinstance(block, CommandLineBlock)

        container = app.query_one("#results-container")
        reference = Static(block._src_markup)
        await container.mount(reference)
        await pilot.pause()
        await pilot.pause()
        assert block.size.height == reference.size.height


async def test_line_api_block_line_cursor_navigates(isolated_home, monkeypatch):
    _enable_line_api(monkeypatch)
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await submit(pilot, "seq -f 'cur-%02g' 1 5")
        block = await wait_command_done(app)
        assert isinstance(block, CommandLineBlock)
        await pilot.press("tab")
        await pilot.pause()
        assert app.focused is block

        block.enter_line_nav(notify=False)
        assert block.line_nav_active
        lines = block._nav_lines()
        target = next(i for i, line in enumerate(lines) if line.strip() == "cur-03")
        block.jump_to_line(target)
        assert block._current_plain_line().strip() == "cur-03"
        block.exit_line_nav(notify=False)
        assert not block.line_nav_active


async def test_line_api_block_collapse_restores(isolated_home, monkeypatch):
    _enable_line_api(monkeypatch)
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await submit(pilot, "seq 1 10")
        block = await wait_command_done(app)
        assert isinstance(block, CommandLineBlock)
        full_height = block.size.height
        assert full_height > 1

        block.toggle_collapse()
        await pilot.pause()
        assert block.collapsed
        assert block.size.height < full_height

        block.toggle_collapse()
        await pilot.pause()
        assert not block.collapsed
        assert block.size.height == full_height


# -- InfoBlock (инфо-блоки: справка :?, ответы :llm) -----------------------


def _click_metas(block: InfoBlock) -> list[str]:
    """Значения `@click` из видимых Strip'ов (разметка дожила до рендера)."""
    metas: list[str] = []
    for strip in block._strips:
        for segment in strip:
            style = segment.style
            if style is not None and style.meta and "@click" in style.meta:
                metas.append(style.meta["@click"])
    return metas


async def test_info_block_line_api_renders_text(isolated_home, monkeypatch):
    """Регрессия: InfoBlock на Line API должен рисовать текст, а не пустые строки.

    ``Content.to_strips`` ждёт Textual-стиль (``Widget.visual_style``). При
    передаче Rich-стиля он молча (без исключения) отдаёт пустые Strip'ы —
    проверки по ``text_content`` этого не видят, поэтому читаем именно
    отрисованное: ``render_line(y).text``.
    """
    _enable_line_api(monkeypatch)
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await submit(pilot, ":?")
        await pilot.pause()

        block = last_info(app)
        assert block._line_api_enabled()
        width = int(block.size.width)
        height = block.get_content_height(block.size, block.size, width)
        assert height == len(block._strips) > 10

        rendered = [block.render_line(y).text for y in range(height)]
        assert any("Commands Help" in line for line in rendered)
        assert len([line for line in rendered if line.strip()]) > 10


async def test_info_block_line_api_keeps_click_markup(isolated_home, monkeypatch):
    """Разметка (кликабельные `:команды` в `:?`) должна доживать до Strip'ов."""
    _enable_line_api(monkeypatch)
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await submit(pilot, ":?")
        await pilot.pause()

        block = last_info(app)
        block._ensure_strips(int(block.size.width))
        assert any("insert_colon_draft('md')" in meta for meta in _click_metas(block))


async def test_info_block_line_api_focus_bg(isolated_home, monkeypatch):
    """Фон фокуса накладывается в render_line (в кэше strip'ов фона нет)."""
    _enable_line_api(monkeypatch)
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await submit(pilot, ":?")
        await pilot.pause()

        block = last_info(app)
        assert block._cache_key is not None
        # Кэш строится по стилю без фона — иначе клик по блоку пересобирал бы всё.
        assert block._cache_key[1].background is None

        assert not block.has_focus
        unfocused_bg = _first_text_bg(block)
        block.focus()
        await pilot.pause()
        await pilot.pause()
        assert block.has_focus
        assert _first_text_bg(block) != unfocused_bg


async def test_info_block_line_api_off_uses_static(isolated_home):
    """Без Line API InfoBlock рендерит базовый Static (старое поведение)."""
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await submit(pilot, ":?")
        await pilot.pause()

        block = last_info(app)
        assert not block._line_api_enabled()
        rendered = "\n".join(
            block.render_line(y).text for y in range(int(block.size.height))
        )
        assert "Commands Help" in rendered


async def test_line_api_block_repaints_on_focus(isolated_home, monkeypatch):
    """Кэш Strip'ов должен учитывать фон виджета: при фокусе он меняется."""
    _enable_line_api(monkeypatch)
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await submit(pilot, "echo focus-bg")
        block = await wait_command_done(app)
        assert isinstance(block, CommandLineBlock)

        await pilot.press("escape")
        await pilot.pause()
        assert not block.has_focus
        unfocused_bg = _first_text_bg(block)

        await pilot.press("tab")
        await pilot.pause()
        await pilot.pause()
        assert app.focused is block
        focused_bg = _first_text_bg(block)
        assert focused_bg != unfocused_bg

        await pilot.press("escape")
        await pilot.pause()
        assert _first_text_bg(block) == unfocused_bg


# -- выделение мышью на Line API --------------------------------------------


async def test_line_api_block_selection_spans_lines(isolated_home, monkeypatch):
    """Регрессия: протяжка по нескольким строкам не должна схлопываться в первую.

    ``Content.to_strips`` ставил ``meta['offset'] = (x, 0)`` для каждой строки
    (мы рендерим по одной логической строке за вызов), и все координаты
    выделения попадали в строку 0 — выделить текст дальше первой строки было
    невозможно.
    """
    _enable_line_api(monkeypatch)
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "printf 'dragaa\\ndragbb\\ndragcc\\ndragdd\\n'")
        block = await wait_command_done(app)
        assert isinstance(block, CommandLineBlock)
        await pilot.pause()

        await _drag(pilot, block, (0, 0), (3, 3))
        selected = app.screen.get_selected_text()
        assert selected
        # Строки 1–3 попали в выделение (раньше была только первая).
        assert "dragbb" in selected
        assert "dragcc" in selected


async def test_line_api_block_selection_is_highlighted(isolated_home, monkeypatch):
    """Выделенная строка должна быть подкрашена (Line API сам этого не делает)."""
    _enable_line_api(monkeypatch)
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "printf 'hlrow1\\nhlrow2\\nhlrow3\\n'")
        block = await wait_command_done(app)
        assert isinstance(block, CommandLineBlock)
        await pilot.pause()

        selection_bg = str(
            app.screen.get_component_rich_style("screen--selection").bgcolor
        )
        before = _row_bgs(block, 2)
        assert selection_bg not in before

        await _drag(pilot, block, (0, 1), (4, 2))
        after = _row_bgs(block, 2)
        assert selection_bg in after

        # Снятие выделения возвращает исходный вид строки.
        await pilot.press("escape")
        await pilot.pause()
        assert _row_bgs(block, 2) == before


async def test_info_block_line_api_selection_spans_lines(isolated_home, monkeypatch):
    """То же для инфоблоков: выделение в `:?` не залипает на первой строке."""
    _enable_line_api(monkeypatch)
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await submit(pilot, ":?")
        await pilot.pause()

        block = last_info(app)
        assert block._line_api_enabled()
        await _drag(pilot, block, (0, 0), (20, 2))
        selected = app.screen.get_selected_text()
        assert selected
        assert "Application" in selected


def _assert_cell_offsets(app, block, expected: str) -> None:
    """Клетка → символ: компоситор должен находить ровно тот символ, что видно.

    Читаем `meta['offset']` так же, как `Screen.get_widget_and_offset_at`
    (это то, чем Textual связывает протяжку мыши с текстом). Строку ищем по
    тексту: одна логическая строка может занимать несколько визуальных (перенос),
    и сравнивать номер визуальной строки с логической нельзя.
    """
    rows = [
        y
        for y in range(int(block.size.height))
        if block._logical_line(y) is not None
        and (y == 0 or block._logical_line(y) != block._logical_line(y - 1))
        and block.render_line(y).text.startswith(expected)
    ]
    assert rows, f"нет строки, начинающейся с {expected!r}"
    row = rows[0]
    logical = block._logical_line(row)
    region = block.content_region
    for cell, char in enumerate(expected):
        widget, offset = app.screen.get_widget_and_offset_at(
            region.x + cell, region.y + row
        )
        assert widget is block
        assert offset is not None
        assert offset.y == logical, (cell, char, offset, logical)
        assert offset.x == cell, (cell, char, offset)


async def test_line_api_selection_keeps_cell_offsets(isolated_home, monkeypatch):
    """Регрессия: подсветка не должна ломать meta['offset'] разрезанных сегментов.

    Разрезанный сегмент сохранял мету исходного (у хвоста — «начало сегмента»),
    поэтому компоситор сопоставлял клетку не с тем символом: выделение ползло
    вдвое медленнее курсора и цеплялось за конец строки.
    """
    _enable_line_api(monkeypatch)
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "printf 'cellaa\\ncellbb\\ncellcc\\n'")
        block = await wait_command_done(app)
        assert isinstance(block, CommandLineBlock)
        await pilot.pause()

        await _drag(pilot, block, (0, 1), (3, 1))
        assert block.text_selection is not None
        _assert_cell_offsets(app, block, "cellbb")

        # То же, когда выделение накрывает несколько строк.
        await _drag(pilot, block, (0, 1), (2, 2))
        assert block.text_selection is not None
        _assert_cell_offsets(app, block, "cellaa")
        _assert_cell_offsets(app, block, "cellbb")


async def test_info_block_line_api_selection_keeps_cell_offsets(
    isolated_home, monkeypatch
):
    """То же для инфоблока `:?` (там строки с разметкой и ссылками)."""
    _enable_line_api(monkeypatch)
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await submit(pilot, ":?")
        await pilot.pause()

        block = last_info(app)
        assert block._line_api_enabled()
        await _drag(pilot, block, (0, 0), (10, 2))
        assert block.text_selection is not None
        _assert_cell_offsets(app, block, "Application Commands")
