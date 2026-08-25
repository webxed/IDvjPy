"""DevOps starfield screensaver (Norton Commander-style idle overlay)."""
import asyncio
import time

from app import CommandRunner
from screensaver import (
    TICKER_SEP,
    DevopsScreensaver,
    LibraryTicker,
    StarField,
    flatten_command,
    load_library_reminders,
    ticker_items_from_commands,
)

from tests.conftest import input_widget, last_info, submit


def test_flatten_command_collapses_whitespace():
    assert flatten_command("  echo   hi  ") == "echo hi"


def test_ticker_items_from_commands():
    items = ticker_items_from_commands(
        [
            ("deploy", 1, "rsync -av src/ host:"),
            ("deploy", 2, "systemctl restart app"),
            ("kpod", 1, "kubectl get pods -A"),
        ]
    )
    assert items == (
        "!deploy[1]  rsync -av src/ host:",
        "!deploy[2]  systemctl restart app",
        "!kpod[1]  kubectl get pods -A",
    )


def test_ticker_items_empty():
    assert ticker_items_from_commands([]) == ()


def test_load_library_skips_hidden(isolated_home):
    import database_v2 as database

    db = str(isolated_home / "test_history.db")
    database.init_db(db)
    database.add_command(db, "echo hello-ss-unique", "hint")
    database.add_command(db, "echo gone", "hide")
    database.delete_commands_by_tag(db, "hide")
    items = load_library_reminders(db)
    assert any("hello-ss-unique" in item for item in items)
    assert any(item.startswith("!hint[") for item in items)
    assert not any("!hide" in item for item in items)


def test_ticker_shuffles_and_scrolls():
    items = tuple(f"cmd-{i}" for i in range(16))
    one = LibraryTicker(items, seed=1)
    two = LibraryTicker(items, seed=2)
    assert sorted(one.order) == sorted(items)
    assert one.order != list(items)
    assert one.order != two.order
    line = one.render_line(20)
    assert len(line.plain) == 20
    assert "00ff5f" in (line.style or "") or any(
        span.style and "00ff5f" in str(span.style) for span in line.spans
    )
    before = one.render_line(24).plain
    one.tick(0.5)
    after = one.render_line(24).plain
    assert before != after
    assert TICKER_SEP.strip() in (one._tape)


def test_starfield_tick_renders_rows():
    field = StarField(40, 12, seed=7)
    for _ in range(40):
        field.tick(0.08)
    text = field.render_text()
    plain = text.plain
    lines = plain.splitlines()
    assert len(lines) == 12
    assert any(ch not in " " for ch in plain)
    assert "any key" in plain


async def test_colon_screensaver_opens_and_key_does_not_type(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await submit(pilot, ":screensaver")
        await pilot.pause()
        assert isinstance(app.screen, DevopsScreensaver)
        await pilot.press("x")
        await pilot.pause()
        assert not isinstance(app.screen, DevopsScreensaver)
        assert input_widget(app).value == ""


async def test_screensaver_idle_zero_never_starts(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert app.screensaver_idle == 0
        app._launch_screensaver()
        await pilot.pause()
        assert not isinstance(app.screen, DevopsScreensaver)


async def test_screensaver_starts_after_idle(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        app.screensaver_idle = 0.2
        app._bump_screensaver_idle()
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if isinstance(app.screen, DevopsScreensaver):
                break
            await asyncio.sleep(0.05)
            await pilot.pause()
        assert isinstance(app.screen, DevopsScreensaver)
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, DevopsScreensaver)


async def test_screensaver_ticker_loads_library(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await submit(pilot, "#hint echo hello-ss-unique")
        await submit(pilot, ":screensaver")
        await pilot.pause()
        assert isinstance(app.screen, DevopsScreensaver)
        assert any("hello-ss-unique" in item for item in app.screen._ticker.items)
        assert "hello-ss-unique" in app.screen._ticker._tape
        bar = app.screen.query_one("#ss-ticker")
        assert not bar.has_class("-empty")
        line = app.screen._ticker.render_line(80).plain
        assert len(line) == 80


async def test_colon_screensaver_off(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await submit(pilot, ":screensaver 0")
        assert "off" in last_info(app).text_content.lower()
        assert app.screensaver_idle == 0
