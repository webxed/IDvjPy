"""Песочница Textual Line API (ветка `line-api-experiments`) — без `src/`.

Изолированный скрипт для проверки концепций гайда
https://textual.textualize.io/guide/widgets/ на нашем стеке (Textual 7.3.0).
Ничего не импортирует из приложения: только `textual` и `rich`.

Запуск:

    python3 experiments/line_api_demo.py                # интерактивная TUI
    python3 experiments/line_api_demo.py --lines 50000  # крупнее лог
    python3 experiments/line_api_demo.py --bench 100000 # только замер, без TUI

Демо (переключение цифрами, футер подсказывает):

    1  LineLog    — Line API: `render_line` + `ScrollView` + `virtual_size`.
                    Строки генерируются на лету (O(1) памяти), стиль рядов — из
                    CSS через `COMPONENT_CLASSES`.
    2  StaticLog  — baseline: один большой `Static` + `update()` (как сейчас
                    устроен CommandBlock). Содержимое строится лениво, чтобы
                    честно увидеть цену полного рендера.
    3  StreamLog  — точечные обновления: одна строка за тик, `refresh(Region)`;
                    в border_subtitle видно число region-redraws.
    4  GridDemo   — канонический пример гайда: курсор под мышью, перерисовка
                    только двух клеток (старой и новой) через `var` + `watch_*`.

    r  — сбросить активное демо
    q  — выход

`--bench N` меряет три пути на N строках (без TUI) и печатает отчёт:
построение Strip'ов на лету (Line API), один большой `Text` (Static) и
одиночный Strip (region refresh), плюс пиковую память списка строк.
"""
from __future__ import annotations

import argparse
import time

from rich.segment import Segment
from rich.style import Style
from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.geometry import Offset, Region, Size
from textual.reactive import var
from textual.scroll_view import ScrollView
from textual.strip import Strip
from textual.widgets import ContentSwitcher, Footer, Header, Static

_LEVELS = ("INFO", "WARN", "DEBUG", "ERROR")
_WORKERS = 16
_BAR = "█"


def format_row(row: int) -> str:
    """Правдоподобная строка лога (детерминированная, без random)."""
    level = _LEVELS[(row * 7) % len(_LEVELS)]
    worker = row % _WORKERS
    duration = (row * 37) % 997
    tail = "x" * (row % 8)
    return (
        f"{row:>8}  {level:<5} worker-{worker:<3} "
        f"item={row:<8} dur={duration:>3}ms payload={tail}"
    )


# --- 1. Line API: render_line + ScrollView + virtual_size -------------------


class LineLog(ScrollView):
    """Логи на Line API: строки не хранятся, а генерируются на каждый render_line."""

    COMPONENT_CLASSES = {"linelog--even", "linelog--odd"}

    DEFAULT_CSS = """
    LineLog {
        border: round $primary;
    }
    LineLog .linelog--even {
        background: $surface;
        color: $text;
    }
    LineLog .linelog--odd {
        background: $panel;
        color: $text-muted;
    }
    """

    def __init__(self, total: int = 20000, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._total = total
        self.border_title = f"LineLog — {total} строк, 0 в памяти"

    def on_resize(self, event: events.Resize) -> None:
        self.virtual_size = Size(event.size.width, self._total)

    def restart(self) -> None:
        self.scroll_home(animate=False)
        self.refresh()

    def render_line(self, y: int) -> Strip:
        scroll_x, scroll_y = self.scroll_offset
        row = y + scroll_y
        width = self.size.width
        if row < 0 or row >= self._total or width <= 0:
            return Strip.blank(max(width, 0))
        text = format_row(row)[:width].ljust(width)
        name = "linelog--even" if row % 2 == 0 else "linelog--odd"
        strip = Strip([Segment(text, self.get_component_rich_style(name))], width)
        if scroll_x:
            strip = strip.crop(scroll_x, scroll_x + width)
        return strip


# --- 2. Baseline: один большой Static ---------------------------------------


class StaticLog(ScrollView):
    """Как устроен текущий CommandBlock: всё содержимое — один Static + update()."""

    DEFAULT_CSS = """
    StaticLog {
        border: round $secondary;
    }
    StaticLog Static {
        width: auto;
        height: auto;
    }
    """

    def __init__(self, total: int = 20000, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._total = total
        self._built = False
        self.border_title = f"StaticLog — тот же лог одним Static ({total} строк)"

    def compose(self) -> ComposeResult:
        yield Static("", id="static-body")

    def ensure_content(self) -> None:
        """Собрать весь текст один раз (лениво — иначе старт TUI тормозит)."""
        if self._built:
            return
        started = time.perf_counter()
        body = "\n".join(format_row(row) for row in range(self._total))
        self.query_one("#static-body", Static).update(body)
        self._built = True
        elapsed_ms = (time.perf_counter() - started) * 1000
        self.border_subtitle = (
            f"сборка текста: {elapsed_ms:.0f} ms, {len(body) / 1024:.0f} KiB"
        )

    def restart(self) -> None:
        self.scroll_home(animate=False)


# --- 3. Точечные обновления: refresh(Region) --------------------------------


class StreamLog(ScrollView):
    """Живой дашборд: за тик меняется одна строка, redraw — только её регион."""

    COMPONENT_CLASSES = {"streamlog--bar"}

    DEFAULT_CSS = """
    StreamLog {
        border: round $accent;
    }
    StreamLog .streamlog--bar {
        background: $surface;
        color: $success;
    }
    """

    def __init__(self, rows: int = 24, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._rows = rows
        self._values = [0] * rows
        self._ticks = 0
        self._draws = 0
        self._max = 40
        self.border_title = "StreamLog — один ряд за тик, refresh(Region)"
        self.border_subtitle = "ticks 0 · region redraws 0"

    def on_mount(self) -> None:
        self.virtual_size = Size(self.size.width or 80, self._rows)
        self.set_interval(0.08, self._tick)

    def on_resize(self, event: events.Resize) -> None:
        self.virtual_size = Size(event.size.width, self._rows)

    def _tick(self) -> None:
        row = self._ticks % self._rows
        self._ticks += 1
        self._values[row] = (self._values[row] + 1 + self._ticks % 5) % self._max
        self._draws += 1
        visible_y = row - int(self.scroll_offset.y)
        # Перерисовываем ровно одну строку, а не весь виджет.
        self.refresh(Region(0, visible_y, self.size.width, 1))
        self.border_subtitle = f"ticks {self._ticks} · region redraws {self._draws}"

    def restart(self) -> None:
        self._values = [0] * self._rows
        self._ticks = 0
        self._draws = 0
        self.refresh()

    def render_line(self, y: int) -> Strip:
        scroll_x, scroll_y = self.scroll_offset
        row = y + scroll_y
        width = self.size.width
        if row < 0 or row >= self._rows or width <= 0:
            return Strip.blank(max(width, 0))
        value = self._values[row]
        bar_width = max(1, width - 18)
        bar_cells = int(value / self._max * bar_width)
        label = f"row {row:>3} |{_BAR * bar_cells:<{bar_width}} {value:>3}"
        text = label[:width].ljust(width)
        strip = Strip(
            [Segment(text, self.get_component_rich_style("streamlog--bar"))], width
        )
        if scroll_x:
            strip = strip.crop(scroll_x, scroll_x + width)
        return strip


# --- 4. Канонический пример гайда: клетки под курсором -----------------------


class GridDemo(ScrollView):
    """Одноклеточная сетка: при движении мыши перерисовываются 2 клетки."""

    COMPONENT_CLASSES = {"griddemo--cell", "griddemo--cursor"}

    DEFAULT_CSS = """
    GridDemo {
        border: round $warning;
    }
    GridDemo .griddemo--cell {
        background: $surface;
        color: $text-muted;
    }
    GridDemo .griddemo--cursor {
        background: $accent;
        color: $text;
    }
    """

    cursor = var(Offset(0, 0))

    def __init__(self, cols: int = 60, rows: int = 20, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._cols = cols
        self._rows = rows
        self.border_title = "GridDemo — курсор мышью, refresh только 2 клеток"
        self.border_subtitle = "ведите мышью"

    def on_resize(self, event: events.Resize) -> None:
        self.virtual_size = Size(self._cols * 2, self._rows)

    def restart(self) -> None:
        self.cursor = Offset(0, 0)

    def on_mouse_move(self, event: events.MouseMove) -> None:
        pos = event.offset + self.scroll_offset
        self.cursor = Offset(pos.x // 2, pos.y)

    def watch_cursor(self, previous: Offset, current: Offset) -> None:
        def cell_region(cell: Offset) -> Region:
            region = Region(cell.x * 2, cell.y, 2, 1)
            return region.translate(-self.scroll_offset)

        self.refresh(cell_region(previous))
        self.refresh(cell_region(current))

    def render_line(self, y: int) -> Strip:
        scroll_x, scroll_y = self.scroll_offset
        row = y + scroll_y
        width = self.size.width
        if row < 0 or row >= self._rows or width <= 0:
            return Strip.blank(max(width, 0))
        cell_style = self.get_component_rich_style("griddemo--cell")
        cursor_style = self.get_component_rich_style("griddemo--cursor")
        segments = [
            Segment(
                "  ",
                cursor_style if self.cursor == Offset(col, row) else cell_style,
            )
            for col in range(self._cols)
        ]
        strip = Strip(segments)
        # Как в гайде: обрезаем до видимой области (сетка шире вьюпорта).
        return strip.crop(scroll_x, scroll_x + width)


# --- Приложение-песочница ----------------------------------------------------


class LineApiApp(App[None]):
    """Переключение демо цифрами 1–4."""

    TITLE = "Textual Line API sandbox"
    SUB_TITLE = "1 LineLog · 2 StaticLog · 3 StreamLog · 4 GridDemo · r reset · q quit"

    CSS = """
    ContentSwitcher {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("1", "show('line')", "LineLog"),
        Binding("2", "show('static')", "StaticLog"),
        Binding("3", "show('stream')", "StreamLog"),
        Binding("4", "show('grid')", "GridDemo"),
        Binding("r", "restart", "Reset"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, lines: int = 20000) -> None:
        super().__init__()
        self._lines = lines

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with ContentSwitcher(initial="line"):
            yield LineLog(self._lines, id="line")
            yield StaticLog(self._lines, id="static")
            yield StreamLog(24, id="stream")
            yield GridDemo(60, 20, id="grid")
        yield Footer()

    def action_show(self, name: str) -> None:
        self.query_one(ContentSwitcher).current = name
        widget = self.query_one(f"#{name}")
        if isinstance(widget, StaticLog):
            widget.ensure_content()  # baseline строим только когда показали

    def action_restart(self) -> None:
        current_id = self.query_one(ContentSwitcher).current
        if not isinstance(current_id, str):
            return
        widget = self.query_one(f"#{current_id}")
        restart = getattr(widget, "restart", None)
        if callable(restart):
            restart()


# --- Замер -------------------------------------------------------------------


def run_benchmark(total: int, width: int = 120, visible: int = 40, frames: int = 200) -> int:
    """Сравнить стоимость кадра: Line API (visible строк) vs Static (весь текст)."""
    import io
    import tracemalloc

    from rich.console import Console

    style = Style(color="white")

    def one_strip(row: int) -> Strip:
        text = format_row(row)[:width].ljust(width)
        return Strip([Segment(text, style)], width)

    tracemalloc.start()
    started = time.perf_counter()
    lines = [format_row(i) for i in range(total)]
    build_list_s = time.perf_counter() - started
    _, peak_list = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    big = Text("\n".join(lines))
    console = Console(width=width, file=io.StringIO(), no_color=True)

    # Line API: кадр = только видимые строки (scroll не влияет на цену).
    started = time.perf_counter()
    for _ in range(frames):
        for row in range(min(visible, total)):
            one_strip(row)
    line_frame_s = (time.perf_counter() - started) / frames

    # Static: на каждый refresh перерисовывается весь текст целиком.
    started = time.perf_counter()
    console.print(big)
    static_frame_s = time.perf_counter() - started

    # Line API: сгенерировать все N строк один раз (информативно).
    started = time.perf_counter()
    for i in range(total):
        one_strip(i)
    all_strips_s = time.perf_counter() - started

    def ms(seconds: float) -> str:
        return f"{seconds * 1000:,.2f} ms"

    def us(seconds: float) -> str:
        return f"{seconds / total * 1e6:,.2f} µs/строка"

    print(f"Line API sandbox — benchmark (N = {total:,}, width = {width})")
    print("-" * 70)
    print(
        f"КАДР Line API ({min(visible, total)} видимых строк)".ljust(46)
        + f"{ms(line_frame_s):>16}"
    )
    print(f"КАДР Static (весь текст, {total:,} стр.)".ljust(46) + f"{ms(static_frame_s):>16}")
    print("-" * 70)
    print(
        f"один прогон генерации всех {total:,} строк".ljust(46)
        + f"{ms(all_strips_s):>16}  {us(all_strips_s)}"
    )
    print("сборка списка строк".ljust(46) + f"{ms(build_list_s):>16}")
    print(
        "пик памяти на список".ljust(46)
        + f"{peak_list / 1024 / 1024:,.1f} MiB"
    )
    print("текст Static в одном объекте".ljust(46) + f"{len(big.plain) / 1024 / 1024:,.1f} MiB")
    print("-" * 70)
    print("Line API: цена кадра зависит от высоты окна, а не от N; строки не хранятся.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="line_api_demo",
        description="Textual Line API sandbox (experiments branch).",
    )
    parser.add_argument(
        "--bench",
        type=int,
        metavar="N",
        help="run the timing benchmark for N lines and exit (no TUI)",
    )
    parser.add_argument(
        "--lines",
        type=int,
        default=20000,
        help="rows in the LineLog / StaticLog demos (default: 20000)",
    )
    args = parser.parse_args(argv)
    if args.bench:
        return run_benchmark(args.bench)
    LineApiApp(lines=args.lines).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
