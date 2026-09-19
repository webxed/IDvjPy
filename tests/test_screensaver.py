"""DevOps starfield screensaver (Norton Commander-style idle overlay)."""
import asyncio
import time
from contextlib import contextmanager
from datetime import datetime

from rich.style import Style
from rich.text import Text
from textual.app import App as TextualApp
from textual.widgets import Static

from app import CommandRunner
from screensaver import (
    MATRIX_GLYPHS,
    MATRIX_HEAD_STYLE,
    MATRIX_MAX_SPEED,
    MATRIX_MIN_SPEED,
    MATRIX_TAIL_STYLES,
    PAINT_INTERVAL,
    TICK_SECONDS,
    TICKER_SEP,
    DevopsScreensaver,
    HelpTypewriter,
    HostSnapshot,
    HostStats,
    LibraryTicker,
    MatrixRain,
    StarField,
    cells_to_text,
    clock_glyph,
    command_help_lines,
    flatten_command,
    format_bytes_short,
    load_library_reminders,
    overlay_host_on_help,
    parse_meminfo,
    render_host_line,
    ticker_items_from_commands,
)
from tests.conftest import input_widget, last_info, submit, wait_command_done


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
    assert "00ff5f" in str(line.style or "") or any(
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
    assert all("  — " in line for line in command_help_lines())


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


def test_matrix_rain_pace_is_slow_and_smooth():
    """Дождь идёт медленно и ровно: за кадр голова сдвигается меньше чем на полстроки."""
    assert MATRIX_MAX_SPEED * TICK_SECONDS < 0.5
    assert MATRIX_MIN_SPEED > 0.5  # но столбцы не стоят на месте


def test_matrix_rain_columns_fall_and_restart():
    rain = MatrixRain(30, 10, seed=3)
    assert len(rain.columns) == 30
    ys_before = [column.y for column in rain.columns]
    for _ in range(3):
        rain.tick(0.1)
    ys_after = [column.y for column in rain.columns]
    assert all(after > before for before, after in zip(ys_before, ys_after, strict=True))

    # Столбцы доходят до низа и начинаются заново сверху (шаг 0.5 с — дождь медленный).
    restarts = 0
    previous = [column.y for column in rain.columns]
    for _ in range(200):
        rain.tick(0.5)
        current = [column.y for column in rain.columns]
        restarts += sum(1 for was, now in zip(previous, current, strict=True) if now < was)
        previous = current
    assert restarts > 0


def test_matrix_rain_render_uses_glyphs_and_trail():
    rain = MatrixRain(20, 8, seed=11)
    for _ in range(40):
        rain.tick(0.1)
    text = rain.render_text()
    lines = text.plain.split("\n")
    assert len(lines) == 8
    assert all(len(line) == 20 for line in lines)

    glyphs = {ch for ch in text.plain if ch not in " \n"}
    assert glyphs  # дождь нарисован
    assert glyphs <= set(MATRIX_GLYPHS)
    # Голова — самым ярким стилем, хвост затухает в пределах палитры.
    # В `Text` стили лежат разобранными (`Style`), поэтому сравниваем парсы.
    assert Style.parse(MATRIX_HEAD_STYLE) in {span.style for span in text.spans}
    assert {span.style for span in text.spans} <= {
        Style.parse(MATRIX_HEAD_STYLE),
        *(Style.parse(style) for style in MATRIX_TAIL_STYLES),
    }
    assert rain._style_for(0) == MATRIX_HEAD_STYLE
    assert rain._style_for(1) == MATRIX_TAIL_STYLES[0]
    assert rain._style_for(99) == MATRIX_TAIL_STYLES[-1]


def test_matrix_rain_resize_and_seed_are_reproducible():
    first = MatrixRain(40, 12, seed=9)
    second = MatrixRain(40, 12, seed=9)
    for _ in range(10):
        first.tick(0.1)
        second.tick(0.1)
    assert first.render_text().plain == second.render_text().plain

    first.resize(80, 20)
    assert first.width == 80
    assert first.height == 20
    assert len(first.columns) == 80
    assert len(first.render_text().plain.split("\n")) == 20


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


async def test_tty_command_return_does_not_show_screensaver(isolated_home, monkeypatch):
    """Возврат из `> cmd` не встречает заставкой, даже если TTY был долгим.

    Регрессия: таймеры Textual идут и во время `suspend()`, поэтому `> vim` на
    пару минут «зажигал» заставку — она открывалась сразу после выхода из TTY.
    """

    @contextmanager
    def slow_tty(_self):
        # TTY-сессия длиннее screensaver_idle (в тесте — блокирующая пауза, как
        # настоящий subprocess.run в `_run_in_tty`).
        time.sleep(2.5)
        yield

    # Подменяем базовый `App.suspend`: обёртка `CommandRunner.suspend`
    # (пауза + перезапуск простоя) должна отработать как в жизни.
    monkeypatch.setattr(TextualApp, "suspend", slow_tty)
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        app.screensaver_idle = 2.0  # в settings.yml только целые секунды
        app._bump_screensaver_idle()
        await submit(pilot, "> true")
        await pilot.pause()
        await pilot.pause()
        # Сразу после выхода из TTY заставки нет, хотя таймер уже перезрел: до
        # фикса он срабатывал на возврате (`> vim` встречал заставкой).
        assert not isinstance(app.screen, DevopsScreensaver)
        assert app._ss_timer is not None  # и простой отсчитывается заново
        # А после настоящего простоя — открывается как обычно.
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not isinstance(
            app.screen, DevopsScreensaver
        ):
            await asyncio.sleep(0.05)
            await pilot.pause()
        assert isinstance(app.screen, DevopsScreensaver)


async def test_launch_screensaver_waits_out_a_tty_session(isolated_home):
    """Пока TUI спит (`> cmd`), сработавший таймер заставку не открывает."""
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        app.screensaver_idle = 2.0
        app._tty_active = True
        app._ss_bumped_at = time.monotonic() - 10  # таймер давно перезрел
        app._launch_screensaver()
        await pilot.pause()
        assert not isinstance(app.screen, DevopsScreensaver)
        app._tty_active = False


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
        # Отключаем авто-запуск: при idle 0.2с скринсейвер иначе успевает
        # открыться заново, и проверка ловит уже новый экран (флейк).
        app.screensaver_idle = 0
        await pilot.press("escape")
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and isinstance(app.screen, DevopsScreensaver):
            await asyncio.sleep(0.05)
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
        assert app.screen._help.current in command_help_lines()
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
    """`screensaver_stars: false` — звёздное поле без пыли/токенов (матрица выключена)."""
    settings = isolated_home / "settings.yml"
    settings.write_text(
        settings.read_text(encoding="utf-8")
        + "screensaver_matrix: false\nscreensaver_stars: false\n",
        encoding="utf-8",
    )
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await submit(pilot, ":screensaver")
        await pilot.pause()
        assert isinstance(app.screen, DevopsScreensaver)
        assert app.screensaver_matrix is False
        assert app.screensaver_stars is False
        assert isinstance(app.screen._field, StarField)
        assert app.screen._field.stars_enabled is False
        assert all(star.kind == "clock" for star in app.screen._field.stars)


async def test_screensaver_matrix_on_by_default(isolated_home):
    """Матричный дождь — холст по умолчанию (`screensaver_matrix: true`)."""
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await submit(pilot, ":screensaver")
        await pilot.pause()
        assert isinstance(app.screen, DevopsScreensaver)
        assert app.screensaver_matrix is True
        assert app.screen._matrix is True
        assert isinstance(app.screen._field, MatrixRain)
        # Клик/пауза могли не дать ни одного тика — прокручиваем дождь и смотрим холст.
        for _ in range(30):
            app.screen._field.tick(0.08)
        glyphs = {
            ch for ch in app.screen._field.render_text().plain if ch not in " \n"
        }
        assert glyphs
        assert glyphs <= set(MATRIX_GLYPHS)


async def test_screensaver_matrix_off_from_settings(isolated_home):
    """`screensaver_matrix: false` — снова звёздное поле (с пылью, как раньше)."""
    settings = isolated_home / "settings.yml"
    settings.write_text(
        settings.read_text(encoding="utf-8") + "screensaver_matrix: false\n",
        encoding="utf-8",
    )
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await submit(pilot, ":screensaver")
        await pilot.pause()
        assert isinstance(app.screen, DevopsScreensaver)
        assert app.screensaver_matrix is False
        assert isinstance(app.screen._field, StarField)
        assert app.screen._field.stars_enabled is True


async def test_colon_screensaver_switches_canvas(isolated_home):
    """`:screensaver stars` / `:screensaver matrix` показывают другой холст на раз."""
    settings = isolated_home / "settings.yml"
    settings.write_text(
        settings.read_text(encoding="utf-8") + "screensaver_matrix: false\n",
        encoding="utf-8",
    )
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await submit(pilot, ":screensaver stars")
        await pilot.pause()
        assert isinstance(app.screen, DevopsScreensaver)
        assert isinstance(app.screen._field, StarField)
        await pilot.press("x")  # закрыть заставку
        await pilot.pause()

        await submit(pilot, ":screensaver matrix")
        await pilot.pause()
        assert isinstance(app.screen, DevopsScreensaver)
        assert isinstance(app.screen._field, MatrixRain)
        # Настройка не менялась — это только показ.
        assert app.screensaver_matrix is False


async def test_colon_screensaver_usage_on_unknown_arg(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await submit(pilot, ":screensaver nope")
        assert "matrix|stars" in last_info(app).text_content


async def test_forwarded_command_wakes_screensaver(isolated_home):
    """`:send` из другой сессии снимает активный скринсейвер — видно журнал."""
    from session_mailbox import send_message

    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await submit(pilot, ":screensaver")
        await pilot.pause()
        assert isinstance(app.screen, DevopsScreensaver)

        # Команда ждала в ящике, пока приложение показывало скринсейвер.
        send_message(str(isolated_home), "default", "echo forwarded", sender="s2")
        app._poll_session_inbox()
        await pilot.pause()

        assert not isinstance(app.screen, DevopsScreensaver)
        assert "Forwarded" in last_info(app).text_content
        assert input_widget(app).value == "echo forwarded"


async def test_forwarded_run_wakes_screensaver_and_executes(isolated_home):
    """Тот же путь для режима `run` (`:send!`): снять и выполнить."""
    from session_mailbox import MODE_RUN, send_message

    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await submit(pilot, ":screensaver")
        await pilot.pause()
        assert isinstance(app.screen, DevopsScreensaver)

        send_message(
            str(isolated_home), "default", "seq 2", sender="s2", mode=MODE_RUN
        )
        app._poll_session_inbox()
        block = await wait_command_done(app)

        assert not isinstance(app.screen, DevopsScreensaver)
        assert "2" in block.raw_stdout


async def test_colon_screensaver_off(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await submit(pilot, ":screensaver 0")
        assert "off" in last_info(app).text_content.lower()
        assert app.screensaver_idle == 0


async def test_mouse_scroll_resets_screensaver_idle(isolated_home):
    """Колесо мыши — активность: чтение журнала не уходит в скринсейвер."""
    from textual import events

    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        app.screensaver_idle = 30
        app._bump_screensaver_idle()
        first = app._ss_timer
        assert first is not None
        app.on_mouse_scroll_down(events.MouseScrollDown(None, 0, 0, 0, 1, 0, False, False, False))
        app.on_mouse_scroll_up(events.MouseScrollUp(None, 0, 0, 0, -1, 0, False, False, False))
        await pilot.pause()
        assert app._ss_timer is not None and app._ss_timer is not first
        app.screensaver_idle = 0


async def test_mouse_move_resets_screensaver_idle(isolated_home):
    from textual import events

    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        app.screensaver_idle = 30
        app._bump_screensaver_idle()
        first = app._ss_timer
        assert first is not None
        app._ss_move_bump = 0.0  # снять throttle
        app.on_mouse_move(events.MouseMove(None, 0, 0, 0, 0, 0, False, False, False))
        await pilot.pause()
        assert app._ss_timer is not None and app._ss_timer is not first
        app.screensaver_idle = 0


# --- Стоимость кадра: сборка текста, троттлинг отрисовки ----------------------


def test_cells_to_text_groups_style_runs():
    """Кадр собирается кусками по стилю, а не по одной ячейке (было ~9.6k append)."""
    cells = [
        [("a", ""), ("b", ""), ("c", "bold"), ("d", "bold"), ("e", "")],
        [("x", "")],
    ]
    canvas = cells_to_text(cells)
    assert canvas.plain == "abcde\nx"
    # Плейн-текст span'ов не создаёт, «cd» — один span на два одинаковых стиля
    # (раньше был бы один `Text.append` на каждую из 5 ячеек).
    assert len(canvas.spans) == 1
    span = canvas.spans[0]
    assert (span.start, span.end) == (2, 4)
    assert span.style == Style.parse("bold")


def test_cells_to_text_reuses_parsed_styles():
    """Стили палитры парсятся один раз (Rich не кэширует `Style.parse`)."""
    first = cells_to_text([[("a", "bold #00ff5f")]])
    second = cells_to_text([[("b", "bold #00ff5f")]])
    assert first.spans[0].style == second.spans[0].style


def test_matrix_tick_reports_only_visible_changes():
    rain = MatrixRain(20, 8, seed=3)
    rain.columns = []
    rain.version = 0
    assert rain.tick(TICK_SECONDS) is False
    assert rain.version == 0

    rain = MatrixRain(20, 8, seed=3)
    before = rain.version
    assert rain.tick(5.0) is True  # большой шаг — головы пересекли строки
    assert rain.version == before + 1


def test_matrix_flicker_touches_only_visible_rows():
    """Мерцание выбирает строку хвоста в пределах экрана (вне экрана мерцать нечему)."""
    rain = MatrixRain(10, 6, seed=5)
    column = rain.columns[0]
    column.y, column.length = 3.4, 4
    for _ in range(50):
        row = rain._visible_row(column)
        assert row is not None
        assert 0 <= row <= 3

    column.y = -20.0  # хвост целиком над экраном
    assert rain._visible_row(column) is None


def test_starfield_tick_reports_no_change_for_zero_dt():
    field = StarField(60, 20, seed=7, now=lambda: datetime(2026, 1, 1, 12, 0, 0))
    field.tick(0.0)  # первый тик мог досчитать часы
    before = field.version
    assert field.tick(0.0) is False
    assert field.version == before


async def test_paint_is_throttled_and_skips_unchanged_field(isolated_home):
    """Холст перерисовывается не чаще `PAINT_INTERVAL` и только при изменениях поля."""
    assert PAINT_INTERVAL > 0
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await submit(pilot, ":screensaver")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, DevopsScreensaver)
        canvas = screen.query_one("#ss-canvas", Static)
        calls: list[int] = []
        original = canvas.update
        canvas.update = lambda *args, **kwargs: (
            calls.append(1),
            original(*args, **kwargs),
        )[1]

        screen._paint(force=True)
        assert len(calls) == 1
        screen._paint()  # только что рисовали — троттлинг
        assert len(calls) == 1
        screen._last_paint_at = 0.0  # время прошло, но поле не менялось
        screen._paint()
        assert len(calls) == 1
        screen._field.version += 1  # поле изменилось — кадр пересобираем
        screen._last_paint_at = 0.0
        screen._paint()
        assert len(calls) == 2
        app.screensaver_idle = 0
