"""Быстрые подсказки `:`-команд: при вводе `:` показывается список с описанием.

Таблица подсказок — `src/colon_commands.py`; здесь проверяются её полнота
(покрытие `CommandRunner.CMD_*`), фильтр по буквам и то, что подсказка не
ломает обычный ввод: `:q` + Enter по-прежнему выполняет команду.
"""
from __future__ import annotations

from app import CommandBlock, CommandRunner
from colon_commands import COLON_COMMAND_NAMES, colon_command_hint, linkify_colon_commands
from tests.conftest import (
    completion_click_spans,
    input_widget,
    last_info,
    submit,
    wait_command_done,
)


def _command_values() -> set[str]:
    return {
        getattr(CommandRunner, attr)
        for attr in dir(CommandRunner)
        if attr.startswith("CMD_")
    }


def test_table_covers_every_colon_command():
    """Новая `:`-команда без подсказки — падение теста, а не тихий пропуск."""
    missing = _command_values() - set(COLON_COMMAND_NAMES)
    assert not missing, f"no completion hint for: {sorted(missing)}"


def test_table_has_no_duplicates_and_nonempty_descriptions():
    names = list(COLON_COMMAND_NAMES)
    assert len(names) == len(set(names))
    assert all(names)
    # Подсказка приходит из локали: непереведённый ключ вернулся бы как `cmd.<имя>`.
    missing = [name for name in names if colon_command_hint(name) == f"cmd.{name}"]
    assert not missing, f"no hint text for: {sorted(missing)}"


async def _type(app: CommandRunner, pilot, value: str):
    inp = input_widget(app)
    inp.value = value
    inp.cursor_position = len(value)
    await pilot.pause()
    return inp


async def test_colon_lists_all_commands(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await _type(app, pilot, ":")
        clist = app._completion_list
        assert clist.is_visible()
        assert clist.total_candidates == len(COLON_COMMAND_NAMES)
        assert ":q" in clist.all_candidates
        assert ":md" in clist.all_candidates
        # Описание видно рядом с именем, а не только имя.
        assert any("—" in display for display in clist.all_displays)


async def test_colon_prefix_filters_by_letters(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await _type(app, pilot, ":m")
        clist = app._completion_list
        assert clist.is_visible()
        assert {c for c in clist.all_candidates if c.startswith(":m")} == set(
            clist.all_candidates
        )
        assert ":md" in clist.all_candidates
        assert ":q" not in clist.all_candidates


async def test_colon_slash_stays_journal_search(isolated_home):
    """`:/text` — поиск по строкам журнала, список команд его не перебивает."""
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await _type(app, pilot, ":/")
        assert not app._completion_list.is_visible()


async def test_colon_list_hides_after_space(isolated_home):
    """После имени набран пробел — своя семантика (`:cd /tmp`), не список команд."""
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await _type(app, pilot, ":cd ")
        assert not app._completion_list.is_visible()


async def test_applying_hint_inserts_command_without_running(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        inp = await _type(app, pilot, ":wa")
        await pilot.press("tab")
        await pilot.pause()
        assert inp.value == ":watch "
        assert not app.query(CommandBlock)  # команда не запускалась


async def test_enter_on_exact_command_still_runs(isolated_home):
    """`:c` + Enter выполняет команду, а не подставляет подсказку."""
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "seq 3")
        await wait_command_done(app)
        assert app.query(CommandBlock)

        inp = await _type(app, pilot, ":c")
        assert app._completion_list.is_visible()
        await pilot.press("enter")
        await pilot.pause()
        assert not app.query(CommandBlock)
        assert inp.value == ""


# --- Кликабельные ссылки в `:?` -------------------------------------------


def test_linkify_wraps_only_known_commands():
    text = ":q quit\n:md <file> — open\n:name-- hide\nratio:30 v1:done\n:nope"
    linked = linkify_colon_commands(text)
    assert "[@click=app.insert_colon_draft('q')][underline]:q[/][/]" in linked
    assert "[@click=app.insert_colon_draft('md')][underline]:md[/][/]" in linked
    # Не команды: суффикс `--`, чужие слова, слово с двоеточием в прозе.
    assert ":name--" in linked and "insert_colon_draft('name')" not in linked
    assert "ratio:30" in linked and "v1:done" in linked
    assert ":nope" in linked and "insert_colon_draft('nope')" not in linked


async def test_colon_hint_link_covers_only_the_command(isolated_home):
    """В списке `:` ссылка — только на имени команды, описание — текст."""
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await _type(app, pilot, ":jso")
        clist = app._completion_list
        spans = completion_click_spans(clist)
        assert list(spans.values()) == [":json"]

        row = next(iter(spans))
        line = clist.render_line(row).text
        assert "—" in line  # описание видно
        assert "—" not in spans[row]  # но оно не ссылка


async def test_help_block_has_clickable_commands(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":?")
        await pilot.pause()
        text = last_info(app).text_content
        assert "Commands Help" in text
        assert "[@click=app.insert_colon_draft('md')]" in text
        assert "[@click=app.insert_colon_draft('q')]" in text


async def test_help_link_inserts_command_without_running(isolated_home):
    """Клик по `:md` в `:?` колдёт команду во ввод (как ссылки `!tag`)."""
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":?")
        await pilot.pause()

        app.action_insert_colon_draft("md")
        await pilot.pause()
        assert input_widget(app).value == ":md "
        assert not app.query(CommandBlock)  # ничего не запускалось

        # Строку не затираем: следующая ссылка дописывается.
        app.action_insert_colon_draft("stats")
        await pilot.pause()
        assert input_widget(app).value == ":md :stats "


async def test_help_link_ignores_unknown_name(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        inp = input_widget(app)
        inp.value = "echo keep"
        await pilot.pause()
        app.action_insert_colon_draft("nope")
        await pilot.pause()
        assert inp.value == "echo keep"
