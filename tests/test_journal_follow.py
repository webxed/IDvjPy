"""Режим чтения журнала: новый вывод не уводит вид и не крадёт фокус.

Пока пользователь отскроллил журнал вверх или держит фокус на блоке, блоки
дописываются вниз, но viewport и фокус остаются на месте. Слежение
возвращается, когда пользователь докрутил до низа или запустил команду.
"""
from __future__ import annotations

from app import CommandRunner, InfoBlock
from session_mailbox import MODE_RUN, send_message
from tests.conftest import input_widget, submit, wait_command_done


class _Wheel:
    """Заглушка события колеса: обработчикам нужен только `stop()`."""

    def __init__(self) -> None:
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


async def _long_journal(pilot, app: CommandRunner, lines: int = 200):
    """Журнал из одного длинного блока — так вид можно увести вверх."""
    await submit(pilot, f"seq 1 {lines}")
    await wait_command_done(app)
    await pilot.pause()
    container = app.query_one(f"#{app.ID_RESULTS_CONTAINER}")
    assert float(container.max_scroll_y) > 10
    # Обычный случай: за своим выводом следим (мы у нижнего края).
    assert app._follow_paused is False
    assert float(container.scroll_y) >= float(container.max_scroll_y) - 2
    return container


async def _scroll_up(app: CommandRunner, times: int = 5) -> None:
    for _ in range(times):
        app.on_mouse_scroll_up(_Wheel())


async def test_wheel_up_pauses_follow_and_keeps_view(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        container = await _long_journal(pilot, app)
        assert input_widget(app).has_focus

        await _scroll_up(app)
        await pilot.pause()
        assert app._follow_paused is True
        before = float(container.scroll_y)
        assert before < float(container.max_scroll_y) - 2

        # Новый вывод просто дописывается вниз: вид и фокус не двигаются.
        app.add_block(InfoBlock("late output"))
        await pilot.pause()
        assert float(container.scroll_y) == before
        assert input_widget(app).has_focus


async def test_wheel_scrolls_three_lines_per_notch(isolated_home):
    """Шаг колеса — 3 строки (как в `:log`/F7): `:?` иначе листается сотнями щелчков."""
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        container = await _long_journal(pilot, app)
        bottom = float(container.scroll_y)

        app.on_mouse_scroll_up(_Wheel())
        await pilot.pause()
        assert bottom - float(container.scroll_y) == 3

        app.on_mouse_scroll_down(_Wheel())
        await pilot.pause()
        assert float(container.scroll_y) == bottom


async def test_submit_resumes_follow(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        container = await _long_journal(pilot, app)
        await _scroll_up(app)
        await pilot.pause()
        assert app._follow_paused is True

        # Пользователь запустил команду — снова следим за выводом.
        await submit(pilot, "seq 1 3")
        await wait_command_done(app)
        await pilot.pause()
        assert app._follow_paused is False
        assert float(container.scroll_y) >= float(container.max_scroll_y) - 2


async def test_scrolling_back_to_bottom_resumes_follow(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await _long_journal(pilot, app)
        await _scroll_up(app)
        await pilot.pause()
        assert app._follow_paused is True

        for _ in range(40):
            app.on_mouse_scroll_down(_Wheel())
        await pilot.pause()
        assert app._follow_paused is False


async def test_focus_on_journal_block_keeps_view_and_focus(isolated_home):
    """PgUp из ввода уводит фокус на блок (чтение/копирование) — не отбираем."""
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        container = await _long_journal(pilot, app)

        await pilot.press("pageup")  # фокус на последний командный блок
        await pilot.pause()
        await pilot.press("pageup")  # и уже прокрутка вверх
        await pilot.pause()
        assert not input_widget(app).has_focus
        focused = app.focused
        before = float(container.scroll_y)

        app.add_block(InfoBlock("late output"))
        await pilot.pause()
        assert float(container.scroll_y) == before
        assert app.focused is focused


async def test_forwarded_run_does_not_move_view_while_reading(isolated_home):
    """`:send!` во время чтения: команда выполняется, но вид не уводит."""
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        container = await _long_journal(pilot, app)
        await _scroll_up(app)
        await pilot.pause()
        before = float(container.scroll_y)

        send_message(str(isolated_home), "default", "seq 1 3", sender="s2", mode=MODE_RUN)
        app._poll_session_inbox()
        await wait_command_done(app)
        await pilot.pause()

        assert float(container.scroll_y) == before
        assert app._follow_paused is True
