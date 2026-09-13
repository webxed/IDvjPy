"""Модальный диалог метки буфера (`:name` / F8).

Метка даёт пайп из выбранного блока без перезапуска источника:
`|@<label> <команда>`. Enter — сохранить, пустое значение — снять метку,
Esc — отмена.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Static


def _escape_markup(text: str) -> str:
    """Скобки из подсказки (имя команды) не должны стать разметкой."""
    return (text or "").replace("[", "\\[")


class BlockLabelScreen(ModalScreen[str | None]):
    """Ввод метки блока. Возвращает строку или None (отмена)."""

    _modal = True

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    DEFAULT_CSS = """
    BlockLabelScreen {
        align: center middle;
        background: $background 60%;
    }
    BlockLabelScreen #label-box {
        width: 60;
        max-width: 90%;
        height: auto;
        border: round $primary;
        background: $surface;
        padding: 1 2;
    }
    BlockLabelScreen #label-title {
        text-style: bold;
        color: $accent;
    }
    BlockLabelScreen #label-input {
        margin: 1 0;
        border: tall $primary-darken-1;
    }
    BlockLabelScreen #label-hint {
        color: $text-muted;
    }
    """

    def __init__(
        self,
        *,
        initial: str = "",
        block_hint: str = "",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._initial = initial or ""
        self._block_hint = block_hint or ""

    def compose(self) -> ComposeResult:
        title = Static(
            "Label block — reuse its output via `|@label <command>`",
            id="label-title",
        )
        field = Input(value=self._initial, placeholder="label", id="label-input")
        hint_body = "Enter — save · empty — remove label · Esc — cancel"
        if self._block_hint:
            hint_body = f"{_escape_markup(self._block_hint)}\n{hint_body}"
        hint = Static(hint_body, id="label-hint")
        with Vertical(id="label-box"):
            yield title
            yield field
            yield hint

    def on_mount(self) -> None:
        field = self.query_one("#label-input", Input)
        field.focus()
        field.select_all()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self.dismiss(event.value)

    def action_cancel(self) -> None:
        self.dismiss(None)
