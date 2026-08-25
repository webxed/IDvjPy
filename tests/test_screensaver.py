"""DevOps starfield screensaver (Norton Commander-style idle overlay)."""
import asyncio
import time

from app import CommandRunner
from screensaver import DevopsScreensaver, StarField

from tests.conftest import input_widget, last_info, submit


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


async def test_colon_screensaver_off(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await submit(pilot, ":screensaver 0")
        assert "off" in last_info(app).text_content.lower()
        assert app.screensaver_idle == 0
