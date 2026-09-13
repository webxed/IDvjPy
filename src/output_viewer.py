"""Полноэкранный просмотр вывода блока на Line API (полный, без обрезки).

Открывается по `:log [N]` и F7. В журнале блок показывает только последние
`CommandBlock.MAX_DISPLAY_LINES` строк; здесь доступен **весь** вывод: строки
рисуются лениво через `render_line` — цена кадра зависит от высоты окна, а не
от длины файла (память — только одна копия исходных строк).

Строки берутся из `raw_stdout` (настоящие, как F3), секреты не маскируются —
приложение предупреждает об этом в заголовке.
"""
from __future__ import annotations

from collections.abc import Sequence

from rich.segment import Segment
from textual.app import ComposeResult
from textual.binding import Binding
from textual.geometry import Size
from textual.screen import ModalScreen
from textual.scroll_view import ScrollView
from textual.strip import Strip
from textual.widgets import Footer, Header

# Ограничение виртуальной ширины: очень длинные строки (minified JSON) не должны
# раздувать horizontal scrollbar; дальше — обрезка.
MAX_LINE_WIDTH = 4096


class OutputView(ScrollView):
    """Line-API виджет: рисует только видимые строки списка."""

    COMPONENT_CLASSES = {"outputview--even", "outputview--odd"}

    DEFAULT_CSS = """
    OutputView {
        border: round $primary;
    }
    OutputView .outputview--even {
        background: $surface;
        color: $text;
    }
    OutputView .outputview--odd {
        background: $panel;
        color: $text-muted;
    }
    """

    def __init__(self, lines: Sequence[str], **kwargs) -> None:
        super().__init__(**kwargs)
        self._lines: list[str] = list(lines)
        longest = max((len(line) for line in self._lines), default=1)
        self._max_width = max(1, min(MAX_LINE_WIDTH, longest))
        self.virtual_size = Size(self._max_width, len(self._lines))

    @property
    def line_count(self) -> int:
        return len(self._lines)

    def render_line(self, y: int) -> Strip:
        scroll_x, scroll_y = self.scroll_offset
        row = y + scroll_y
        width = self.size.width
        if row < 0 or row >= len(self._lines) or width <= 0:
            return Strip.blank(max(width, 0))
        text = self._lines[row][:MAX_LINE_WIDTH]
        if len(text) < scroll_x + width:
            text = text.ljust(scroll_x + width)
        name = "outputview--even" if row % 2 == 0 else "outputview--odd"
        strip = Strip([Segment(text, self.get_component_rich_style(name))])
        return strip.crop(scroll_x, scroll_x + width)


class OutputViewerScreen(ModalScreen[None]):
    """Модальный экран: полный вывод блока с прокруткой (Esc / q — закрыть)."""

    _modal = True

    BINDINGS = [
        Binding("escape", "close_screen", "Close"),
        Binding("q", "close_screen", "Close"),
    ]

    def __init__(
        self,
        lines: Sequence[str],
        *,
        title: str = "Output",
        subtitle: str = "",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._lines = list(lines)
        self._title = title
        self._subtitle = subtitle

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield OutputView(self._lines, id="output-view")
        yield Footer()

    def on_mount(self) -> None:
        self.title = self._title
        self.sub_title = self._subtitle
        self.query_one(OutputView).focus()

    def action_close_screen(self) -> None:
        self.dismiss(None)
