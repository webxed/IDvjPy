"""DevOps starfield screensaver (Norton Commander-style idle overlay)."""
import asyncio
import time

from datetime import datetime

from rich.text import Text
from app import CommandRunner
from screensaver import (
    COMMAND_HELP_LINES,
    TICKER_SEP,
    DevopsScreensaver,
    HelpTypewriter,
    HostSnapshot,
    HostStats,
    LibraryTicker,
    StarField,
    clock_glyph,
    flatten_command,
    format_bytes_short,
    load_library_reminders,
    parse_meminfo,
    overlay_host_on_help,
    render_host_line,
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


def test_help_typewriter_overwrites_left_to_right():
    tw = HelpTypewriter(("AAAA", "BB"), seed=1, type_cps=1, pause=30)
    tw.previous = "AAAA"
    tw.current = "BB"
    tw.typed = 1
    tw.phase = "type"
    vis = tw.visible()
    assert vis[0] == "B"
    assert vis[1] == "A"
    tw.typed = 4
    vis = tw.visible()
    assert vis.startswith("BB")
    assert vis[2:4] == "  "
    tw.phase = "pause"
    assert tw.visible() == "BB"


def test_help_typewriter_shuffles_pauses_and_cycles():
    lines = tuple(f"L{i}  — d{i}" for i in range(8))
    a = HelpTypewriter(lines, seed=1, type_cps=500, pause=0.01)
    b = HelpTypewriter(lines, seed=2, type_cps=500, pause=0.01)
    seen = [a.current]
    for _ in range(7):
        a.tick(1.0)
        assert a.phase == "pause"
        assert a.visible() == a.current
        a.tick(0.02)
        seen.append(a.current)
    assert sorted(seen) == sorted(lines)
    assert seen != list(lines)
    assert a.current != b.current or a._deck != b._deck
    assert all("  — " in line for line in COMMAND_HELP_LINES)


def test_help_typewriter_indents_from_left_edge():
    tw = HelpTypewriter((":?  — full command help",), seed=1, type_cps=1000, pause=30)
    tw.tick(1.0)
    plain = tw.render_line(80).plain
    assert len(plain) == 80
    pad = len(plain) - len(plain.lstrip())
    assert 8 <= pad <= 24
    assert pad < 40
    assert plain.lstrip().startswith(":?")


def test_parse_meminfo_uses_available():
    used, total = parse_meminfo(
        "MemTotal:       16384000 kB\n"
        "MemFree:         1000000 kB\n"
        "MemAvailable:    8192000 kB\n"
        "Buffers:          100000 kB\n"
        "Cached:          2000000 kB\n"
    )
    assert total == 16384000 * 1024
    assert used == (16384000 - 8192000) * 1024


def test_parse_meminfo_falls_back_without_available():
    used, total = parse_meminfo(
        "MemTotal:        2000000 kB\n"
        "MemFree:          500000 kB\n"
        "Buffers:          100000 kB\n"
        "Cached:           200000 kB\n"
    )
    assert total == 2000000 * 1024
    assert used == (2000000 - 800000) * 1024


def test_format_bytes_short():
    assert format_bytes_short(4 * 1024 ** 3) == "4.0G"
    assert format_bytes_short(16 * 1024 ** 3) == "16G"
    assert format_bytes_short(512 * 1024 ** 2) == "512M"


def test_host_stats_polls_once_per_second():
    calls = {"n": 0}

    def reader():
        calls["n"] += 1
        return HostSnapshot(
            load1=0.15, load5=0.10, load15=0.05,
            mem_used=4 * 1024 ** 3, mem_total=16 * 1024 ** 3,
        )

    hs = HostStats(reader=reader, poll=1.0)
    assert calls["n"] == 1
    for _ in range(12):
        assert hs.tick(0.08) is False
    assert calls["n"] == 1
    assert hs.tick(0.08) is True
    assert calls["n"] == 2


def test_host_line_is_right_inset():
    snap = HostSnapshot(
        load1=0.15, load5=0.10, load15=0.05,
        mem_used=4 * 1024 ** 3, mem_total=16 * 1024 ** 3,
    )
    plain = render_host_line(snap, 80).plain
    assert len(plain) == 80
    right_pad = len(plain) - len(plain.rstrip())
    assert 8 <= right_pad <= 24
    assert right_pad < 40
    assert not plain.startswith("load")
    assert "load avg" in plain
    assert "0.15" in plain
    assert "mem" in plain
    assert "4.0G/16G" in plain
    assert plain.rstrip().endswith("25%")


def test_host_overlays_help_on_a_narrow_row():
    snap = HostSnapshot(
        load1=1.0, load5=0.5, load15=0.25,
        mem_used=1024 ** 3, mem_total=2 * 1024 ** 3,
    )
    help_line = Text(" " * 8 + ":q  — quit")
    wide = overlay_host_on_help(help_line, snap, 80).plain
    assert ":q" in wide
    assert "load avg 1.00" in wide
    assert wide.rstrip().endswith("%")
    narrow = overlay_host_on_help(help_line, snap, 36).plain
    assert "load avg" in narrow
    assert len(narrow) == 36


def test_starfield_tick_renders_rows():
    field = StarField(40, 12, seed=7)
    for _ in range(40):
        field.tick(0.08)
    text = field.render_text()
    plain = text.plain
    lines = plain.splitlines()
    assert len(lines) == 12
    assert any(ch not in " " for ch in plain)
    assert "any key" not in plain


def test_starfield_has_no_comets():
    field = StarField(80, 24, seed=1)
    for _ in range(200):
        field.tick(0.08)
        kinds = {star.kind for star in field.stars}
        assert "comet" not in kinds
        for star in field.stars:
            assert "→" not in star.glyph


def test_starfield_stars_are_slow():
    field = StarField(60, 20, seed=11)
    dust = [star for star in field.stars if star.kind != "clock"]
    clocks = [star for star in field.stars if star.kind == "clock"]
    assert dust
    assert all(0.06 <= star.speed <= 0.18 for star in dust)
    assert all(0.03 <= star.speed <= 0.08 for star in clocks)


def test_starfield_can_disable_flying_stars():
    field = StarField(60, 20, seed=4, stars=False)
    kinds = {star.kind for star in field.stars}
    assert "dust" not in kinds
    assert "token" not in kinds
    assert kinds == {"clock"}
    field.resize(80, 24)
    assert all(star.kind == "clock" for star in field.stars)
    assert {star.label for star in field.stars} == {"time", "date"}


def test_clock_glyph_formats_time_and_date():
    moment = datetime(2026, 8, 26, 15, 35, 7)
    assert clock_glyph(moment, "time") == "15:35:07"
    assert clock_glyph(moment, "date") == "2026-08-26"


def test_starfield_clocks_fly_and_update():
    current = {"t": datetime(2026, 8, 26, 15, 35, 1)}

    def now():
        return current["t"]

    field = StarField(50, 16, seed=3, now=now)
    clocks = [star for star in field.stars if star.kind == "clock"]
    assert {star.label for star in clocks} == {"time", "date"}
    assert any(star.glyph == "15:35:01" for star in clocks)
    assert any(star.glyph == "2026-08-26" for star in clocks)
    before = {star.label: star.z for star in clocks}
    field.tick(0.5)
    for star in clocks:
        assert star.z != before[star.label] or star.z > 0.5
    current["t"] = datetime(2026, 8, 26, 15, 36, 9)
    field.tick(0.08)
    by_label = {star.label: star for star in field.stars if star.kind == "clock"}
    assert by_label["time"].glyph == "15:36:09"
    assert by_label["date"].glyph == "2026-08-26"
    by_label["time"].x, by_label["time"].y, by_label["time"].z = 0.0, -0.12, 0.22
    by_label["date"].x, by_label["date"].y, by_label["date"].z = 0.0, 0.18, 0.22
    plain = field.render_text().plain
    assert "15:36:09" in plain
    assert "2026-08-26" in plain
    field.resize(80, 24)
    labels = [star.label for star in field.stars if star.kind == "clock"]
    assert sorted(labels) == ["date", "time"]


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
        assert not line.startswith("load")


async def test_screensaver_help_bar_types_command_help(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await submit(pilot, ":screensaver")
        await pilot.pause()
        assert isinstance(app.screen, DevopsScreensaver)
        help_bar = app.screen.query_one("#ss-help")
        assert app.screen._help.current in COMMAND_HELP_LINES
        for _ in range(8):
            app.screen._tick()
        line = app.screen._help.render_line(80).plain
        assert len(line) == 80
        assert help_bar.visible


async def test_screensaver_host_bar_shows_load_and_mem(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await submit(pilot, ":screensaver")
        await pilot.pause()
        assert isinstance(app.screen, DevopsScreensaver)
        help_bar = app.screen.query_one("#ss-help")
        app.screen._paint()
        line = overlay_host_on_help(
            app.screen._help.render_line(80),
            app.screen._host.snapshot,
            80,
        ).plain
        assert len(line) == 80
        assert "load" in line
        assert "mem" in line
        assert not line.startswith("load")
        assert help_bar.visible


async def test_screensaver_stars_off_from_settings(isolated_home):
    settings = isolated_home / "settings.yml"
    settings.write_text(
        settings.read_text(encoding="utf-8") + "screensaver_stars: false\n",
        encoding="utf-8",
    )
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await submit(pilot, ":screensaver")
        await pilot.pause()
        assert isinstance(app.screen, DevopsScreensaver)
        assert app.screensaver_stars is False
        assert app.screen._field.stars_enabled is False
        assert all(star.kind == "clock" for star in app.screen._field.stars)


async def test_colon_screensaver_off(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await submit(pilot, ":screensaver 0")
        assert "off" in last_info(app).text_content.lower()
        assert app.screensaver_idle == 0
