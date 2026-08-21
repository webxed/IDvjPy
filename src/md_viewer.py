"""Modal Markdown viewer for handbook .md files in the repo."""
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Markdown, Static

REPO_ROOT = Path(__file__).resolve().parent.parent


def handbook_md_path(name: str) -> Path | None:
    """Resolve a handbook markdown file by basename (cwd, then repo root)."""
    raw = (name or "").strip()
    if not raw or any(sep in raw for sep in ("/", "\\", "..")):
        return None
    base = Path(raw).name
    if not base.lower().endswith(".md"):
        return None
    for folder in (Path.cwd(), REPO_ROOT):
        path = (folder / base).resolve()
        try:
            path.relative_to(folder.resolve())
        except ValueError:
            continue
        if path.is_file():
            return path
    return None


class HandbookMarkdownScreen(ModalScreen[None]):
    """Full-screen formatted Markdown; Esc / q closes.

    Scroll stays inside this screen: the app journal also listens to the
    mouse wheel, so we stop those events here.
    """

    BINDINGS = [
        Binding("escape", "close_screen", "Close", show=True),
        Binding("q", "close_screen", "Close", show=False),
        Binding("up", "md_up", show=False),
        Binding("down", "md_down", show=False),
        Binding("pageup", "md_page_up", show=False),
        Binding("pagedown", "md_page_down", show=False),
        Binding("home", "md_home", show=False),
        Binding("end", "md_end", show=False),
    ]

    def __init__(self, path: Path, markdown: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._path = path
        self._markdown = markdown

    def compose(self) -> ComposeResult:
        with Vertical(id="md-frame"):
            yield Static(
                f"[bold #b794f4]{self._path.name}[/]  [dim]Esc / q — close · wheel / arrows scroll[/]",
                id="md-title",
            )
            with VerticalScroll(id="md-scroll"):
                yield Markdown(self._markdown, open_links=False, id="md-body")

    def on_mount(self) -> None:
        body = self.query_one("#md-scroll", VerticalScroll)
        body.can_focus = True
        body.focus()

    def _body(self) -> VerticalScroll:
        return self.query_one("#md-scroll", VerticalScroll)

    def action_close_screen(self) -> None:
        if self.app.screen is self:
            self.app.pop_screen()

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
