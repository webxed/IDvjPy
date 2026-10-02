"""Non-blocking confirmation for safe execution mode."""
from __future__ import annotations

from collections.abc import Callable

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from i18n import t


class SafeModeScreen(ModalScreen[bool]):
    """Enter approves a frozen launch; Escape cancels it."""

    _modal = True
    BINDINGS = [
        Binding("enter", "approve", "Run", show=False),
        Binding("escape", "cancel", "Cancel", show=False),
    ]
    DEFAULT_CSS = """
    SafeModeScreen { align: center middle; background: $background 60%; }
    SafeModeScreen #safe-box { width: 76; max-width: 94%; height: auto; border: round $warning; background: $surface; padding: 1 2; }
    SafeModeScreen #safe-title { text-style: bold; color: $warning; }
    SafeModeScreen #safe-command { margin: 1 0; color: $text-muted; }
    """

    def __init__(self, command: str, risks: tuple[str, ...], **kwargs) -> None:
        super().__init__(**kwargs)
        self._command = command
        self._risks = risks

    def compose(self) -> ComposeResult:
        with Vertical(id="safe-box"):
            yield Static(t("safe.confirm_title"), id="safe-title")
            yield Static(t("safe.confirm_risks", risks=", ".join(self._risks)))
            yield Static(self._command, id="safe-command")
            yield Static(t("safe.confirm_hint"))

    def action_approve(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


def confirm(app: object, command: str, risks: tuple[str, ...], callback: Callable[[], None], cancelled: Callable[[], None] | None = None) -> None:
    """Ask asynchronously; callbacks receive no mutable command input."""
    def done(approved: bool | None) -> None:
        if approved:
            callback()
        elif cancelled is not None:
            cancelled()
    app.push_screen(SafeModeScreen(command, risks), done)
