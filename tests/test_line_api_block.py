"""Line-API блоки журнала: включаются ключом ``line_api_blocks`` / IDVJPY_LINE_BLOCKS.

Проверяем, что при включённом флаге журнал использует ``CommandLineBlock`` и
сохраняет штатное поведение: вывод, высота (перенос как у Static), построчный
курсор и сворачивание.
"""
from __future__ import annotations

from textual.widgets import Static

from app import CommandLineBlock, CommandRunner
from tests.conftest import submit, wait_command_done


def _enable_line_api(monkeypatch) -> None:
    monkeypatch.setenv("IDVJPY_LINE_BLOCKS", "1")


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
