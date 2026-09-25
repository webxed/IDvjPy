"""Модалка секретов хранилища: маскированный ввод (`:vault …`).

Пароль хранилища и значения записей вводятся точками (Textual
`Input(password=True)`), на экране и в журнале не появляются. Enter — принять,
Esc — отмена. С `confirm=True` спрашиваем дважды: при создании хранилища опечатка
в пароле стоила бы всех записей (в отличие от `$$NAME=…`, где значение можно
переписать).
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Static


def _escape_markup(text: str) -> str:
    """Скобки из подсказки не должны стать разметкой Textual."""
    return (text or "").replace("[", "\\[")


class VaultSecretScreen(ModalScreen[str | None]):
    """Ввод секрета. Возвращает строку или None (отмена)."""

    _modal = True

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    DEFAULT_CSS = """
    VaultSecretScreen {
        align: center middle;
        background: $background 60%;
    }
    VaultSecretScreen #vault-box {
        width: 64;
        max-width: 92%;
        height: auto;
        border: round $primary;
        background: $surface;
        padding: 1 2;
    }
    VaultSecretScreen #vault-title {
        text-style: bold;
        color: $accent;
    }
    VaultSecretScreen #vault-input {
        margin: 1 0;
        border: tall $primary-darken-1;
    }
    VaultSecretScreen #vault-hint {
        color: $text-muted;
    }
    VaultSecretScreen #vault-error {
        color: $error;
    }
    """

    def __init__(
        self,
        *,
        title: str,
        prompt: str,
        confirm: bool = False,
        hint: str = "",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._title = title
        self._prompt = prompt
        self._confirm = bool(confirm)
        self._hint = hint
        self._first: str | None = None
        self._error = ""

    def compose(self) -> ComposeResult:
        with Vertical(id="vault-box"):
            yield Static(_escape_markup(self._title), id="vault-title")
            yield Static(_escape_markup(self._prompt), id="vault-prompt")
            yield Input(password=True, id="vault-input")
            hint = "Enter — accept · Esc — cancel"
            if self._hint:
                hint = f"{_escape_markup(self._hint)}\n{hint}"
            yield Static(hint, id="vault-hint")
            yield Static("", id="vault-error")

    def on_mount(self) -> None:
        self.query_one("#vault-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        value = event.value or ""
        if not self._confirm or self._first is None:
            if not self._confirm:
                self.dismiss(value)
                return
            if not value:
                self._show_error("Empty password")
                return
            self._first = value
            self._show_error("")
            self.query_one("#vault-prompt", Static).update(
                _escape_markup(f"{self._prompt} (repeat)")
            )
            field = self.query_one("#vault-input", Input)
            field.value = ""
            field.focus()
            return
        if value != self._first:
            self._first = None
            self._show_error("Passwords do not match — try again")
            self.query_one("#vault-prompt", Static).update(_escape_markup(self._prompt))
            field = self.query_one("#vault-input", Input)
            field.value = ""
            field.focus()
            return
        self.dismiss(self._first)

    def _show_error(self, text: str) -> None:
        self._error = text
        try:
            self.query_one("#vault-error", Static).update(_escape_markup(text))
        except Exception:
            pass

    def action_cancel(self) -> None:
        self.dismiss(None)
