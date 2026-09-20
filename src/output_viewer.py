"""Полноэкранный просмотр вывода блока на Line API (полный, без обрезки).

Открывается по `:log [N]` и F7. В журнале блок показывает только последние
`CommandBlock.MAX_DISPLAY_LINES` строк; здесь доступен **весь** вывод: строки
рисуются лениво через `render_line` — цена кадра зависит от высоты окна, а не
от длины файла (память — только одна копия исходных строк).

Поиск по тексту: `/` открывает поле ввода, Enter — искать вперёд от текущей
позиции, `n` / `N` — следующее / предыдущее совпадение (с заворотом), Esc в поле
закрывает поиск. Строка совпадения подсвечивается **целиком** — фоном `--hit`
(плюс bold), а не только найденными символами. `f` оставляет на экране только
строки с совпадениями (как фильтр в JSON-вьюере), повторный `f` или Esc
возвращают весь вывод; в режиме фильтра по совпадениям ходят и стрелки `↑` / `↓`.
Enter и Ctrl+C копируют подсвеченную строку в буфер (как Enter в построчном
режиме F2), `y` — путь исходного файла (`source_path`, raw-вид `:md`); `q` / Esc —
закрыть экран.

Строки берутся из `raw_stdout` (настоящие, как F3), секреты не маскируются —
приложение предупреждает об этом в заголовке.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from rich.segment import Segment
from textual import events
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
    """Line-API виджет: рисует только видимые строки списка.

    Список строк — либо весь вывод, либо только совпадения поиска
    (`set_filter`; клавиша `f` в `OutputViewerScreen`).
    """

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
        self._all_lines: list[str] = list(lines)
        self._lines: list[str] = list(lines)
        # Исходные номера видимых строк — только когда включён фильтр.
        self._rows: list[int] = []
        self._filtered = False
        self._pattern = ""
        self._match_row: int | None = None
        longest = max((len(line) for line in self._all_lines), default=1)
        self._max_width = max(1, min(MAX_LINE_WIDTH, longest))
        self.virtual_size = Size(self._max_width, len(self._lines))

    @property
    def line_count(self) -> int:
        """Сколько строк в выводе — всего, независимо от фильтра."""
        return len(self._all_lines)

    @property
    def visible_count(self) -> int:
        """Сколько строк показано сейчас (весь вывод или отобранные)."""
        return len(self._lines)

    @property
    def filtered(self) -> bool:
        """Включён ли режим «только совпадения»."""
        return self._filtered

    def source_line(self, row: int) -> int:
        """1-based номер строки вывода для видимой строки `row`."""
        return self._source_index(row) + 1

    def _source_index(self, row: int) -> int:
        if self._filtered and 0 <= row < len(self._rows):
            return self._rows[row]
        return row

    @property
    def match_row(self) -> int | None:
        """Строка текущего совпадения поиска (или None)."""
        return self._match_row

    @property
    def pattern(self) -> str:
        """Текущий образец поиска."""
        return self._pattern

    def visible_line(self, row: int) -> str:
        """Текст видимой строки `row` (в режиме фильтра — из отобранных)."""
        if 0 <= row < len(self._lines):
            return self._lines[row]
        return ""

    @property
    def current_line(self) -> str:
        """Текст строки под курсором совпадения ("" — курсора нет)."""
        row = self._match_row
        return self.visible_line(row) if row is not None else ""

    def on_key(self, event: events.Key) -> None:
        """↑/↓ — по найденным строкам, пока включён фильтр «только совпадения».

        В режиме фильтра на экране одни совпадения, и построчная прокрутка
        бессмысленна: стрелки ведут подсвеченную строку к соседнему совпадению
        (как `n` / `N`), а вид экрана держит `_jump` экрана. Без фильтра не мешаем
        `ScrollableContainer` прокручивать вывод, поэтому перехватываем клавишу
        только на успешный шаг (иначе событие идёт дальше — к обычной прокрутке).
        """
        if not self._filtered or event.key not in ("up", "down"):
            return
        walk = getattr(self.screen, "walk_matches", None)
        if callable(walk) and walk(-1 if event.key == "up" else 1):
            event.stop()

    def set_pattern(self, pattern: str) -> None:
        """Задать образец поиска (сбрасывает совпадение и фильтр «только совпадения»)."""
        self._pattern = pattern or ""
        self._match_row = None
        if self._filtered:
            self.set_filter(False)
        self.refresh()

    def set_filter(self, enabled: bool) -> int:
        """Оставить только строки с совпадениями (`enabled`) или весь вывод.

        Возвращает число видимых строк. Если совпадений нет, фильтр не
        включается — пустой экран без объяснения хуже полного списка (вызов
        остаётся за вызывающим: он говорит «No match»). Индекс совпадения
        пересчитывается так, чтобы не потерять место при включении/выключении.
        """
        pattern = self._pattern.casefold()
        current = None if self._match_row is None else self._source_index(self._match_row)
        rows = (
            [i for i, line in enumerate(self._all_lines) if pattern in line.casefold()]
            if enabled and pattern
            else []
        )
        if enabled and not rows:
            if self._filtered:
                self.set_filter(False)
            return 0
        self._filtered = bool(enabled)
        self._rows = rows
        self._lines = (
            [self._all_lines[i] for i in rows] if enabled else list(self._all_lines)
        )
        self.virtual_size = Size(self._max_width, len(self._lines))
        if enabled:
            self._match_row = rows.index(current) if current in rows else 0
        else:
            self._match_row = current
        self.scroll_to(y=0, animate=False)
        self.refresh()
        return len(self._lines)

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
        # Стиль строки выбираем сразу, а не через `Strip.apply_style`: в Rich/Textual
        # он сливается как `применяемый + стиль сегмента`, поэтому цвета сегмента
        # (фон чётной/нечётной строки) побеждали бы фон совпадения и от `--hit`
        # оставался бы только `bold` — т. е. подсветка строки не появлялась.
        if row == self._match_row:
            name = "outputview--hit"
        else:
            name = "outputview--even" if row % 2 == 0 else "outputview--odd"
        strip = Strip([Segment(text, self.get_component_rich_style(name))])
        return strip.crop(scroll_x, scroll_x + width)


class OutputViewerScreen(ModalScreen[None]):
    """Модальный экран: полный вывод блока с прокруткой и поиском.

    Esc / q — закрыть (сначала — поле поиска, затем фильтр «только совпадения»),
    `/` — поиск, Enter — искать вперёд, `n` / `N` — следующее / предыдущее
    совпадение, `f` — оставить только строки с совпадениями, в этом режиме по
    совпадениям ходят и стрелки `↑` / `↓` (обрабатывает `OutputView` — виджету
    с фокусом их иначе забирает `ScrollableContainer`). Enter и Ctrl+C копируют
    подсвеченную строку в буфер: Enter — привязкой экрана, Ctrl+C — методом
    `copy_shortcut` (Ctrl+C — priority-binding приложения, до виджетов он не
    доходит; см. `CommandRunner.action_copy_input_or_block`).
    """

    _modal = True

    BINDINGS = [
        Binding("escape", "escape_action", "Close"),
        Binding("q", "close_screen", "Close"),
        Binding("slash", "find_prompt", "Find"),
        Binding("enter", "copy_line", "Copy line"),
        Binding("n", "find_next", "Next"),
        # Shift+N терминал присылает как заглавную `N` (см. json_viewer);
        # `shift+n` — для терминалов с modifyOtherKeys, где модификатор явный.
        Binding("N", "find_prev", "Prev"),
        Binding("shift+n", "find_prev", "Prev", show=False),
        Binding("f", "toggle_filter", "Filter"),
        Binding("y", "copy_path", "Copy path", show=False),
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
        start_line: int | None = None,
        source_path: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._lines = list(lines)
        self._title = title
        self._subtitle = subtitle
        # 1-based строка, к которой прыгнуть при открытии (большие md в raw-виде).
        self._start_line = int(start_line) if start_line and int(start_line) > 0 else None
        # Файл-источник: `y` копирует его полный путь (для `:log` не задан).
        self._source_path = str(source_path) if source_path else None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Input(
            placeholder=(
                "text  ·  Enter — search · n / N — next / prev"
                "  ·  f — matches only (↑ / ↓) · Esc — close field"
            ),
            id="output-search",
        )
        yield OutputView(self._lines, id="output-view")
        yield Footer()

    def on_mount(self) -> None:
        self.title = self._title
        self.sub_title = self._subtitle
        self._search_input().display = False
        self._view().focus()
        if self._start_line is not None:
            self.call_after_refresh(self._jump_to_start)

    def _jump_to_start(self) -> None:
        """Прокрутить и подсветить стартовую строку (после первого layout)."""
        start = self._start_line
        if start is None:
            return
        view = self._view()
        if view.line_count == 0:
            return
        row = min(start - 1, view.line_count - 1)
        view.set_match(row)
        height = max(1, int(view.size.height))
        view.scroll_to(y=max(0, row - height // 3), animate=False)

    def _view(self) -> OutputView:
        return self.query_one(OutputView)

    def _copy(self, text: str) -> bool:
        """Положить текст в буфер через приложение (False — не вышло)."""
        runner: Any = self.app
        copy = getattr(runner, "copy_text", None)
        try:
            if copy is None:
                raise RuntimeError("no clipboard helper")
            copy(text)
        except Exception:
            return False
        return True

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
        was_filtered = view.filtered
        if pattern != view.pattern:
            # Новый образец — начинаем поиск заново; тот же — идём от совпадения.
            view.set_pattern(pattern)
        if was_filtered:
            # Фильтр перестраивается под образец; если совпадений нет, `set_filter`
            # возвращает полный список — тогда ниже скажем «No match».
            view.set_filter(True)
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
        if view.filtered:
            self.sub_title = (
                f"{pattern}  ·  matches {view.visible_count}/{view.line_count}"
                f"  ·  line {view.source_line(row)}"
                f"  ·  ↑↓ / n N — matches  ·  f / Esc — all lines"
            )
        else:
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

    def walk_matches(self, direction: int) -> bool:
        """Сдвинуть подсвеченную строку на соседнее совпадение (`↑` / `↓`).

        True — сдвинулись. Зовётся из `OutputView.on_key` только в режиме фильтра,
        где на экране одни совпадения: шаг — соседняя строка (не новый поиск по
        образцу; `n` / `N` остаются поиском, поэтому разницы в фильтре не видно).
        """
        view = self._view()
        total = view.visible_count
        if not view.pattern or total <= 0:
            return False
        current = view.match_row
        if current is None:
            row = 0 if direction > 0 else total - 1
        else:
            row = (current + direction) % total  # по кругу, как `find`
        self._jump(row, view.pattern)
        return True

    def action_copy_line(self) -> None:
        """Enter / Ctrl+C — подсвеченная строка вывода в буфер.

        «Выделенная» — строка текущего совпадения: её ставит `/`, по ней ходят
        `n` / `N` и стрелки в режиме фильтра. Без поиска выделять нечего, поэтому
        говорим об этом прямо (как `f` без образца), а не копируем первую строку
        наугад; экран при этом не закрывается — можно искать дальше.
        """
        view = self._view()
        row = view.match_row
        if row is None or not (0 <= row < view.visible_count):
            self.sub_title = (
                "Nothing selected: / text, Enter — then Enter / Ctrl+C copies the line"
            )
            return
        text = view.current_line
        line_no = view.source_line(row)
        if not self._copy(text):
            self.sub_title = "Error copying the line to clipboard."
            return
        shown = " ".join(text.split())
        self.sub_title = (
            f"Copied line {line_no}: {shown[:60]}" if shown else f"Copied line {line_no} (empty)"
        )

    def copy_shortcut(self) -> bool:
        """Ctrl+C внутри модалки: текст поля поиска или строка под курсором.

        Ctrl+C — `priority=True` у приложения, такие привязки `App.on_event`
        проверяет раньше виджетов, поэтому до экрана клавиша доходит только через
        приложение (`CommandRunner.action_copy_input_or_block` спрашивает активный
        экран методом `copy_shortcut` — сразу после выделения мышью). Поэтому
        и в поле поиска Ctrl+C копирует текст поля, а не строку вывода.
        """
        search = self._search_input()
        if search.display and search.has_focus:
            text = search.selected_text or (search.value or "")
            if not text:
                self.sub_title = "Nothing to copy: the search box is empty"
                return True
            if not self._copy(text):
                self.sub_title = "Error copying to clipboard."
                return True
            self.sub_title = f"Copied search box ({len(text)} chars)"
            return True
        self.action_copy_line()
        return True

    def action_toggle_filter(self) -> None:
        """`f` — оставить только строки с совпадениями (повторно — весь вывод).

        Работает от текущего образца поиска, поэтому `f` без поиска ничего не
        делает и говорит, чего не хватает. Если совпадений нет — фильтр не
        включается (`set_filter` возвращает 0), журнал не пустеет.
        """
        view = self._view()
        if not view.pattern:
            self.sub_title = "Filter needs a search first: / text, Enter, then f"
            return
        if view.filtered:
            view.set_filter(False)
            row = view.match_row
            if row is not None:
                self._jump(row, view.pattern)
            return
        if not view.set_filter(True):
            self.sub_title = f"No match: {view.pattern}"
            return
        row = view.match_row if view.match_row is not None else 0
        self._jump(row, view.pattern)

    def action_escape_action(self) -> None:
        """Esc: сначала закрыть поле поиска, затем фильтр, затем сам экран."""
        if self._search_input().display:
            self._hide_search()
            return
        if self._view().filtered:
            self.action_toggle_filter()
            return
        self.dismiss(None)

    def action_copy_path(self) -> None:
        """`y` — полный путь исходного файла (raw-вид `:md`) в буфер обмена."""
        if not self._source_path:
            self.sub_title = "No file path to copy (this is block output)."
            return
        if not self._copy(self._source_path):
            self.sub_title = "Error copying the file path to clipboard."
            return
        self.sub_title = f"Path copied: {self._source_path}"

    def action_close_screen(self) -> None:
        self.dismiss(None)
