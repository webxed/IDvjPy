"""Modal Markdown viewer for handbook .md files in the repo."""
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Markdown, Static

REPO_ROOT = Path(__file__).resolve().parent.parent


def _escape_markup(text: str) -> str:
    """`[` → `\\[`: имя/путь пользовательского файла не должны ломать разметку Textual."""
    return (text or "").replace("[", "\\[")


def handbook_md_path(name: str, lang: str | None = None) -> Path | None:
    """Resolve a handbook markdown by basename.

    Seed handbooks moved to ``docs/``; the overview docs (K8S_CHAINS.md) stay
    at the repo root. Search cwd and repo root, each also under ``docs/``.

    ``lang`` (по умолчанию — язык интерфейса) даёт приоритет каталогу языка:
    ``docs/<lang>/NAME`` → ``docs/NAME`` → ``NAME``. Каталогов перевода может
    и не быть — тогда работает базовый (русский) справочник.
    """
    raw = (name or "").strip()
    if not raw or any(sep in raw for sep in ("/", "\\", "..")):
        return None
    base = Path(raw).name
    if not base.lower().endswith(".md"):
        return None
    if lang is None:
        try:
            from i18n import current_language

            lang = current_language()
        except ImportError:  # pragma: no cover - i18n always ships with src/
            lang = None
    code = (lang or "").strip()
    for folder in (Path.cwd(), REPO_ROOT):
        candidates = []
        if code:
            candidates.append(folder / "docs" / code / base)
        candidates.extend((folder / "docs" / base, folder / base))
        for candidate in candidates:
            try:
                candidate.resolve().relative_to(folder.resolve())
            except ValueError:
                continue
            if candidate.is_file():
                return candidate.resolve()
    return None


def resolve_md_path(name: str, extra_dirs: Sequence[str] = ()) -> Path | None:
    """Resolve a markdown file by path (absolute, or relative to extra_dirs/cwd/repo).

    Used by `:rg` results and `:md <path>`: unlike ``handbook_md_path`` (basename
    only) this accepts a path anywhere, e.g. inside an Obsidian vault.
    """
    raw = (name or "").strip()
    if not raw:
        return None
    candidate = Path(os.path.expanduser(raw))
    tries: list[Path] = []
    if candidate.is_absolute():
        tries.append(candidate)
    else:
        for folder in (*extra_dirs, str(Path.cwd())):
            if folder:
                tries.append(Path(os.path.expanduser(folder)) / raw)
        tries.append(REPO_ROOT / raw)
    for path in tries:
        if path.is_file():
            return path.resolve()
    return None


class HandbookMarkdownScreen(ModalScreen[None]):
    """Full-screen formatted Markdown; Esc / q closes.

    Scroll stays inside this screen: the app journal also listens to the
    mouse wheel, so we stop those events here. The file name in the header is
    clickable and `y` copies the full path (`[@click=screen.copy_path]`).
    """

    BINDINGS = [
        Binding("escape", "close_screen", "Close", show=True),
        Binding("q", "close_screen", "Close", show=False),
        Binding("y", "copy_path", "Copy path", show=False),
        Binding("up", "md_up", show=False),
        Binding("down", "md_down", show=False),
        Binding("pageup", "md_page_up", show=False),
        Binding("pagedown", "md_page_down", show=False),
        Binding("home", "md_home", show=False),
        Binding("end", "md_end", show=False),
    ]

    def __init__(
        self,
        path: Path,
        markdown: str,
        line: int | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._path = path
        self._markdown = markdown
        self._line = int(line) if line and int(line) > 0 else None
        self._jump_done = False

    def _title_text(self, tail: str | None = None) -> str:
        """Шапка: имя файла (клик — копия пути) + подсказка или результат копирования."""
        name = _escape_markup(self._path.name)
        line = f"[bold #b794f4] · line {self._line}[/]" if self._line else ""
        if tail is None:
            tail = (
                "[dim]y / click — copy full path · Esc / q — close · "
                "wheel / arrows scroll[/]"
            )
        return f"[@click=screen.copy_path][bold #b794f4]{name}[/][/]{line}  {tail}"

    def compose(self) -> ComposeResult:
        with Vertical(id="md-frame"):
            yield Static(self._title_text(), id="md-title")
            with VerticalScroll(id="md-scroll"):
                yield Markdown(self._markdown, open_links=False, id="md-body")

    def on_mount(self) -> None:
        body = self.query_one("#md-scroll", VerticalScroll)
        body.can_focus = True
        body.focus()
        if self._line is not None:
            self.call_after_refresh(self._scroll_to_line)

    def on_markdown_table_of_contents_updated(
        self, event: Markdown.TableOfContentsUpdated
    ) -> None:
        """Как только документ отрисован — прыгнуть к нужной строке (однократно)."""
        if self._line is not None and not self._jump_done:
            self._scroll_to_line()

    def _scroll_to_line(self, attempt: int = 0) -> None:
        """Прокрутить к блоку, содержащему строку исходника (1-based).

        `MarkdownBlock.source_range` — 0-based полуинтервал [start, end) в строках
        документа; если точного блока ещё нет (рендер асинхронный), пробуем ещё раз.
        """
        if self._line is None or self._jump_done:
            return
        target = self._line - 1
        blocks: list[tuple[int, int, Widget]] = []
        for block in self.query_one(Markdown).query("*"):
            rng = getattr(block, "source_range", None)
            if not rng:
                continue
            start, end = rng
            blocks.append((int(start), int(end), block))
        chosen: Widget | None = next(
            (b for s, e, b in blocks if s <= target < e), None
        )
        if chosen is None:
            before = [(s, b) for s, _end, b in blocks if s <= target]
            if before:
                chosen = max(before, key=lambda item: item[0])[1]
            elif blocks:
                chosen = blocks[0][2]
        if chosen is None:
            if attempt < 12:
                self.set_timer(0.05, lambda: self._scroll_to_line(attempt + 1))
            return
        self._jump_done = True
        try:
            self._body().scroll_to_widget(chosen, top=True)
        except Exception:
            pass

    def _body(self) -> VerticalScroll:
        return self.query_one("#md-scroll", VerticalScroll)

    def action_close_screen(self) -> None:
        if self.app.screen is self:
            self.app.pop_screen()

    def _copy_to_clipboard(self, text: str) -> bool:
        """Скопировать через приложение (как F3/:cmd); при ошибке — False."""
        runner: Any = self.app
        copy = getattr(runner, "copy_text", None)
        if copy is None:
            return False
        try:
            copy(text)
        except Exception:
            return False
        return True

    def action_copy_path(self) -> None:
        """`y` / клик по имени файла — полный путь в буфер обмена."""
        path = str(self._path)
        if self._copy_to_clipboard(path):
            tail = f"[green]copied:[/] [dim]{_escape_markup(path)}[/]"
        else:
            tail = "[red]could not copy the path[/]"
        try:
            self.query_one("#md-title", Static).update(self._title_text(tail))
        except Exception:
            pass

    def action_md_up(self) -> None:
        self._body().scroll_relative(y=-1, animate=False, immediate=True)

    def action_md_down(self) -> None:
        self._body().scroll_relative(y=1, animate=False, immediate=True)

    def action_md_page_up(self) -> None:
        self._body().scroll_page_up(animate=False)

    def action_md_page_down(self) -> None:
        self._body().scroll_page_down(animate=False)

    def action_md_home(self) -> None:
        self._body().scroll_home(animate=False)

    def action_md_end(self) -> None:
        self._body().scroll_end(animate=False)

    def on_mouse_scroll_down(self, event) -> None:
        self._body().scroll_relative(y=3, animate=False, immediate=True)
        event.stop()
        event.prevent_default()

    def on_mouse_scroll_up(self, event) -> None:
        self._body().scroll_relative(y=-3, animate=False, immediate=True)
        event.stop()
        event.prevent_default()

    def on_markdown_link_clicked(self, event: Markdown.LinkClicked) -> None:
        event.stop()
        href = (event.href or "").split("#", 1)[0].strip()
        if href.startswith(("http://", "https://")):
            self.app.open_url(href)
            return
        name = Path(href).name
        opener = getattr(self.app, "action_open_handbook_md", None)
        if opener:
            opener(name)
