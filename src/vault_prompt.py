"""Модалка секретов хранилища: маскированный ввод (`:key …`).

Пароль хранилища и значения записей вводятся точками (Textual `Input(password=True)`),
на экране и в журнале не появляются. Enter — принять, Esc — отмена. С
`confirm=True` спрашиваем дважды: при создании хранилища опечатка в пароле стоила
бы всех записей (в отличие от `$$NAME=…`, где значение можно переписать).

С `comment=True` у поля значения появляется второе, обычное (не маскированное)
поле комментария — ссылки/пометки к ключу. Результат такой модалки — `VaultInput`
(значение + комментарий), а не простая строка.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Static


def _escape_markup(text: str) -> str:
    """Скобки из подсказки не должны стать разметкой Textual."""
    return (text or "").replace("[", "\\[")


@dataclass
class VaultInput:
    """Результат модалки записи: значение (скрытое) и комментарий."""

    value: str
    comment: str = ""


@dataclass(frozen=True)
class TotpView:
    """Что показать в окошке TOTP: `raw` — для буфера, `shown` — для экрана."""

    raw: str
    shown: str
    seconds: int
    bar: str = ""


class VaultSecretScreen(ModalScreen[str | VaultInput | None]):
    """Ввод секрета (и, если `comment=True`, комментария). Возвращает строку,
    `VaultInput` или None (отмена)."""

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
    VaultSecretScreen #vault-comment-label {
        color: $text-muted;
        margin: 1 0 0 0;
    }
    VaultSecretScreen #vault-comment {
        margin: 0 0 1 0;
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
        comment: bool = False,
        comment_value: str = "",
        comment_label: str = "Comment (optional)",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._title = title
        self._prompt = prompt
        self._confirm = bool(confirm)
        self._hint = hint
        self._comment = bool(comment)
        self._comment_value = comment_value or ""
        self._comment_label = comment_label
        self._first: str | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="vault-box"):
            yield Static(_escape_markup(self._title), id="vault-title")
            yield Static(_escape_markup(self._prompt), id="vault-prompt")
            yield Input(password=True, id="vault-input")
            if self._comment:
                yield Static(
                    _escape_markup(self._comment_label), id="vault-comment-label"
                )
                yield Input(value=self._comment_value, id="vault-comment")
            hint = "Enter — accept · Esc — cancel"
            if self._comment:
                hint = "Enter — accept · Tab — comment · Esc — cancel"
            if self._hint:
                hint = f"{_escape_markup(self._hint)}\n{hint}"
            yield Static(hint, id="vault-hint")
            yield Static("", id="vault-error")

    def on_mount(self) -> None:
        self.query_one("#vault-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        # Всегда читаем поле значения по id: Enter мог прийти и из поля комментария
        # (там в `event.value` — комментарий, а не значение).
        value = self.query_one("#vault-input", Input).value or ""
        if self._comment:
            if not value:
                self._show_error("Value is empty")
                return
            comment = self.query_one("#vault-comment", Input).value or ""
            self.dismiss(VaultInput(value=value, comment=comment.strip()))
            return
        if not self._confirm:
            self.dismiss(value)
            return
        if self._first is None:
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
        try:
            self.query_one("#vault-error", Static).update(_escape_markup(text))
        except Exception:
            pass

    def action_cancel(self) -> None:
        self.dismiss(None)


class VaultTotpScreen(ModalScreen[str | None]):
    """Живой TOTP-код: обновляется каждую секунду; Enter/`c` — копировать, Esc — закрыть.

    Секрет сюда не попадает — только текущий одноразовый код (и комментарий
    записи). Код пересчитывается на каждый тик и в момент копирования: если окно
    времени перевернулось, в буфер уйдёт свежий код, а не тот, что нарисован.
    """

    _modal = True

    BINDINGS = [
        Binding("escape", "cancel", "Close", show=False),
        Binding("enter", "copy", "Copy", show=False),
        Binding("c", "copy", "Copy", show=False),
    ]

    DEFAULT_CSS = """
    VaultTotpScreen {
        align: center middle;
        background: $background 60%;
    }
    VaultTotpScreen #totp-box {
        width: 48;
        max-width: 92%;
        height: auto;
        border: round $primary;
        background: $surface;
        padding: 1 2;
    }
    VaultTotpScreen #totp-title {
        text-style: bold;
        color: $accent;
    }
    VaultTotpScreen #totp-code {
        text-style: bold;
        color: $success;
        padding: 1 0;
    }
    VaultTotpScreen #totp-bar {
        color: $text-muted;
    }
    VaultTotpScreen #totp-comment {
        color: $text-muted;
    }
    VaultTotpScreen #totp-hint {
        color: $text-muted;
    }
    """

    def __init__(
        self,
        *,
        title: str,
        provider: Callable[[], TotpView],
        comment: str = "",
        hint: str = "",
        left_template: str = "{sec}s left",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._title = title
        self._provider = provider
        self._comment = comment or ""
        self._hint = hint
        self._left_template = left_template

    def compose(self) -> ComposeResult:
        with Vertical(id="totp-box"):
            yield Static(_escape_markup(self._title), id="totp-title")
            yield Static("", id="totp-code")
            yield Static("", id="totp-bar")
            if self._comment:
                yield Static(_escape_markup(self._comment), id="totp-comment")
            yield Static(_escape_markup(self._hint), id="totp-hint")

    def on_mount(self) -> None:
        self._refresh()
        self.set_interval(1.0, self._refresh)

    def _refresh(self) -> None:
        view = self._provider()
        try:
            self.query_one("#totp-code", Static).update(_escape_markup(view.shown))
            self.query_one("#totp-bar", Static).update(_escape_markup(
                f"{view.bar}  {self._left_template.format(sec=view.seconds)}"
            ))
        except Exception:
            pass

    def action_copy(self) -> None:
        # Свежий код, а не тот, что успел устареть между тиками.
        self.dismiss(self._provider().raw)

    def action_cancel(self) -> None:
        self.dismiss(None)
