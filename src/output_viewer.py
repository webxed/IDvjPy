"""Полноэкранный просмотр вывода блока на Line API (полный, без обрезки).

Открывается по `:log [N]` и F7. В журнале блок показывает только последние
`CommandBlock.MAX_DISPLAY_LINES` строк; здесь доступен **весь** вывод: строки
рисуются лениво через `render_line` — цена кадра зависит от высоты окна, а не
от длины файла (память — только одна копия исходных строк).

Поиск по тексту: `/` открывает поле ввода, Enter — искать вперёд от текущей
позиции, `n` / `N` — следующее / предыдущее совпадение (с заворотом), Esc в поле
закрывает поиск. Найденная строка подсвечивается. `q` / Esc — закрыть экран.

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
from textual.widgets import Footer, Header, Input

# Ограничение виртуальной ширины: очень длинные строки (minified JSON) не должны
# раздувать horizontal scrollbar; дальше — обрезка.
MAX_LINE_WIDTH = 4096


class OutputView(ScrollView):
    """Line-API виджет: рисует только видимые строки списка."""

    COMPONENT_CLASSES = {"outputview--even", "outputview--odd", "outputview--hit"}

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
    OutputView .outputview--hit {
        background: $accent 55%;
        color: $text;
        text-style: bold;
    }
    """

    def __init__(self, lines: Sequence[str], **kwargs) -> None:
        super().__init__(**kwargs)
        self._lines: list[str] = list(lines)
        self._pattern = ""
        self._match_row: int | None = None
        longest = max((len(line) for line in self._lines), default=1)
        self._max_width = max(1, min(MAX_LINE_WIDTH, longest))
        self.virtual_size = Size(self._max_width, len(self._lines))

    @property
    def line_count(self) -> int:
        return len(self._lines)

    @property
    def match_row(self) -> int | None:
        """Строка текущего совпадения поиска (или None)."""
        return self._match_row

    @property
    def pattern(self) -> str:
        """Текущий образец поиска."""
        return self._pattern

    def set_pattern(self, pattern: str) -> None:
        """Задать образец поиска (сбрасывает подсветку совпадения)."""
        self._pattern = pattern or ""
        self._match_row = None
        self.refresh()

    def find(self, from_row: int, direction: int = 1) -> int | None:
        """Найти совпадение (регистр не важен), начиная со следующей строки.

        Идёт по кругу: дойдя до конца, продолжает с начала. Возвращает индекс
        строки или None, если образец пуст / ничего не найдено.
        """
        pattern = self._pattern.casefold()
        total = len(self._lines)
        if not pattern or total == 0:
            return None
        step = 1 if direction >= 0 else -1
        for offset in range(1, total + 1):
            row = (from_row + step * offset) % total
            if pattern in self._lines[row].casefold():
                return row
        return None

    def set_match(self, row: int | None) -> None:
        self._match_row = row
        self.refresh()

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
        strip = strip.crop(scroll_x, scroll_x + width)
        if row == self._match_row:
            strip = strip.apply_style(self.get_component_rich_style("outputview--hit"))
        return strip


class OutputViewerScreen(ModalScreen[None]):
    """Модальный экран: полный вывод блока с прокруткой и поиском.

    Esc / q — закрыть (если открыт поиск — сначала закрыть его). `/` — поиск,
    Enter — искать вперёд, `n` / `N` — следующее / предыдущее совпадение.
    """

    _modal = True

    BINDINGS = [
        Binding("escape", "escape_action", "Close"),
        Binding("q", "close_screen", "Close"),
        Binding("slash", "find_prompt", "Find"),
        Binding("n", "find_next", "Next"),
        Binding("shift+n", "find_prev", "Prev"),
    ]

    DEFAULT_CSS = """
    OutputViewerScreen #output-search {
        height: 1;
        border: none;
        padding: 0 1;
        background: $panel;
    }
    """

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
        yield Input(
            placeholder="/text  ·  Enter — search, n/N — next/prev, Esc — close field",
            id="output-search",
        )
        yield OutputView(self._lines, id="output-view")
        yield Footer()

    def on_mount(self) -> None:
        self.title = self._title
        self.sub_title = self._subtitle
        self._search_input().display = False
        self._view().focus()

    def _view(self) -> OutputView:
        return self.query_one(OutputView)

    def _search_input(self) -> Input:
        return self.query_one("#output-search", Input)

    def action_find_prompt(self) -> None:
        """`/` — показать поле поиска и поставить в него фокус."""
        search = self._search_input()
        search.display = True
        search.focus()

    def _hide_search(self) -> None:
        search = self._search_input()
        if search.display:
            search.display = False
        self._view().focus()

    def _run_search(self, direction: int) -> None:
        pattern = (self._search_input().value or "").strip()
        if not pattern:
            self._hide_search()
            return
        view = self._view()
        if pattern != view.pattern:
            # Новый образец — начинаем поиск заново; тот же — идём от совпадения.
            view.set_pattern(pattern)
        current = view.match_row
        from_row = current if current is not None else int(view.scroll_offset.y) - 1
        row = view.find(from_row, direction)
        if row is None:
            self.sub_title = f"No match: {pattern}"
            return
        self._jump(row, pattern)

    def _jump(self, row: int, pattern: str) -> None:
        view = self._view()
        view.set_match(row)
        height = max(1, int(view.size.height))
        view.scroll_to(y=max(0, row - height // 3), animate=False)
        self.sub_title = f"{pattern}  ·  line {row + 1}/{view.line_count}"

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self._run_search(1)
        self._view().focus()

    def action_find_next(self) -> None:
        if not (self._search_input().value or "").strip():
            self.action_find_prompt()
            return
        self._run_search(1)

    def action_find_prev(self) -> None:
        if not (self._search_input().value or "").strip():
            self.action_find_prompt()
            return
        self._run_search(-1)

    def action_escape_action(self) -> None:
        """Esc: сначала закрыть поле поиска, затем сам экран."""
        if self._search_input().display:
            self._hide_search()
            return
        self.dismiss(None)

    def action_close_screen(self) -> None:
        self.dismiss(None)
