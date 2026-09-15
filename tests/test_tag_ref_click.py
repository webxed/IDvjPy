"""Клик по ссылке `!tag[tid]` в журнале: обычный — вставить, Ctrl/двойной — выполнить.

Мета-действия Textual модификаторов не знают: `@click.ctrl` в разметке не
парсится (ключ меты — `[@a-zA-Z_-][a-zA-Z0-9_-]*=`, точки в нём нет), а
`App._broker_event` модификаторы ключа вообще отбрасывает. Поэтому намерение
«вставить и сразу выполнить» ловит сам блок (`LineNavigable.on_click` →
`note_block_link_click`), а выполняет `action_insert_bang_draft`. Клавиатурный
путь не меняется: `!tag[tid]` по-прежнему только подставляет текст.
"""
import pytest
from textual.widget import Widget

from app import CommandBlock, CommandRunner
from tests.conftest import input_widget, submit, wait_command_done

pytestmark = pytest.mark.slow


def _find_link_cell(app: CommandRunner, needle: str) -> tuple[Widget, tuple[int, int]] | None:
    """Виджет и смещение клетки с `@click`-ссылкой, в действии которой есть `needle`."""
    size = app.screen.size
    for y in range(size.height):
        for x in range(size.width):
            style = app.screen.get_style_at(x, y)
            meta = getattr(style, "meta", None) if style is not None else None
            if not meta or needle not in str(meta.get("@click", "")):
                continue
            try:
                widget, _region = app.screen.get_widget_at(x, y)
            except Exception:
                continue
            return widget, (x - widget.region.x, y - widget.region.y)
    return None


async def _link_to_clickref(pilot, app: CommandRunner) -> tuple[Widget, tuple[int, int]]:
    """Тег + `?tag` в журнале; вернуть (виджет, смещение) ссылки `!clickref[1]`."""
    await submit(pilot, "#clickref echo hello")
    await submit(pilot, "?clickref")
    cell = _find_link_cell(app, "insert_bang_draft('clickref', '1')")
    assert cell is not None, "в журнале нет ссылки !clickref[1]"
    return cell


async def test_plain_click_inserts_without_running(isolated_home):
    """Обычный клик — как раньше: только вставка, запуск отдельным Enter."""
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        widget, offset = await _link_to_clickref(pilot, app)
        before = len(list(app.query(CommandBlock)))

        await pilot.click(widget, offset=offset)
        await pilot.pause()

        assert input_widget(app).value == "!clickref[1] "
        assert len(list(app.query(CommandBlock))) == before  # ничего не запустилось


async def test_ctrl_click_inserts_and_runs(isolated_home):
    """Ctrl+клик — вставить и сразу выполнить."""
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        widget, offset = await _link_to_clickref(pilot, app)
        before = len(list(app.query(CommandBlock)))

        await pilot.click(widget, offset=offset, control=True)
        await pilot.pause()

        block = await wait_command_done(app)
        assert block.raw_stdout.strip() == "hello"
        assert len(list(app.query(CommandBlock))) == before + 1
        assert input_widget(app).value == ""  # строка ушла на выполнение
        # История — как после клавиатурного «Enter, Enter»: сами ссылки в историю
        # не пишутся (`log_to_history` пропускает `!`), остаётся раскрытая команда.
        history = (isolated_home / "history_default.txt").read_text(encoding="utf-8")
        assert history.strip().splitlines()[-1] == "echo hello"


async def test_double_click_inserts_once_and_runs(isolated_home):
    """Двойной клик — то же, но без дубля: вставку делает только первый клик.

    Регрессия: брокер `@click` срабатывает на каждый клик серии, поэтому
    ввод получал `!clickref[1] !clickref[1] ` и выполнилось бы `echo hello echo hello`.
    """
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        widget, offset = await _link_to_clickref(pilot, app)
        before = len(list(app.query(CommandBlock)))

        await pilot.click(widget, offset=offset, times=2)
        await pilot.pause()

        block = await wait_command_done(app)
        assert block.raw_stdout.strip() == "hello"
        assert len(list(app.query(CommandBlock))) == before + 1
        assert input_widget(app).value == ""


async def test_ctrl_click_on_tag_without_tid_only_inserts(isolated_home):
    """`!tag ` (без tid) — не команда: Ctrl+клик по такой ссылке только вставляет."""
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "#clickme echo x")
        app.note_block_link_click("app.insert_bang_draft('clickme')", ctrl=True, chain=1)
        app.action_insert_bang_draft("clickme")
        await pilot.pause()

        assert input_widget(app).value == "!clickme "


async def test_ctrl_click_on_other_links_does_not_run(isolated_home):
    """Ссылки не на `!tag[tid]` (`:?`, `.md`, `--seed`) остаются «только вставить».

    Заодно проверяем, что признак одноразовый: после чужой ссылки он сброшен и
    следующая вставка `!tag[tid]` ничего не выполняет.
    """
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "#clickme echo x")
        before = len(list(app.query(CommandBlock)))

        app.note_block_link_click("app.insert_colon_draft('md')", ctrl=True, chain=1)
        app.action_insert_colon_draft("md")
        await pilot.pause()
        assert input_widget(app).value == ":md "
        assert app._link_click_run is None

        app.action_insert_bang_draft("clickme", "1")
        await pilot.pause()
        assert input_widget(app).value == ":md !clickme[1] "
        assert len(list(app.query(CommandBlock))) == before
