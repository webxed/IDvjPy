# Vibe-Authors: markovskiy.pavel & Gemini, GLM-4.7, CLAUDE
"""
IDvjPy_term - Textual TUI terminal application.

A keyboard-driven terminal interface with persistent tagged command history.
Supports command execution, variable management, and command tagging.

Usage:
    python app.py
"""
import subprocess
import sys
import argparse

# Parse command-line arguments BEFORE importing dependencies
def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="IDvjPy_term - Textual TUI terminal application",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python app.py                    # Run with default instance name
  python app.py --instance-name=user1  # Run with custom instance name
        """
    )
    parser.add_argument(
        '--instance-name',
        type=str,
        default='default',
        help='Instance name for unique .bashrc_term file (default: default)'
    )
    return parser.parse_args()

# Default instance name. CLI --instance-name is applied only in __main__,
# so the app module can be imported by tests without argparse fighting pytest.
INSTANCE_NAME = "default"

# Check dependencies before importing
try:
    import yaml
    import datetime
    import os
    import json
    import database_v2 as database
    import threading
    import re
    import time
    import portalocker
    from typing import Any, List, Optional, Dict, Tuple, Union
    from command_parser_v2 import CommandParser
    from textual import events
    from textual.app import App, ComposeResult, SuspendNotSupported
    from textual.binding import Binding
    from textual.widgets import Header, Footer, Input, Static
    from rich.markup import escape
    from rich.text import Text
    from textual.containers import VerticalScroll, Vertical
    from json_viewer import JSONViewer
    from ingress_analyzer import IngressAnalyzer
    from clipboard import (
        copy_text_to_clipboards,
        paste_text_from_clipboards,
    )
    from shell_env import (
        RE_VAR_NAME,
        expand_aliases,
        load_aliases_from_file,
        parse_bashrc_assignment,
        parse_standalone_cd,
        substitute_variables,
    )
except ImportError as e:
    print(f"Error: Missing dependency - {e}", file=sys.stderr)
    print("Please install required dependencies:", file=sys.stderr)
    print("  pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)


# ============================================================================
# Pre-compiled Regex Patterns (Performance Optimization)
# ============================================================================

RE_ANSI_TAGS = re.compile(r'\x1b\[[0-9;]*m')
RE_RICH_TAGS = re.compile(r'\[/?[^\]]*\]')
RE_COMMAND_REFS = re.compile(r'(?<!!)!([a-zA-Z_0-9]+)\[(\d+)\]|(?<!!)!(\d+)')
RE_SHELL_OPERATORS = re.compile(r'[&|;]')
RE_TAG_TID = re.compile(r'^([a-zA-Z_0-9]+)\[(\d+)\]$')
RE_TAG_MATCH = re.compile(r'^([a-zA-Z_0-9]+)\[(\d+)\]')
RE_DIGIT_MATCH = re.compile(r'^(\d+)')
RE_FORMATTING_TAGS = re.compile(
    r'\[(?:\/)?(?:dim|bold|italic|underline|strike|code|link|inverse|on|off)\]|\[\/\]'
)
RE_TAG_TID_FIND = re.compile(r'!([a-zA-Z_0-9]+)\[(\d+)\]')
RE_GID_FIND = re.compile(r'(?<!!)!(\d+)')
RE_BANG_PARTIAL = re.compile(
    r'^!([A-Za-z_][A-Za-z0-9_]*)(\[(\d*)(\]?))?$'
)
TOKEN_SEPS = frozenset(" \t|&;")


# ============================================================================
# File Locking Utilities with Timeout (Cross-platform)
# ============================================================================

class FileLockTimeoutError(Exception):
    """Raised when file lock cannot be acquired within timeout."""
    pass


def acquire_file_lock(file_obj, timeout_sec: int = 5) -> None:
    """
    Acquire exclusive lock on file with timeout (cross-platform).

    Uses portalocker for cross-platform file locking support:
    - Linux/Unix: fcntl.flock()
    - Windows: msvcrt.locking() or Win32 file locking

    Args:
        file_obj: Open file object (must be opened in a mode that allows locking)
        timeout_sec: Maximum time to wait for lock (default: 5 seconds)

    Raises:
        FileLockTimeoutError: If lock cannot be acquired within timeout
        IOError: If locking operation fails
    """
    start_time = time.time()

    while True:
        try:
            # Try to acquire exclusive lock (non-blocking)
            portalocker.lock(file_obj, portalocker.LOCK_EX)
            return  # Lock acquired successfully
        except portalocker.exceptions.LockException as e:
            # Lock is held by another process
            elapsed = time.time() - start_time
            if elapsed >= timeout_sec:
                raise FileLockTimeoutError(
                    f"Could not acquire file lock after {timeout_sec} seconds"
                )
            # Wait a bit before retrying (100ms)
            time.sleep(0.1)
        except Exception as e:
            # Some other error occurred
            raise IOError(f"Failed to acquire file lock: {e}")


def release_file_lock(file_obj) -> None:
    """
    Release exclusive lock on file (cross-platform).

    Args:
        file_obj: Open file object
    """
    try:
        portalocker.unlock(file_obj)
    except Exception:
        pass  # Lock was already released or file was closed


class LineNavigable:
    """Построчный курсор: F2/Enter включают; Enter копирует и уходит во ввод; Shift+Enter/Ctrl+V дописывают во ввод."""

    def _nav_plain_text(self) -> str:
        return ""

    def _nav_lines(self) -> List[str]:
        text = self._nav_plain_text()
        if text.endswith("\n"):
            text = text[:-1]
        return text.split("\n") if text else [""]

    def _visible_line_index(self, lines: List[str]) -> int:
        try:
            container = self.app.query_one("#results-container", VerticalScroll)
            block_y = int(getattr(self, "virtual_region", self.region).y)
            rel = int(container.scroll_y) - block_y
            return max(0, min(len(lines) - 1, rel))
        except Exception:
            return 0

    def _paint_line_cursor(self) -> None:
        lines = self._nav_lines()
        idx = getattr(self, "line_index", None)
        if idx is None or not (0 <= idx < len(lines)):
            self.update(self._nav_plain_text())
            return
        painted = list(lines)
        painted[idx] = f"[reverse]{painted[idx]}[/reverse]"
        suffix = "\n" if self._nav_plain_text().endswith("\n") else ""
        self.update("\n".join(painted) + suffix)

    def _scroll_cursor_into_view(self) -> None:
        idx = getattr(self, "line_index", None)
        if idx is None:
            return
        try:
            container = self.app.query_one("#results-container", VerticalScroll)
            block_y = int(getattr(self, "virtual_region", self.region).y)
            y = block_y + int(idx)
            top = int(container.scroll_y)
            height = max(1, int(container.size.height))
            if y < top:
                container.scroll_to(y=y, animate=False)
            elif y >= top + height:
                container.scroll_to(y=max(0, y - height + 1), animate=False)
        except Exception:
            pass

    def enter_line_nav(self, notify: bool = True) -> None:
        """Включить режим курсора по строкам."""
        self.line_nav_active = True
        try:
            self.add_class("line-nav")
        except Exception:
            pass
        lines = self._nav_lines()
        if getattr(self, "line_index", None) is None:
            self.line_index = self._visible_line_index(lines)
        else:
            self.line_index = max(0, min(self.line_index, max(0, len(lines) - 1)))
        self._paint_line_cursor()
        self._scroll_cursor_into_view()
        app = getattr(self, "app", None)
        if notify and app is not None:
            app.sub_title = "Line cursor: on (Enter copy+input, Shift+Enter/Ctrl+V append; F2/Esc off)"
            try:
                app.set_timer(app.TIMER_DELAY, app.clear_subtitle)
            except Exception:
                pass

    def jump_to_line(self, idx: int, notify: bool = False) -> None:
        """Перейти на строку и включить построчный курсор (поиск по журналу)."""
        lines = self._nav_lines()
        if not lines:
            return
        self.line_index = max(0, min(int(idx), len(lines) - 1))
        if not getattr(self, "line_nav_active", False):
            self.enter_line_nav(notify=notify)
        else:
            self._paint_line_cursor()
            self._scroll_cursor_into_view()

    def exit_line_nav(self, notify: bool = True) -> None:
        """Выключить режим курсора по строкам."""
        was_on = getattr(self, "line_nav_active", False)
        self.line_nav_active = False
        self.line_index = None
        try:
            self.remove_class("line-nav")
        except Exception:
            pass
        try:
            self.update(self._nav_plain_text())
        except Exception:
            pass
        app = getattr(self, "app", None)
        if notify and was_on and app is not None:
            app.sub_title = "Line cursor: off"
            try:
                app.set_timer(app.TIMER_DELAY, app.clear_subtitle)
            except Exception:
                pass

    def toggle_line_nav(self) -> None:
        if getattr(self, "line_nav_active", False):
            self.exit_line_nav()
        else:
            self.enter_line_nav()

    def _plain_copy_line(self, line: str) -> str:
        text = line.replace("[reverse]", "").replace("[/reverse]", "")
        app = getattr(self, "app", None)
        if app is not None and hasattr(app, "_strip_formatting_tags"):
            text = app._strip_formatting_tags(text)
        return text.rstrip()

    def _current_plain_line(self) -> str:
        lines = self._nav_lines()
        idx = getattr(self, "line_index", None)
        if idx is None or not (0 <= idx < len(lines)):
            return ""
        return self._plain_copy_line(lines[idx])

    def copy_current_line(self) -> str:
        """Копирует текущую строку в буфер. Возвращает скопированный текст."""
        text = self._current_plain_line()
        app = getattr(self, "app", None)
        try:
            copy_text_to_clipboards(text, app)
            if app is not None:
                app.sub_title = getattr(app, "MSG_COPIED", "Copied to clipboard!")
                try:
                    app.set_timer(app.TIMER_DELAY, app.clear_subtitle)
                except Exception:
                    pass
        except Exception:
            if app is not None:
                app.sub_title = "Error copying to clipboard."
                try:
                    app.set_timer(app.TIMER_DELAY, app.clear_subtitle)
                except Exception:
                    pass
            return ""
        return text

    def append_current_line_to_input(self) -> None:
        """Shift+Enter / Ctrl+V: дописать выделенную строку во ввод через пробел."""
        text = self._current_plain_line()
        if not text:
            return
        # Key ctrl+v and terminal Paste often arrive together; keep one append.
        now = time.monotonic()
        if (
            now - getattr(self, "_last_append_at", 0) < 0.08
            and getattr(self, "_last_append_text", None) == text
        ):
            return
        self._last_append_at = now
        self._last_append_text = text
        app = getattr(self, "app", None)
        if app is None:
            return
        try:
            inp = app.query_one(f"#{app.ID_INPUT}", Input)
        except Exception:
            return
        current = inp.value or ""
        if not current:
            new_val = text
        elif current.endswith((" ", "\t")):
            new_val = current + text
        else:
            new_val = current + " " + text
        inp.value = new_val
        inp.cursor_position = len(new_val)
        if getattr(app, "_completion_list", None) is not None:
            app._completion_list.hide()
        app.sub_title = f"Appended to input: {text}"
        try:
            app.set_timer(app.TIMER_DELAY, app.clear_subtitle)
        except Exception:
            pass

    def move_line(self, delta: int) -> bool:
        """Сдвиг курсора на delta строк. False — край блока, пусть журнал скроллится дальше."""
        if not getattr(self, "line_nav_active", False):
            return False
        lines = self._nav_lines()
        if not lines:
            return False
        current = getattr(self, "line_index", None)
        if current is None:
            current = self._visible_line_index(lines)
        nxt = current + delta
        if nxt < 0 or nxt >= len(lines):
            return False
        self.line_index = nxt
        self._paint_line_cursor()
        self._scroll_cursor_into_view()
        return True

    def on_click(self, event: events.Click) -> None:
        """Клик по блоку в журнале — выделить его, не прокручивая к началу."""
        prev = getattr(self.app, "focused", None)
        if (
            prev is not None
            and prev is not self
            and isinstance(prev, LineNavigable)
            and getattr(prev, "line_nav_active", False)
        ):
            prev.exit_line_nav(notify=False)
        self.focus(scroll_visible=False)

    def jump_line(self, where: str) -> None:
        if not getattr(self, "line_nav_active", False):
            return
        lines = self._nav_lines()
        if not lines:
            return
        self.line_index = 0 if where == "home" else len(lines) - 1
        self._paint_line_cursor()
        self._scroll_cursor_into_view()

    def _is_append_line_key(self, event: events.Key) -> bool:
        """Shift+Enter в разных терминалах: shift+enter, ctrl+enter; Ctrl+V — привычный fallback."""
        key = event.key or ""
        if key in ("shift+enter", "ctrl+enter", "ctrl+v"):
            return True
        if (event.character or "") == "\x16":
            return True
        parts = key.split("+")
        if "enter" in parts and "shift" in parts:
            return True
        aliases = getattr(event, "aliases", None) or []
        return any(a in ("shift+enter", "ctrl+enter", "ctrl+v") for a in aliases)

    def action_append_line(self) -> None:
        if getattr(self, "line_nav_active", False):
            self.append_current_line_to_input()

    def action_append_line_or_paste(self) -> None:
        """Ctrl+V: в построчном режиме дописать строку, иначе вставить буфер во ввод."""
        if getattr(self, "line_nav_active", False):
            self.append_current_line_to_input()
        elif hasattr(self.app, "action_paste_clipboard"):
            self.app.action_paste_clipboard()

    def on_paste(self, event: events.Paste) -> None:
        """Многие терминалы шлют Ctrl+V как Paste, а не как клавишу."""
        if getattr(self, "line_nav_active", False):
            self.append_current_line_to_input()
            event.stop()

    def on_key(self, event: events.Key) -> None:
        if self._is_append_line_key(event):
            if getattr(self, "line_nav_active", False):
                self.append_current_line_to_input()
                event.stop()
            return
        if event.key == "enter":
            if getattr(self, "line_nav_active", False):
                self.copy_current_line()
                if hasattr(self.app, "action_focus_input"):
                    self.app.action_focus_input()
            else:
                self.enter_line_nav()
            event.stop()
            return
        if event.key == "escape" and getattr(self, "line_nav_active", False):
            self.exit_line_nav()
            event.stop()
            return
        if not getattr(self, "line_nav_active", False):
            return
        # VerticalScroll тоже слушает ↑/↓/Home/End — останавливаем событие на блоке.
        if event.key == "up":
            if not self.move_line(-1):
                self.app._scroll_journal_and_focus(-1)
            event.stop()
        elif event.key == "down":
            if not self.move_line(1):
                self.app._scroll_journal_and_focus(1)
            event.stop()
        elif event.key == "home":
            self.jump_line("home")
            event.stop()
        elif event.key == "end":
            self.jump_line("end")
            event.stop()

    def action_journal_page_up(self) -> None:
        """PgUp крутит журнал, а не сам блок."""
        self.app._scroll_journal_and_focus(-max(1, int(self.app._journal_page_size())))

    def action_journal_page_down(self) -> None:
        self.app._scroll_journal_and_focus(max(1, int(self.app._journal_page_size())))

    def action_journal_search(self) -> None:
        """/ в журнале — черновик :/ во вводе."""
        self.app.set_input_draft(":/")

    def action_search_next(self) -> None:
        self.app._journal_search(self.app._search_pattern, direction=1, next_only=True)

    def action_search_prev(self) -> None:
        self.app._journal_search(self.app._search_pattern, direction=-1, next_only=True)

    def on_blur(self) -> None:
        self.exit_line_nav(notify=False)


_LINE_NAV_APPEND_BINDINGS = [
    Binding("shift+enter", "append_line", show=False, priority=True),
    Binding("ctrl+enter", "append_line", show=False, priority=True),
    Binding("ctrl+v", "append_line_or_paste", show=False, priority=True),
    Binding("pageup", "journal_page_up", show=False, priority=True),
    Binding("pagedown", "journal_page_down", show=False, priority=True),
    Binding("slash", "journal_search", show=False, priority=True),
    Binding("n", "search_next", show=False, priority=True),
    Binding("shift+n", "search_prev", show=False, priority=True),
]


class CommandBlock(LineNavigable, Static):
    """Виджет для отображения одной команды и её вывода."""
    MAX_DISPLAY_LINES = 300  # Безопасный лимит для рендера в UI
    BINDINGS = _LINE_NAV_APPEND_BINDINGS

    def __init__(self, header: str, raw_stdout: str, raw_stderr: str, return_code: int, source_command: str = "", **kwargs):
        """
        Инициализация блока команды.

        Args:
            header: Заголовок (время, директория, команда).
            raw_stdout: Вывод команды.
            raw_stderr: Ошибки команды.
            return_code: Код возврата.
        """
        self.header = header
        self.raw_stdout = raw_stdout
        self.raw_stderr = raw_stderr
        self.return_code = return_code
        self.source_command = source_command or ""
        self.collapsed = False
        self._truncated = False  # Флаг: вывод был обрезан
        self.pending = True  # True пока не пришёл результат из потока (run_command)
        self.line_index: Optional[int] = None
        self.line_nav_active: bool = False

        # Формируем отображаемый контент
        self.text_content = self._format_output()
        super().__init__(self.text_content, **kwargs)
        self.can_focus = True

    def _simple_mode(self) -> bool:
        """Плоский текст без Rich-тегов — удобнее выделять и копировать строки в терминале."""
        app = getattr(self, "app", None)
        return bool(app and getattr(app, "simple_output_mode", False))

    def _truncate_output(self, text: str) -> str:
        """
        Обрезает вывод для стабильного рендера UI, сохраняя полный raw_stdout.
        Показывает последние строки (обычно самые релевантные).
        """
        lines = text.split('\n')
        if len(lines) <= self.MAX_DISPLAY_LINES:
            self._truncated = False
            return text
        self._truncated = True
        truncated = '\n'.join(lines[-self.MAX_DISPLAY_LINES:])
        hidden = len(lines) - self.MAX_DISPLAY_LINES
        if self._simple_mode():
            return f"(...{hidden} lines truncated for UI stability, F3 copies full output)\n{truncated}"
        return f"[dim](...{hidden} lines truncated for UI stability, F3 copies full output)[/dim]\n{truncated}"

    def _format_output(self) -> str:
        """Форматирует вывод команды."""
        if self.collapsed:
            # Свернутый вид — только заголовок
            if self._simple_mode():
                return f"▶ {self.header}\n"
            indicator = "[dim]▶[/dim]"
            return f"{indicator} {self.header}\n"

        parts = [self.header]

        # Основной вывод (с обрезкой если нужно)
        if self.raw_stdout:
            stdout_display = self._truncate_output(self.raw_stdout.rstrip())
            parts.append(stdout_display)

        # Stderr внизу с подсветкой ошибки
        if self.raw_stderr and self.raw_stderr.strip():
            if self._simple_mode():
                parts.append(f"STDERR:\n{self.raw_stderr.rstrip()}")
            else:
                parts.append(f"[bold red]STDERR:[/bold red]\n{self.raw_stderr.rstrip()}")

        # Return code если != 0
        if self.return_code != 0:
            if self._simple_mode():
                parts.append(f"Exit code: {self.return_code}")
            else:
                parts.append(f"[bold yellow]Exit code: {self.return_code}[/bold yellow]")

        return "\n".join(parts) + "\n\n"

    def _nav_plain_text(self) -> str:
        return self._format_output()

    def toggle_collapse(self) -> None:
        """Переключает состояние сворачивания."""
        self.collapsed = not self.collapsed
        self.exit_line_nav()
        try:
            self.update(self._format_output())
        except Exception:
            # При очень большом выводе может быть ошибка рендеринга
            # В этом случае оставляем блок свернутым
            if not self.collapsed:
                self.collapsed = True
                if self._simple_mode():
                    self.update(f"▶ {self.header}\n(Output too large to display)\n")
                else:
                    self.update(f"[dim]▶[/dim] {self.header}\n[yellow](Output too large to display)[/yellow]\n")

    def update_content(self, raw_stdout: str, raw_stderr: str, return_code: int) -> None:
        """
        Обновляет содержимое блока после завершения выполнения команды в фоновом потоке.
        Безопасно вызывается через call_from_thread.
        """
        self.raw_stdout = raw_stdout
        self.raw_stderr = raw_stderr
        self.return_code = return_code
        self._truncated = False  # Сброс флага при обновлении
        self.pending = False
        self.update(self._format_output())
        if getattr(self, "line_nav_active", False) and getattr(self, "line_index", None) is not None:
            n = len(self._nav_lines())
            self.line_index = min(self.line_index, max(0, n - 1))
            self._paint_line_cursor()

    def on_focus(self) -> None:
        """
        Событие получения фокуса.
        Запоминает этот блок как активный источник для пайпинга.
        """
        if hasattr(self.app, 'active_pipe_source'):
            self.app.active_pipe_source = self

class ClickableCommand(Static):
    """Кликабельный виджет для отображения команды с возможностью клика."""

    def __init__(self, command_ref: str, display_text: str, **kwargs):
        """
        Инициализация кликабельной команды.

        Args:
            command_ref: Ссылка на команду (например, "!deploy[2]")
            display_text: Отображаемый текст (например, "deploy[2]")
        """
        self.command_ref = command_ref
        super().__init__(display_text, **kwargs)

    def on_click(self, event) -> None:
        """Обработчик клика - вставляет команду в input."""
        app = self.app
        if hasattr(app, 'query_one'):
            input_widget = app.query_one(f"#{app.ID_INPUT}", Input)
            input_widget.value = self.command_ref
            input_widget.cursor_position = len(self.command_ref)
            input_widget.focus()
        return False

class InfoBlock(LineNavigable, Static):
    """Виджет для отображения информационных сообщений (не от команд)."""

    BINDINGS = _LINE_NAV_APPEND_BINDINGS

    def __init__(self, text_content: str, **kwargs):
        """
        Инициализация информационного блока.

        Args:
            text_content: Текст для отображения.
        """
        self.text_content = text_content.rstrip() + "\n\n"
        self.line_index: Optional[int] = None
        self.line_nav_active: bool = False
        super().__init__(self.text_content, **kwargs)
        self.can_focus = True

    def _nav_plain_text(self) -> str:
        return self.text_content


class CompletionItem:
    """Один пункт списка подсказок: что показать и что вставить."""

    def __init__(
        self,
        insert: str,
        display: Optional[str] = None,
        replace_token: bool = False,
        add_space: bool = False,
        reopen: bool = False,
    ) -> None:
        self.insert = insert
        self.display = insert if display is None else display
        self.replace_token = replace_token
        self.add_space = add_space
        self.reopen = reopen


class CompletionList(Static):
    """Список подсказок: в потоке layout под полем ввода, не overlay поверх журнала."""

    MIN_VISIBLE_ITEMS = 6
    MAX_VISIBLE_ITEMS = 24
    _CHROME_ROWS = 8  # header + input + footer + list border
    _JOURNAL_MIN_ROWS = 6

    DEFAULT_CSS = """
    CompletionList {
        background: $surface;
        border: round #4a8c58;
        width: 100%;
        height: auto;
        overflow: hidden;
        padding: 0 1;
        display: none;
    }
    CompletionList .selected {
        background: $accent;
        color: $text;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.can_focus = False
        self._items: List[CompletionItem] = []
        self.candidates: List[CompletionItem] = []
        self.window_start: int = 0
        self.selected_index: int = 0
        self.total_candidates: int = 0
        self.preview: str = ""
        self.replace_token: bool = False

    @property
    def all_candidates(self) -> List[str]:
        return [item.insert for item in self._items]

    @property
    def all_displays(self) -> List[str]:
        return [item.display for item in self._items]

    def _visible_capacity(self) -> int:
        """Сколько пунктов влезает: растёт с высотой терминала, журнал не съедаем."""
        height = 24
        try:
            if self.app is not None and self.app.size.height:
                height = int(self.app.size.height)
        except Exception:
            pass
        extra = 1  # строка счётчика всегда
        if self.preview:
            extra += 1
        cap = height - self._CHROME_ROWS - self._JOURNAL_MIN_ROWS - extra
        return max(self.MIN_VISIBLE_ITEMS, min(self.MAX_VISIBLE_ITEMS, cap))

    def _window_status(self) -> str:
        """Всегда видно, полный это список или есть ещё пункты."""
        n = self.total_candidates
        cap = self._visible_capacity()
        if n == 0:
            return "0/0"
        shown = min(cap, n - self.window_start)
        start = self.window_start + 1
        end = self.window_start + shown
        if self.window_start == 0 and end >= n:
            return f"{n}/{n}  all"
        parts = [f"{start}–{end} / {n}"]
        above = self.window_start
        below = n - end
        if above:
            parts.append(f"↑{above}")
        if below:
            parts.append(f"↓{below} more")
        return "  ".join(parts)

    def update_candidates(
        self,
        candidates: List[Union[str, CompletionItem]],
        preview: str = "",
    ) -> None:
        """Обновить список кандидатов и опциональную расшифровку !tag[tid]."""
        items: List[CompletionItem] = []
        for cand in candidates:
            if isinstance(cand, CompletionItem):
                items.append(cand)
            else:
                items.append(CompletionItem(insert=cand, display=cand))
        self._items = items
        self.total_candidates = len(items)
        self.preview = preview or ""
        self.replace_token = any(item.replace_token for item in items)
        self.window_start = 0
        self.selected_index = 0
        if self._items or self.preview:
            self._render_list()
            self.styles.display = "block"
        else:
            self.styles.display = "none"

    def _render_list(self) -> None:
        """Отрисовать список; высота окна = число видимых строк."""
        cap = self._visible_capacity()
        if self.window_start > 0 and self.window_start + cap > len(self._items):
            self.window_start = max(0, len(self._items) - cap)
        window_end = self.window_start + cap
        self.candidates = self._items[self.window_start:window_end]

        lines = []
        if self.preview:
            lines.append(f"[dim]→ {escape(self.preview)}[/dim]")
        for i, item in enumerate(self.candidates):
            global_index = self.window_start + i
            safe = escape(item.display)
            if global_index == self.selected_index:
                lines.append(f"[bold reverse] {safe} [/bold reverse]")
            else:
                lines.append(f" {safe}")

        if self._items:
            lines.append(f"[dim]{escape(self._window_status())}[/dim]")
        self.update("\n".join(lines) if lines else "")
        self.styles.max_height = max(len(lines) + 2, 3)

    def next_item(self) -> None:
        """Следующий элемент."""
        if self._items:
            cap = self._visible_capacity()
            self.selected_index = (self.selected_index + 1) % len(self._items)
            if self.selected_index < self.window_start:
                self.window_start = self.selected_index
            elif self.selected_index >= self.window_start + cap:
                self.window_start = self.selected_index - cap + 1
            self._render_list()

    def prev_item(self) -> None:
        """Предыдущий элемент."""
        if self._items:
            cap = self._visible_capacity()
            self.selected_index = (self.selected_index - 1) % len(self._items)
            if self.selected_index < self.window_start:
                self.window_start = self.selected_index
            elif self.selected_index >= self.window_start + cap:
                self.window_start = self.selected_index - cap + 1
            self._render_list()

    def get_selected(self) -> Optional[str]:
        """Текст для вставки выбранного элемента."""
        item = self.get_selected_item()
        return None if item is None else item.insert

    def get_selected_item(self) -> Optional[CompletionItem]:
        if self._items and 0 <= self.selected_index < len(self._items):
            return self._items[self.selected_index]
        return None

    def is_visible(self) -> bool:
        """Видим ли список."""
        return bool(self._items) or bool(self.preview)

    def hide(self) -> None:
        """Скрыть список."""
        self._items = []
        self.candidates = []
        self.window_start = 0
        self.total_candidates = 0
        self.preview = ""
        self.replace_token = False
        self.styles.display = "none"


class CommandInput(Input):
    """Поле ввода: Tab — в журнал; Ctrl+D — очистить строку."""

    BINDINGS = [
        Binding("tab", "tab_input", show=False, priority=True),
        Binding("shift+insert", "paste_clipboard", show=False, priority=True),
        Binding("ctrl+v", "paste_clipboard", show=False, priority=True),
        Binding("ctrl+d", "clear_input", show=False, priority=True),
    ]

    def __init__(self, **kwargs):
        kwargs.setdefault("select_on_focus", False)
        super().__init__(**kwargs)
        self._completion_list: Optional[CompletionList] = None
        self._applying_completion: bool = False  # Флаг: применяем completion

    def set_completion_list(self, completion_list: 'CompletionList') -> None:
        """Привязать список подсказок (вызывается из App.on_mount)."""
        self._completion_list = completion_list

    def _token_span(self, text: str, pos: int) -> Tuple[int, int]:
        """Границы текущего токена (разделители: пробел, |, &, ;)."""
        pos = max(0, min(pos, len(text)))
        start = pos
        while start > 0 and text[start - 1] not in TOKEN_SEPS:
            start -= 1
        end = pos
        while end < len(text) and text[end] not in TOKEN_SEPS:
            end += 1
        return start, end

    def _should_replace_last_token(self, selected: str) -> bool:
        """Path-токен заменяем только если кандидат — путь, а не целая команда."""
        clist = self._completion_list
        if clist is not None and getattr(clist, "replace_token", False):
            return True
        item = clist.get_selected_item() if clist is not None else None
        if item is not None and item.replace_token:
            return True
        app = self.app
        if not (hasattr(app, "_is_path_context") and app._is_path_context(self.value)):
            return False
        if any(ch.isspace() for ch in selected.strip()):
            return False
        return True

    def _preview_completion_value(self, selected: str) -> str:
        """Строка ввода после применения кандидата (без изменения поля)."""
        if not self._should_replace_last_token(selected):
            return selected
        current = self.value
        pos = self.cursor_position
        start, end = self._token_span(current, pos)
        return current[:start] + selected + current[end:]

    def _typed_command_is_complete(self) -> bool:
        """Пробел в конце: команда набрана, Enter выполняет её, а не кандидата с аргументами."""
        value = self.value or ""
        return bool(value) and value[-1] in " \t"

    def _apply_selected_completion(self, selected: str) -> bool:
        """
        Применяет выбранное автодополнение.
        В path-контексте и для !tag заменяет только текущий токен, а не всю строку.
        Полная команда из истории/БД всегда подменяет строку целиком
        (иначе `cat json.file` + Enter даёт `cat cat json.file`).
        Возвращает True, если нужно сразу показать подсказки снова.
        """
        item = None
        if self._completion_list is not None:
            item = self._completion_list.get_selected_item()
        self._applying_completion = True
        if not self._should_replace_last_token(selected):
            self.value = selected
            self.cursor_position = len(selected)
            return False

        current = self.value
        pos = self.cursor_position
        start, end = self._token_span(current, pos)
        new_val = current[:start] + selected + current[end:]
        new_pos = start + len(selected)
        add_space = bool(item.add_space) if item is not None else False
        if add_space and end >= len(current) and not selected.endswith(" "):
            new_val += " "
            new_pos += 1
        self.value = new_val
        self.cursor_position = new_pos
        if item is not None:
            return bool(item.reopen)
        return selected.endswith("/")

    def action_tab_input(self) -> None:
        """Tab: применить открытую подсказку, иначе перейти на панель вывода."""
        clist = self._completion_list
        if clist is not None and clist.is_visible():
            selected = clist.get_selected()
            if selected:
                if self._preview_completion_value(selected) != self.value:
                    self._apply_selected_completion(selected)
                    self._applying_completion = False
                    self.call_after_refresh(self._show_completions)
                    return
                # Уже введён готовый каталог (`~/`, `/usr/`): не подменяем дочерним путём.
                clist.hide()
                return
        if hasattr(self.app, "action_focus_output"):
            self.app.action_focus_output()

    def action_paste_clipboard(self) -> None:
        """Shift+Insert / Ctrl+V: системный буфер, не внутренний clipboard Textual."""
        if hasattr(self.app, "action_paste_clipboard"):
            self.app.action_paste_clipboard()

    def action_clear_input(self) -> None:
        """Ctrl+D: удалить всю строку ввода."""
        self.value = ""
        self.cursor_position = 0
        if self._completion_list is not None:
            self._completion_list.hide()

    def on_key(self, event: events.Key) -> None:
        """Обработка клавиш для автодополнения."""
        if not self._completion_list:
            return

        # Навигация по списку. PageUp/PageDown и Esc закрывают список,
        # чтобы журнал оставался доступен мышью и стрелками.
        if self._completion_list.is_visible():
            if event.key in ("pageup", "pagedown"):
                self._completion_list.hide()
                return
            if event.key == "down":
                self._completion_list.next_item()
                event.stop()
                return
            elif event.key == "up":
                self._completion_list.prev_item()
                event.stop()
                return
            elif event.key == "enter":
                if self._typed_command_is_complete():
                    self._completion_list.hide()
                    return
                selected = self._completion_list.get_selected()
                if selected and self._preview_completion_value(selected) != self.value:
                    self._apply_selected_completion(selected)
                    self._applying_completion = False
                    self.call_after_refresh(self._show_completions)
                    event.stop()
                    return
                # Совпадает с уже введённым путём (`ls ~/`) — выполняем команду как есть.
                self._completion_list.hide()
                return
            elif event.key == "escape":
                self._completion_list.hide()
                event.stop()
                return

    def _watch_value(self, value: str) -> None:
        """Вызывается при изменении value (reactive watcher)."""
        # Сначала вызываем родительский метод
        super()._watch_value(value)
        # Не показываем подсказки если применяем completion
        if self._applying_completion:
            self._applying_completion = False
            return
        # Затем показываем подсказки
        self.call_after_refresh(self._show_completions)

    def _show_completions(self) -> None:
        """Показать подсказки."""
        if not self._completion_list:
            return
        app = self.app
        if not hasattr(app, "get_completion_candidates"):
            return

        raw_value = self.value
        bang_items: List[CompletionItem] = []
        preview = ""
        if hasattr(app, "get_bang_completions"):
            bang_items, preview = app.get_bang_completions(raw_value, self.cursor_position)
        if bang_items or preview:
            self._completion_list.update_candidates(bang_items, preview=preview)
            return
        if self._typed_command_is_complete():
            # `ls   ` — выполнить ls, не держать список `ls -la`.
            self._completion_list.hide()
            return
        prefix = raw_value.strip()
        is_path_context = hasattr(app, "_is_path_context") and app._is_path_context(self.value)
        if len(prefix) < 2 and not is_path_context:
            self._completion_list.hide()
            return

        candidates = app.get_completion_candidates(raw_value)
        if candidates:
            # Точная команда уже набрана — не перехватывать Enter повторным apply.
            # Для каталога с / список оставляем, чтобы можно было углубиться.
            if (
                candidates[0] == prefix
                and not prefix.endswith(("/", "\\"))
            ):
                self._completion_list.hide()
                return
            self._completion_list.update_candidates(candidates)
        else:
            self._completion_list.hide()

    def on_mouse_scroll_down(self, event: events.MouseScrollDown) -> None:
        """Колесо над полем ввода — прокрутка области вывода команд (не истории сессии)."""
        app = self.app
        inp = app.query_one(f"#{app.ID_INPUT}", Input)
        if inp.has_focus:
            container = app.query_one(f"#{app.ID_RESULTS_CONTAINER}", VerticalScroll)
            container.scroll_relative(y=1, animate=False, immediate=True)
        else:
            app._scroll_journal_and_focus(1)
        event.stop()

    def on_mouse_scroll_up(self, event: events.MouseScrollUp) -> None:
        app = self.app
        inp = app.query_one(f"#{app.ID_INPUT}", Input)
        if inp.has_focus:
            container = app.query_one(f"#{app.ID_RESULTS_CONTAINER}", VerticalScroll)
            container.scroll_relative(y=-1, animate=False, immediate=True)
        else:
            app._scroll_journal_and_focus(-1)
        event.stop()


class QueryResultsBlock(LineNavigable, Static):
    """
    Виджет для отображения результатов запроса с кликабельными командами.

    Отображает команды в формате:
    <global_id> tag[tid]  command_text
    где tag[tid] является кликабельным.
    """

    BINDINGS = _LINE_NAV_APPEND_BINDINGS

    def __init__(self, content: str, **kwargs):
        """
        Инициализация блока результатов запроса.

        Args:
            content: Текст для отображения (без кликабельных элементов).
        """
        self.text_content = content.rstrip() + "\n\n"
        self.line_index: Optional[int] = None
        self.line_nav_active: bool = False
        super().__init__(self.text_content, **kwargs)
        self.can_focus = True

    def _nav_plain_text(self) -> str:
        return self.text_content


class JournalScroll(VerticalScroll):
    """Журнал: клавиши скролла активируют видимый блок (родитель перехватывает ↑/↓/PgUp раньше App)."""

    def action_scroll_up(self) -> None:
        self.app._scroll_journal_and_focus(-1)

    def action_scroll_down(self) -> None:
        self.app._scroll_journal_and_focus(1)

    def action_page_up(self) -> None:
        height = max(1, int(self.size.height) - 1)
        self.app._scroll_journal_and_focus(-height)

    def action_page_down(self) -> None:
        height = max(1, int(self.size.height) - 1)
        self.app._scroll_journal_and_focus(height)


class CommandRunner(App):
    """Textual приложение для запуска shell команд с поддержкой переменных."""

    CSS_PATH = "app.css"
    BINDINGS = [
        ("escape", "focus_input", "Focus Input"),
        ("f2", "toggle_line_nav", "Line cursor"),
        ("f3", "copy_block", "Copy Block"),
        ("f5", "open_json_viewer", "JSON Viewer"),
        ("f6", "toggle_simple_output", "Simple output"),
        Binding("d", "toggle_dark", "Toggle dark mode", show=False),
        Binding("up", "history_prev", "Previous command", priority=False, show=False),
        Binding("down", "history_next", "Next command", priority=False, show=False),
        Binding("pageup", "journal_page_up", "Prev Block", show=False),
        Binding("pagedown", "journal_page_down", "Next Block", show=False),
        Binding("shift+insert", "paste_clipboard", "Paste", show=False),
        Binding("ctrl+v", "paste_clipboard", "Paste", show=False),
        Binding("space", "toggle_block_collapse", "Collapse", show=False),
        Binding("left", "collapse_block", "← Collapse", show=False),
        Binding("right", "expand_block", "→ Expand", show=False),
    ]

    TITLE = "IDvjPy_term"
    VERSION = "v1.1.52"  # Line-level journal search (:/ :n :N)

    # --- Конфигурация и константы ---
    FILE_SETTINGS = "settings.yml"
    FILE_HISTORY = "history.txt"
    FILE_DATABASE = "mytags.db"
    # FILE_BASHRC теперь уникален для каждого инстанса
    FILE_BASHRC = f".bashrc_term_{INSTANCE_NAME}"  # Файл для хранения локальных переменных
    FILE_BASH_ALIASES = ".bashrc" # Системный файл алиасов

    ID_INPUT = "command-input"
    ID_RESULTS_CONTAINER = "results-container"
    KEY_HISTORY_LINES = "history_lines"
    ENCODING = "utf-8"
    TIMER_DELAY = 2
    COMMAND_TIMEOUT = 10
    FILE_LOCK_TIMEOUT = 5  # Таймаут для получения блокировки файла (секунды)
    DB_RELOAD_INTERVAL = 5  # Интервал перезагрузки БД для актуальности (секунды) 
    
    MSG_COPIED = "Copied to clipboard!"
    MSG_NO_FOCUS = "No command block focused."
    MSG_TIMEOUT = "Process timed out ({sec}s). Killed."
    
    # Префиксы команд
    PREFIX_CMD = ":"
    PREFIX_TAG = "#"
    PREFIX_QUERY = "?"
    PREFIX_BANG = "!"
    PREFIX_DOUBLE_BANG = "!!"
    PREFIX_PIPE = "|"
    PREFIX_VAR = "$" # Новый префикс для переменных
    PREFIX_TTY = ">"
    
    CMD_QUIT = "q"
    CMD_WRITE = "w"
    CMD_HISTORY = "h"
    CMD_CLEAR = "c"
    CMD_JSON = "json"
    CMD_INGRESS = "i"
    CMD_HELP = "?"
    CMD_CD = "cd"
    CMD_REPLAY = "r"
    CMD_GREP = "g"
    CMD_SEARCH_NEXT = "n"
    CMD_SEARCH_PREV = "N"
    CMD_EXPORT = "export"
    CMD_IMPORT = "import"

    def __init__(self):
        """Инициализация состояния приложения."""
        super().__init__()
        self.session_history: List[str] = []
        self.session_history_pos: int = 0
        # Словарь для хранения результатов поиска {ID: Command}
        self.last_query_results: Dict[int, str] = {}
        self.history_lines: int = 20
        self.db_file = self.FILE_DATABASE
        self.active_pipe_source: Optional[CommandBlock] = None
        self.simple_output_mode: bool = False
        # Словарь локальных переменных окружения (имеют приоритет над os.environ)
        self.local_env: Dict[str, str] = {}
        # Словарь для хранения алиасов {alias: command}
        self.aliases: Dict[str, str] = {}
        # v1.1.9+: Парсер команд с поддержкой ссылок
        self.command_parser = CommandParser()
        # Kubernetes Ingress Analyzer
        self.ingress_analyzer: Optional[IngressAnalyzer] = None
        self._old_cwd: Optional[str] = None
        self._search_pattern: str = ""
        self._search_hits: List[Tuple[Static, int]] = []
        self._search_index: int = -1
        self._fresh_command_db: bool = False

    def _extract_path_token(self, text: str) -> str:
        """Возвращает последний токен для path completion."""
        if not text:
            return ""
        if text.endswith(" "):
            return ""
        parts = text.split()
        return parts[-1] if parts else text

    def _last_token_is_path_like(self, token: str) -> bool:
        if not token:
            return False
        return (
            token.startswith(("./", "../", "/", "~"))
            or token in (".", "..", "~")
            or "/" in token
            or "\\" in token
        )

    def _is_path_context(self, text: str) -> bool:
        """
        Path-контекст: последний токен похож на путь, либо аргумент cd/pushd.
        Не любое «два слова»: иначе `cat file` + Enter из истории даёт `cat cat file`.
        """
        stripped = text.rstrip()
        if not stripped:
            return False

        token = self._extract_path_token(text)
        if token.startswith(("!", "#", "?", ":", "$", ">")):
            return False
        if self._last_token_is_path_like(token):
            return True

        parts = stripped.split()
        if len(parts) >= 2 and parts[0] in ("cd", "pushd"):
            return True
        # Относительное имя файла после команды: `cat te` → test.json
        if len(parts) >= 2 and token and not token.startswith("-"):
            return True
        return False

    def _get_file_completion_candidates(self, text: str) -> List[str]:
        """Подсказки файлов/директорий для текущей директории (включая скрытые)."""
        if not self._is_path_context(text):
            return []

        token = self._extract_path_token(text)
        if not token:
            token = ""

        if token.startswith("~"):
            expanded = os.path.expanduser(token)
        else:
            expanded = token

        parent = os.path.dirname(expanded) or "."
        base_prefix = os.path.basename(expanded)

        list_parent = parent
        list_base_prefix = base_prefix
        try:
            entries = os.listdir(list_parent)
        except Exception:
            # Fallback на ближайшую существующую директорию при быстром вводе.
            if "/" not in token and "\\" not in token:
                return []
            probe = expanded.rstrip("/")
            resolved = False
            while probe:
                candidate_parent = os.path.dirname(probe) or "."
                candidate_base = os.path.basename(probe)
                try:
                    entries = os.listdir(candidate_parent)
                    list_parent = candidate_parent
                    list_base_prefix = candidate_base
                    resolved = True
                    break
                except Exception:
                    next_probe = candidate_parent.rstrip("/")
                    if next_probe == probe:
                        break
                    probe = next_probe
            if not resolved:
                return []

        suggestions: List[str] = []
        for name in entries:
            if list_base_prefix and not name.startswith(list_base_prefix):
                continue
            full_path = os.path.join(list_parent, name)
            candidate_path = os.path.join(list_parent, name) if list_parent != "." else name
            if token.startswith("~"):
                home = os.path.expanduser("~")
                if candidate_path.startswith(home):
                    candidate_path = "~" + candidate_path[len(home):]
            # Сохраняем явный пользовательский префикс пути в подсказке.
            elif token.startswith("./") and not candidate_path.startswith("./"):
                candidate_path = f"./{candidate_path}"
            elif token.startswith("../") and not candidate_path.startswith("../"):
                candidate_path = f"../{candidate_path}"
            elif token.startswith("/"):
                candidate_path = full_path
            if os.path.isdir(full_path):
                candidate_path += "/"
            suggestions.append(candidate_path)

        suggestions = sorted(suggestions)
        # Токен уже заканчивается на / — это готовый каталог (`~/`, `./`, `/usr/`).
        # Ставим его первым, чтобы Enter выполнил именно его, а не первого ребёнка.
        if token.endswith("/") or token.endswith("\\"):
            dir_path = os.path.expanduser(token) if token.startswith("~") else token
            if os.path.isdir(dir_path):
                suggestions = [c for c in suggestions if c != token]
                suggestions.insert(0, token)
        return suggestions

    def _bang_token_at_cursor(self, text: str, pos: int) -> Optional[str]:
        """Текущий токен, если это !tag / !tag[ / !tag[tid], но не !!."""
        pos = max(0, min(pos, len(text)))
        start = pos
        while start > 0 and text[start - 1] not in TOKEN_SEPS:
            start -= 1
        token = text[start:pos]
        if not token.startswith("!") or token.startswith("!!"):
            return None
        return token

    def _bang_preview_source(self, text: str) -> str:
        """Часть строки, в которой раскрываются !tag[tid] (тело #tag cmd или вся строка)."""
        stripped = text.strip()
        if not stripped:
            return ""
        if stripped.startswith("#"):
            rest = stripped[1:].lstrip()
            if not rest:
                return ""
            tag, sep, body = rest.partition(" ")
            if not sep or not body.strip():
                return ""
            if tag.endswith(("=", "+", "-")) or "=" in tag:
                return ""
            return body.strip()
        if stripped.startswith((":", "?")):
            return ""
        return stripped

    def _expand_bang_refs_preview(self, text: str) -> str:
        """Живая расшифровка полных ссылок !tag[tid] / !ID во время набора."""
        source = self._bang_preview_source(text)
        if not source or not RE_COMMAND_REFS.search(source):
            return ""

        def repl(match: re.Match) -> str:
            tag, tid, gid = match.group(1), match.group(2), match.group(3)
            try:
                if tag and tid:
                    row = database.get_command_by_tid(self.db_file, tag, int(tid))
                    return row["command"] if row else match.group(0)
                if gid:
                    row = database.get_command_by_global_id(self.db_file, int(gid))
                    return row["command"] if row else match.group(0)
            except Exception:
                return match.group(0)
            return match.group(0)

        expanded = RE_COMMAND_REFS.sub(repl, source)
        if expanded == source:
            return ""
        return expanded

    def _tag_completion_items(self, tags: List[str]) -> List[CompletionItem]:
        """Пункты выбора тега: показ `file`, вставка `!file`."""
        items: List[CompletionItem] = []
        for tag in tags:
            try:
                n = len(database.get_commands_by_tag(self.db_file, tag))
            except Exception:
                n = 0
            items.append(
                CompletionItem(
                    insert=f"!{tag}",
                    display=f"{tag}  ({n})" if n else tag,
                    replace_token=True,
                    add_space=False,
                    reopen=True,
                )
            )
        return items

    def get_bang_completions(
        self, text: str, cursor_pos: int
    ) -> Tuple[List[CompletionItem], str]:
        """
        Подсказки для !file / !kube: в списке полная команда, во ввод — !tag[tid].
        Возвращает (пункты, расшифровка уже набранных ссылок).
        """
        preview = self._expand_bang_refs_preview(text)
        token = self._bang_token_at_cursor(text, cursor_pos)
        if not token:
            return [], preview

        try:
            tags = database.get_all_tags(self.db_file)
        except Exception:
            return [], preview

        if token == "!":
            items = self._tag_completion_items(tags)
            if not preview:
                preview = f"[{', '.join(tags)}]" if tags else ""
            return items, preview

        parsed = RE_BANG_PARTIAL.match(token)
        if not parsed:
            return [], preview

        tag_prefix = parsed.group(1)
        has_bracket = parsed.group(2) is not None
        tid_prefix = parsed.group(3) or ""
        closed = parsed.group(4) == "]"
        if closed:
            return [], preview

        exact = [t for t in tags if t == tag_prefix]
        prefixed = [t for t in tags if t.startswith(tag_prefix)]
        items: List[CompletionItem] = []
        command_tags = exact if exact else (prefixed if len(prefixed) == 1 else [])

        if command_tags:
            tag = command_tags[0]
            try:
                rows = database.get_commands_by_tag(self.db_file, tag)
            except Exception:
                rows = []
            for row in rows:
                tid = row["tid"]
                if tid_prefix and not str(tid).startswith(tid_prefix):
                    continue
                insert = f"!{tag}[{tid}]"
                display = f"<{row['id']}> {tag}[{tid}]  {row['command']}"
                comment = ""
                if "comment" in row.keys() and row["comment"]:
                    comment = str(row["comment"]).strip()
                if comment:
                    display += f"  # {comment}"
                items.append(
                    CompletionItem(
                        insert=insert,
                        display=display,
                        replace_token=True,
                        add_space=True,
                    )
                )
        elif not has_bracket:
            items = self._tag_completion_items(prefixed)
            if not preview and prefixed:
                preview = f"[{', '.join(prefixed)}]"

        return items, preview

    def get_completion_candidates(self, prefix: str) -> List[str]:
        """
        Возвращает список команд из БД и истории сессии по префиксу.
        Для выпадающего списка подсказок.
        """
        raw_prefix = prefix
        prefix = prefix.strip()
        if not raw_prefix:
            return []
        file_cands = self._get_file_completion_candidates(raw_prefix)
        if file_cands:
            # Не смешивать полные команды из БД/истории с путями:
            # иначе Enter подставляет `cat json.file` вместо токена файла.
            return file_cands[:20]

        candidates: List[str] = []
        try:
            from_db = database.get_commands_by_prefix(self.db_file, prefix)
            candidates.extend(from_db)
        except Exception:
            pass
        for cmd in self.session_history:
            if cmd.strip().startswith(prefix):
                candidates.append(cmd.strip())
        return sorted(set(candidates))[:20]

    def on_key(self, event: events.Key) -> None:
        """Перехват клавиш для автофокуса на поле ввода."""
        # Явная вставка из буфера для терминалов, где Shift+Insert ловится нестабильно.
        if event.key in ("shift+insert", "ctrl+v"):
            self.action_paste_clipboard()
            event.stop()
            return

        if event.key in ("pageup", "pagedown") and getattr(self, "_completion_list", None):
            self._completion_list.hide()

        # Если нажата печатаемая клавиша и фокус не на input — переводим фокус
        # Но не перехватываем если фокус на CommandBlock (для сворачивания Space)
        focused = self.focused
        if event.is_printable and not isinstance(focused, LineNavigable):
            input_widget = self.query_one(f"#{self.ID_INPUT}", Input)
            if not input_widget.has_focus:
                input_widget.focus()
                # Клавиша обработается input'ом автоматически

    def on_paste(self, event: events.Paste) -> None:
        """Ctrl+V в терминале часто приходит как Paste, не как клавиша ctrl+v."""
        focused = self.focused
        if isinstance(focused, LineNavigable) and getattr(focused, "line_nav_active", False):
            focused.append_current_line_to_input()
            event.stop()

    def action_paste_clipboard(self) -> None:
        """Вставляет текст из буфера обмена в command input.

        В построчном режиме Ctrl+V дописывает текущую строку, а не буфер.
        """
        focused = self.focused
        if isinstance(focused, LineNavigable) and getattr(focused, "line_nav_active", False):
            focused.append_current_line_to_input()
            return

        clip = paste_text_from_clipboards(self)
        if not clip:
            return

        input_widget = self.query_one(f"#{self.ID_INPUT}", CommandInput)
        if not input_widget.has_focus:
            input_widget.focus()
        current = input_widget.value or ""
        sel = getattr(input_widget, "selection", None)
        if sel is not None and getattr(sel, "start", 0) != getattr(sel, "end", 0):
            # Не затирать уже набранное: вставляем в конец, а не вместо выделения.
            pos = len(current)
        else:
            pos = input_widget.cursor_position
        input_widget.value = current[:pos] + clip + current[pos:]
        input_widget.cursor_position = pos + len(clip)

    def copy_text(self, text: str) -> None:
        """Копирует текст в CLIPBOARD, PRIMARY и внутренний буфер Textual."""
        copy_text_to_clipboards(text or "", self)

    def on_mouse_scroll_down(self, event) -> None:
        """Скролл вниз всегда идёт в контейнер вывода."""
        inp = self.query_one(f"#{self.ID_INPUT}", Input)
        if inp.has_focus:
            container = self.query_one(f"#{self.ID_RESULTS_CONTAINER}", VerticalScroll)
            container.scroll_relative(y=1, animate=False, immediate=True)
        else:
            self._scroll_journal_and_focus(1)
        event.stop()

    def on_mouse_scroll_up(self, event) -> None:
        """Скролл вверх всегда идёт в контейнер вывода."""
        inp = self.query_one(f"#{self.ID_INPUT}", Input)
        if inp.has_focus:
            container = self.query_one(f"#{self.ID_RESULTS_CONTAINER}", VerticalScroll)
            container.scroll_relative(y=-1, animate=False, immediate=True)
        else:
            self._scroll_journal_and_focus(-1)
        event.stop()

    def on_mount(self) -> None:
        """
        Вызывается при старте приложения.
        Загружает настройки, базу данных и переменные окружения.
        """
        # 0. Привязать список подсказок к полю ввода
        cmd_input = self.query_one(f"#{self.ID_INPUT}", CommandInput)
        cmd_input.set_completion_list(self._completion_list)

        # 1. Загрузка общих настроек
        try:
            with open(self.FILE_SETTINGS, "r", encoding=self.ENCODING) as f:
                settings = yaml.safe_load(f)
                if settings:
                    self.history_lines = settings.get(self.KEY_HISTORY_LINES, 20)
                    self.COMMAND_TIMEOUT = settings.get("command_timeout", 10)
                    self.db_file = settings.get("database_tags_file", self.FILE_DATABASE)
        except (FileNotFoundError, KeyError, yaml.YAMLError):
            pass

        # 2. Инициализация базы данных (файл создаётся, если его нет в клоне)
        try:
            database.init_db(self.db_file)
            self._fresh_command_db = not database.has_live_commands(self.db_file)
        except Exception as e:
            self._fresh_command_db = False
            self.sub_title = f"DB Error: {e}"
            self.set_timer(5, self.clear_subtitle)

        # 2.5. Миграция .bashrc_term -> .bashrc_term_{INSTANCE_NAME} для обратной совместимости
        if INSTANCE_NAME != "default":
            # Если существует старый .bashrc_term и нет нового с суффиксом, копируем
            if os.path.exists(".bashrc_term") and not os.path.exists(self.FILE_BASHRC):
                try:
                    import shutil
                    shutil.copy(".bashrc_term", self.FILE_BASHRC)
                    self.add_block(InfoBlock(f"Migrated .bashrc_term -> {self.FILE_BASHRC}"))
                    self.set_timer(3, self.clear_subtitle)
                except Exception as e:
                    pass  # Ошибка миграции не критична

        # 3. Загрузка переменных из файла .bashrc_term
        self.load_bashrc()
        self.load_aliases()

        # 4. Автоматическая загрузка всех команд для работы !!
        # Это позволяет использовать команду !! сразу после запуска без предварительного ??
        self._populate_query_results()

        # 5. Периодическая перезагрузка БД для актуальности при работе нескольких копий
        # Каждые DB_RELOAD_INTERVAL секунд обновляем last_query_results
        self.set_timer(
            self.DB_RELOAD_INTERVAL,
            self._periodic_db_reload
        )

    def _populate_query_results(self) -> None:
        """
        Загружает все команды из БД в last_query_results для работы !! команды.

        Этот метод вызывается автоматически при старте приложения в on_mount()
        и заполняет словарь last_query_results всеми командами из базы данных.

        Преимущества:
        - Команда !! работает сразу после запуска без необходимости выполнять ??
        - Улучшает UX: пользователь может сразу собирать команды по ID

        Структура last_query_results:
        - Ключ: глобальный ID команды (int)
        - Значение: текст команды (str)

        Если загрузка не удалась, словарь остается пустым, и пользователю нужно
        будет выполнить ?? или ?tag перед использованием !!.
        """
        try:
            # Получаем все активные команды из базы данных
            all_commands = database.get_all_commands_with_ids(self.db_file)

            # Очищаем и заполняем словарь результатов
            self.last_query_results = {}
            for row in all_commands:
                # row['id'] - глобальный уникальный ID
                # row['command'] - текст команды для выполнения
                self.last_query_results[row['id']] = row['command']
        except Exception as e:
            # Если база недоступна или есть ошибка, оставляем словарь пустым
            # Пользователь увидит ошибку при попытке использовать !!
            self.last_query_results = {}

    def _periodic_db_reload(self) -> None:
        """
        Периодическая перезагрузка last_query_results для актуальности.

        Вызывается каждые DB_RELOAD_INTERVAL секунд для обновления кэша команд.
        Это обеспечивает актуальность данных при работе нескольких копий приложения
        с общей базой данных.

        Не прерывает работу пользователя, выполняется тихо в фоне.
        """
        try:
            # Получаем все активные команды из базы данных
            all_commands = database.get_all_commands_with_ids(self.db_file)

            # Обновляем словарь результатов (не очищая, чтобы не терять текущий контекст)
            old_size = len(self.last_query_results)
            for row in all_commands:
                # row['id'] - глобальный уникальный ID
                # row['command'] - текст команды для выполнения
                self.last_query_results[row['id']] = row['command']

            # Если количество команд изменилось, можно оповестить пользователя (опционально)
            # Но пока делаем это тихо, чтобы не отвлекать
        except Exception as e:
            # При ошибке просто пропускаем эту перезагрузку
            # Следующая попытка будет через DB_RELOAD_INTERVAL секунд
            pass
        finally:
            # Перезапускаем таймер для следующего цикла
            self.set_timer(self.DB_RELOAD_INTERVAL, self._periodic_db_reload)

    def _parse_bashrc_assignment(self, line: str) -> Optional[tuple]:
        return parse_bashrc_assignment(line)

    def load_bashrc(self) -> None:
        """
        Читает `.bashrc_term_<instance>` и `.bashrc_term`, парсит VAR=val / export VAR=val.

        Инстанс-файл имеет приоритет при совпадении имён; переменные только из
        `.bashrc_term` (как MYVAR) подхватываются, даже если в инстанс-файле уже есть NS.
        """
        # Создаем файл, если его нет (с блокировкой)
        if not os.path.exists(self.FILE_BASHRC):
            try:
                example = ".bashrc_term.example"
                if os.path.exists(example):
                    import shutil
                    shutil.copy(example, self.FILE_BASHRC)
                else:
                    with open(self.FILE_BASHRC, "w", encoding=self.ENCODING) as f:
                        acquire_file_lock(f, self.FILE_LOCK_TIMEOUT)
                        f.write("# Terminal-specific environment variables\n")
                        release_file_lock(f)
            except FileLockTimeoutError:
                with open(self.FILE_BASHRC, "w", encoding=self.ENCODING) as f:
                    f.write("# Terminal-specific environment variables\n")
            except Exception as e:
                self.add_block(InfoBlock(f"Error creating {self.FILE_BASHRC}: {e}"))
                return

        try:
            bashrc_files = [self.FILE_BASHRC]
            if self.FILE_BASHRC != ".bashrc_term" and os.path.exists(".bashrc_term"):
                bashrc_files.append(".bashrc_term")

            seen_keys = set()
            for bashrc_file in bashrc_files:
                if not os.path.exists(bashrc_file):
                    continue

                with open(bashrc_file, "r", encoding=self.ENCODING) as f:
                    try:
                        acquire_file_lock(f, self.FILE_LOCK_TIMEOUT)
                    except FileLockTimeoutError:
                        pass

                    try:
                        for raw_line in f:
                            parsed = self._parse_bashrc_assignment(raw_line)
                            if not parsed:
                                continue
                            key, value = parsed
                            if key in seen_keys:
                                continue
                            seen_keys.add(key)
                            self.local_env[key] = value
                            os.environ[key] = value
                    finally:
                        try:
                            release_file_lock(f)
                        except Exception:
                            pass

        except Exception as e:
            self.add_block(InfoBlock(f"Error loading {self.FILE_BASHRC}: {e}"))

    def load_aliases(self) -> None:
        """
        Читает файл ~/.bashrc, парсит строки alias name='command'
        и заполняет словарь self.aliases.
        """
        home_dir = os.path.expanduser("~")
        alias_file = os.path.join(home_dir, self.FILE_BASH_ALIASES)

        if not os.path.exists(alias_file):
            return

        try:
            self.aliases.update(load_aliases_from_file(alias_file, self.ENCODING))
        except Exception as e:
            self.add_block(InfoBlock(f"Warning: Error loading aliases from {alias_file}: {e}"))

    def on_ready(self) -> None:
        """Приветственное сообщение после загрузки UI."""
        self.add_block(InfoBlock(f"--- {self.TITLE} {self.VERSION} ---"))
        if getattr(self, "_fresh_command_db", False):
            self.add_block(InfoBlock(
                f"Empty command database ({self.db_file}). "
                "Save with #tag cmd, or load the handbook:\n"
                "  python3 seed_linux_commands.py --seed\n"
                "  python3 seed_k8s_chains.py --seed"
            ))
        self._request_shift_enter_encoding()

    def _request_shift_enter_encoding(self) -> None:
        """Просим терминал отличать Shift+Enter от Enter (kitty CSI u / xterm)."""
        try:
            driver = getattr(self, "_driver", None)
            if driver is None:
                return
            # 1=disambiguate, 8=report all keys as escape codes → CSI 13;2u
            driver.write("\x1b[>9u")
            driver.write("\x1b[>4;2m")  # xterm modifyOtherKeys=2
            driver.flush()
        except Exception:
            pass

    def on_unmount(self) -> None:
        try:
            driver = getattr(self, "_driver", None)
            if driver is not None:
                driver.write("\x1b[>4;0m")
        except Exception:
            pass

    def compose(self) -> ComposeResult:
        """Построение UI."""
        yield Header()
        yield CommandInput(placeholder="Enter command (type 2+ chars for completion)", id=self.ID_INPUT)
        self._completion_list = CompletionList()
        yield self._completion_list
        yield JournalScroll(id=self.ID_RESULTS_CONTAINER)
        yield Footer()

    def action_focus_input(self) -> None:
        """Переводит фокус в строку ввода без выделения всего текста."""
        inp = self.query_one(f"#{self.ID_INPUT}", CommandInput)
        inp.focus()
        inp.cursor_position = len(inp.value or "")

    def set_input_draft(self, text: str) -> None:
        """Подставляет черновик команды во ввод (после JSON viewer / jq-пути)."""
        inp = self.query_one(f"#{self.ID_INPUT}", CommandInput)
        inp._applying_completion = True
        inp.value = text
        inp.cursor_position = len(text)
        inp.focus()
        if getattr(self, "_completion_list", None) is not None:
            self._completion_list.hide()

    def _journal_blocks(self) -> List[Static]:
        """Блоки журнала в порядке отображения (команды и системный вывод)."""
        container = self.query_one(f"#{self.ID_RESULTS_CONTAINER}", VerticalScroll)
        return [
            child
            for child in container.children
            if isinstance(child, (CommandBlock, InfoBlock, QueryResultsBlock))
        ]

    def action_focus_output(self) -> None:
        """Переводит фокус на последний блок журнала (:h, :?, команда — что было последним)."""
        if getattr(self, "_completion_list", None) is not None:
            self._completion_list.hide()
        blocks = self._journal_blocks()
        if blocks:
            blocks[-1].focus(scroll_visible=False)
            return
        self.query_one(f"#{self.ID_RESULTS_CONTAINER}", VerticalScroll).focus()

    def _journal_block_span(self, block: Static) -> Tuple[int, int]:
        region = getattr(block, "virtual_region", None) or block.region
        top = int(getattr(region, "y", 0))
        height = max(1, int(getattr(region, "height", 1) or 1))
        return top, height

    def _overlapping_journal_blocks(self) -> List[Static]:
        """Блоки, пересекающиеся с видимой областью журнала (сверху вниз)."""
        try:
            container = self.query_one(f"#{self.ID_RESULTS_CONTAINER}", VerticalScroll)
        except Exception:
            return []
        blocks = self._journal_blocks()
        if not blocks:
            return []
        view_top = int(container.scroll_y)
        view_h = max(1, int(container.size.height) or 1)
        view_bottom = view_top + view_h
        visible: List[Static] = []
        for block in blocks:
            top, height = self._journal_block_span(block)
            if min(top + height, view_bottom) - max(top, view_top) > 0:
                visible.append(block)
        return visible

    def _visible_journal_block(self) -> Optional[Static]:
        """Блок у верхней видимой строки; в конце прокрутки — нижний видимый, если он не доезжает до края."""
        try:
            container = self.query_one(f"#{self.ID_RESULTS_CONTAINER}", VerticalScroll)
        except Exception:
            return None
        blocks = self._journal_blocks()
        if not blocks:
            return None
        view_top = int(container.scroll_y)
        view_h = max(1, int(container.size.height) or 1)
        view_bottom = view_top + view_h
        overlapping: List[Tuple[Static, int, int, int]] = []
        for block in blocks:
            top, height = self._journal_block_span(block)
            overlap = min(top + height, view_bottom) - max(top, view_top)
            if overlap > 0:
                overlapping.append((block, top, height, overlap))
        if not overlapping:
            return blocks[-1]
        max_y = float(getattr(container, "max_scroll_y", 0) or 0)
        at_bottom = float(container.scroll_y) >= max_y - 0.5
        if at_bottom and max_y > 0.5:
            last_block, last_top, _, _ = overlapping[-1]
            if last_top > view_top:
                return last_block
        for block, top, height, _ in overlapping:
            if top <= view_top < top + height:
                return block
        chosen = None
        best = 0
        for block, _top, _height, overlap in overlapping:
            if overlap > best:
                best = overlap
                chosen = block
        return chosen or blocks[-1]

    def _assign_journal_focus(self, chosen: Optional[Static]) -> None:
        """Сфокусировать блок журнала, не прокручивая к его началу."""
        if chosen is None:
            return
        prev = self.focused
        if (
            prev is not None
            and prev is not chosen
            and isinstance(prev, LineNavigable)
            and getattr(prev, "line_nav_active", False)
        ):
            prev.exit_line_nav(notify=False)
        if prev is chosen:
            return
        try:
            self.screen.set_focus(chosen, scroll_visible=False)
        except Exception:
            chosen.focus(scroll_visible=False)

    def _focus_visible_block(self) -> None:
        """Сделать видимый блок активным, не прокручивая журнал к его началу."""
        self._assign_journal_focus(self._visible_journal_block())

    def _focus_adjacent_visible_block(self, direction: int) -> None:
        """Если скролл упёрся в край — перевести фокус на соседний видимый блок."""
        visible = self._overlapping_journal_blocks()
        if not visible:
            return
        current = self.focused
        if current in visible:
            idx = visible.index(current)
            nxt = idx + (1 if direction > 0 else -1)
            if 0 <= nxt < len(visible):
                self._assign_journal_focus(visible[nxt])
            return
        blocks = self._journal_blocks()
        if current in blocks:
            ci = blocks.index(current)
            if direction > 0:
                for block in blocks[ci + 1:]:
                    if block in visible:
                        self._assign_journal_focus(block)
                        return
                self._assign_journal_focus(visible[-1])
            else:
                for block in reversed(blocks[:ci]):
                    if block in visible:
                        self._assign_journal_focus(block)
                        return
                self._assign_journal_focus(visible[0])
            return
        self._assign_journal_focus(visible[-1] if direction > 0 else visible[0])

    def _scroll_journal_and_focus(self, delta: int) -> None:
        """Прокрутить журнал и активировать видимый блок; у края — соседний видимый."""
        try:
            container = self.query_one(f"#{self.ID_RESULTS_CONTAINER}", VerticalScroll)
        except Exception:
            return
        y0 = float(container.scroll_y)
        container.scroll_relative(y=delta, animate=False, immediate=True)
        y1 = float(container.scroll_y)
        direction = 1 if delta > 0 else -1
        if abs(y1 - y0) > 0.25:
            self._focus_visible_block()
            self.call_after_refresh(self._focus_visible_block)
            return
        self._focus_adjacent_visible_block(direction)

    def _enter_journal_view(self) -> None:
        """Из ввода: фокус на последний командный блок, без прыжка вьюпорта."""
        blocks = self._journal_blocks()
        if not blocks:
            return
        commands = [b for b in blocks if isinstance(b, CommandBlock)]
        target = commands[-1] if commands else blocks[-1]
        try:
            self.screen.set_focus(target, scroll_visible=False)
        except Exception:
            target.focus(scroll_visible=False)

    def action_journal_page_up(self) -> None:
        """PgUp: в журнале — страница вверх и активный видимый блок; из ввода — войти в просмотр."""
        if getattr(self, "_completion_list", None) is not None:
            self._completion_list.hide()
        inp = self.query_one(f"#{self.ID_INPUT}", Input)
        if inp.has_focus:
            self._enter_journal_view()
            return
        self._scroll_journal_and_focus(-max(1, int(self._journal_page_size())))

    def action_journal_page_down(self) -> None:
        """PgDn: страница вниз, активный видимый блок; из ввода — войти в просмотр."""
        if getattr(self, "_completion_list", None) is not None:
            self._completion_list.hide()
        inp = self.query_one(f"#{self.ID_INPUT}", Input)
        if inp.has_focus:
            self._enter_journal_view()
            return
        self._scroll_journal_and_focus(max(1, int(self._journal_page_size())))

    def _journal_page_size(self) -> int:
        try:
            container = self.query_one(f"#{self.ID_RESULTS_CONTAINER}", VerticalScroll)
            return max(1, int(container.size.height) - 1)
        except Exception:
            return 10

    def clear_all_blocks(self) -> None:
        """
        Очищает все блоки из контейнера вывода.

        Удаляет все CommandBlock и InfoBlock из нижнего фрейма.
        Используется командой :c для очистки экрана.
        """
        try:
            # Получаем контейнер с результатами
            results_container = self.query_one(f"#{self.ID_RESULTS_CONTAINER}", VerticalScroll)

            # Удаляем всех потомков (CommandBlock и InfoBlock)
            # В Textual нужно вызывать remove() на каждом потомке
            for child in list(results_container.children):
                child.remove()

            self.add_block(InfoBlock("All blocks cleared."))
        except Exception as e:
            self.add_block(InfoBlock(f"Error clearing blocks: {e}"))

    def _scroll_results_end(self) -> None:
        """Прокрутить контейнер результатов вниз. Вызов после refresh даёт корректный layout."""
        container = self.query_one(f"#{self.ID_RESULTS_CONTAINER}", VerticalScroll)
        container.scroll_end()

    def add_block(self, block: Static) -> None:
        """
        Добавляет блок в UI, прокручивает вниз и возвращает фокус во ввод.
        Прокрутка выполняется после refresh; повторная прокрутка после второго refresh
        нужна при первом запуске, когда виртуальный размер контейнера ещё не окончателен.
        """
        container = self.query_one(f"#{self.ID_RESULTS_CONTAINER}", VerticalScroll)
        container.mount(block)
        block.focus()  # Кратковременно фокусируем, чтобы обновить active_pipe_source
        self.query_one(f"#{self.ID_INPUT}", Input).focus()

        # Двойная прокрутка после refresh: при первом запуске один refresh недостаточен для
        # финального virtual size контейнера; вторая прокрутка доводит скролл до конца.
        def scroll_then_repeat() -> None:
            self._scroll_results_end()
            self.call_after_refresh(self._scroll_results_end)

        self.call_after_refresh(scroll_then_repeat)

    def clear_subtitle(self) -> None:
        """Очищает подзаголовок (статус-бар)."""
        self.sub_title = ""

    def _strip_formatting_tags(self, text: str) -> str:
        """
        Удаляет теги форматирования Textual из текста.

        Удаляет только известные теги: [dim], [/], [bold], [/bold], [italic], [/italic],
        [underline], [/underline], [strike], [/strike], [code], [/code] и т.д.
        НЕ трогает содержимое в квадратных скобках: <1>, [1], deploy[tid] и т.д.

        Args:
            text: Текст с тегами форматирования

        Returns:
            Текст без тегов форматирования
        """
        return RE_FORMATTING_TAGS.sub('', text)

    def _pending_block_display(self, block: "CommandBlock") -> str:
        """Текст «команда выполняется» до прихода update_content из потока."""
        if self.simple_output_mode:
            return f"{block.header}\nExecuting...\n(Waiting for output or timeout...)\n"
        return f"{block.header}\n[Executing...]\n(Waiting for output or timeout...)"

    def action_toggle_simple_output(self) -> None:
        """Переключает плоский вид журнала (без разметки) — проще копировать строки мышью."""
        self.simple_output_mode = not self.simple_output_mode
        try:
            for block in self.query(CommandBlock):
                if getattr(block, "pending", False):
                    block.update(self._pending_block_display(block))
                else:
                    block.update(block._format_output())
        except Exception:
            pass
        self.sub_title = (
            "Simple output: on (F6)" if self.simple_output_mode else "Simple output: off (F6)"
        )
        self.set_timer(self.TIMER_DELAY, self.clear_subtitle)

    def action_toggle_line_nav(self) -> None:
        """F2: режим курсора по строкам в блоке вывода."""
        focused = self.focused
        if not isinstance(focused, LineNavigable):
            self.action_focus_output()
            focused = self.focused
            if isinstance(focused, LineNavigable):
                focused.enter_line_nav()
            return
        focused.toggle_line_nav()

    def action_copy_block(self) -> None:
        """Копирует содержимое сфокусированного блока в буфер обмена."""
        focused = self.focused
        if isinstance(focused, CommandBlock):
            try:
                # Для CommandBlock копируем только raw_stdout без заголовка и CompletedProcess
                text_to_copy = focused.raw_stdout

                # Удаляем служебные сообщения, если они есть
                lines_to_remove = [
                    "[Executing...]",
                    "(Waiting for output or timeout...)"
                ]
                for line in lines_to_remove:
                    text_to_copy = text_to_copy.replace(line, "")

                # Удаляем лишние переводы строк
                text_to_copy = text_to_copy.strip()

                copy_text_to_clipboards(text_to_copy, self)
                self.sub_title = self.MSG_COPIED
                self.set_timer(self.TIMER_DELAY, self.clear_subtitle)
            except Exception:
                self.sub_title = "Error copying to clipboard."
                self.set_timer(self.TIMER_DELAY, self.clear_subtitle)
        elif isinstance(focused, InfoBlock):
            try:
                # Для InfoBlock копируем весь текст
                clean_text = self._strip_formatting_tags(focused.text_content)
                copy_text_to_clipboards(clean_text, self)
                self.sub_title = self.MSG_COPIED
                self.set_timer(self.TIMER_DELAY, self.clear_subtitle)
            except Exception:
                self.sub_title = "Error copying to clipboard."
                self.set_timer(self.TIMER_DELAY, self.clear_subtitle)

    def action_toggle_block_collapse(self) -> None:
        """Сворачивает/разворачивает сфокусированный блок."""
        focused = self.focused
        if isinstance(focused, CommandBlock):
            focused.toggle_collapse()
        else:
            self.sub_title = self.MSG_NO_FOCUS
            self.set_timer(self.TIMER_DELAY, self.clear_subtitle)

    def action_collapse_block(self) -> None:
        """Сворачивает сфокусированный блок (стрелка влево)."""
        focused = self.focused
        if isinstance(focused, CommandBlock) and not focused.collapsed:
            focused.toggle_collapse()

    def action_expand_block(self) -> None:
        """Разворачивает сфокусированный блок (стрелка вправо)."""
        focused = self.focused
        if isinstance(focused, CommandBlock) and focused.collapsed:
            focused.toggle_collapse()

    def action_open_json_viewer(self) -> None:
        """
        Открывает JSON viewer для сфокусированного блока (F5).
        Если фокус не на блоке — берём последний CommandBlock.
        """
        block = self._block_for_json_viewer()
        if block is None:
            self.sub_title = "No blocks found."
            self.set_timer(self.TIMER_DELAY, self.clear_subtitle)
            return
        try:
            json_data = self._extract_json(self._text_from_json_block(block))
            if json_data is not None:
                self.push_screen(JSONViewer(json_data))
                self.sub_title = "JSON viewer opened! Press Escape to close."
                self.set_timer(2, self.clear_subtitle)
            else:
                self.sub_title = "No valid JSON found in focused/last block."
                self.set_timer(self.TIMER_DELAY, self.clear_subtitle)
        except Exception as e:
            self.sub_title = f"Error parsing JSON: {e}"
            self.set_timer(self.TIMER_DELAY, self.clear_subtitle)

    def _block_for_json_viewer(self) -> Optional[Static]:
        """Сфокусированный блок вывода или последний CommandBlock."""
        focused = self.focused
        if isinstance(focused, (CommandBlock, InfoBlock, QueryResultsBlock)):
            return focused
        commands = list(self.query(CommandBlock))
        if commands:
            return commands[-1]
        others = list(self.query("InfoBlock, QueryResultsBlock"))
        return others[-1] if others else None

    def _text_from_json_block(self, block: Static) -> str:
        if isinstance(block, CommandBlock):
            return block.raw_stdout or ""
        return self._strip_formatting_tags(getattr(block, "text_content", "") or "")

    def _extract_json(self, text: str) -> Optional[Any]:
        """
        Извлекает JSON из текста (объект, массив или примитив).

        Сначала парсит весь текст, затем ищет первый валидный JSON,
        начиная с `{` или `[` (вывод команды может содержать лишние строки).
        """
        import json

        if not text:
            return None
        raw = text.strip().lstrip("\ufeff")
        if not raw:
            return None

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        decoder = json.JSONDecoder()
        for i, char in enumerate(raw):
            if char not in "{[":
                continue
            try:
                obj, _end = decoder.raw_decode(raw, i)
                return obj
            except json.JSONDecodeError:
                continue
        return None

    def _open_json_file(self, filename: str) -> None:
        """
        Открывает JSON viewer для указанного файла.

        Args:
            filename: Путь к JSON файлу
        """
        import json
        try:
            with open(filename, "r", encoding=self.ENCODING) as f:
                json_data = json.load(f)

            self.push_screen(JSONViewer(json_data))
            self.sub_title = f"JSON viewer opened: {filename}"
            self.set_timer(2, self.clear_subtitle)

        except FileNotFoundError:
            self.add_block(InfoBlock(f"Error: File '{filename}' not found."))
        except json.JSONDecodeError as e:
            self.add_block(InfoBlock(f"Error: Invalid JSON in '{filename}': {e}"))
        except Exception as e:
            self.add_block(InfoBlock(f"Error reading file '{filename}': {e}"))

    def _open_json_from_last_block(self) -> None:
        """Открывает JSON viewer для сфокусированного или последнего блока."""
        block = self._block_for_json_viewer()
        if block is None:
            self.add_block(InfoBlock("[bold]ERROR:[/bold] No blocks found."))
            return
        try:
            json_data = self._extract_json(self._text_from_json_block(block))
            if json_data is not None:
                self.push_screen(JSONViewer(json_data))
                self.sub_title = "JSON viewer opened! Press Escape to close."
                self.set_timer(2, self.clear_subtitle)
            else:
                self.add_block(InfoBlock("No valid JSON found in focused/last block."))
        except Exception as e:
            self.add_block(InfoBlock(f"Error parsing JSON: {e}"))

    def on_input_submitted(self, message: Input.Submitted) -> None:
        """
        Главный диспетчер команд.
        Анализирует первый символ и перенаправляет выполнение.

        v1.1.9+: Команды с операторами (&&, ||, ;, |) обрабатываются как обычные,
        даже если начинаются с !. Это позволяет использовать ссылки в составных командах.
        """
        user_input = message.value.strip()
        input_widget = self.query_one(f"#{self.ID_INPUT}", Input)
        input_widget.value = ""

        if not user_input:
            return

        self.log_to_history(user_input)

        # v1.1.9+: Проверяем, содержит ли команда ссылки на другие команды
        # Ссылки: !tag[tid] или !ID (но не !!)
        has_command_refs = bool(RE_COMMAND_REFS.search(user_input))

        # v1.1.9+: Проверяем, содержит ли команда shell-операторы
        has_shell_operators = bool(RE_SHELL_OPERATORS.search(user_input))

        # Маршрутизация по префиксам
        if user_input.startswith(self.PREFIX_CMD):
            self.handle_colon_command(user_input)
        elif user_input.startswith(self.PREFIX_TAG):
            self.handle_save_command(user_input)
        elif user_input.startswith(self.PREFIX_QUERY):
            self.handle_query_command(user_input)
        elif user_input.startswith(self.PREFIX_DOUBLE_BANG):
            self.handle_double_bang_command(user_input)
        elif user_input.startswith(self.PREFIX_BANG) and not has_shell_operators:
            # Одиночная команда !tag[tid] или !ID (без операторов)
            self.handle_bang_command(user_input)
        elif user_input.startswith(self.PREFIX_PIPE):
            self.handle_pipe_command(user_input)
        elif user_input.startswith(self.PREFIX_VAR):
            self.handle_variable_assignment(user_input)
        elif user_input.startswith(self.PREFIX_TTY) and not user_input.startswith(">>"):
            self.handle_tty_command(user_input)
        elif has_command_refs:
            # Команды с ссылками (!tag[tid] или !ID), даже с операторами
            # Раскрываем ссылки и вставляем в input, НЕ выполняем
            resolved_command = self._resolve_command_references(user_input)
            if resolved_command:
                # Ссылки были раскрыты - вставляем в input
                input_widget = self.query_one(f"#{self.ID_INPUT}", Input)
                input_widget.value = resolved_command
                input_widget.cursor_position = len(resolved_command)
                input_widget.focus()
                return  # Важно: не выполняем команду
            else:
                # Ошибка раскрытия - показываем сообщение пользователю
                # Пытаемся определить, какие именно команды не найдены
                not_found = []
                # Ищем все !tag[tid] ссылки
                for match in RE_TAG_TID_FIND.finditer(user_input):
                    tag, tid = match.group(1), int(match.group(2))
                    result = database.get_command_by_tid(self.db_file, tag, tid)
                    if not result:
                        not_found.append(f"{tag}[{tid}]")
                # Ищем все !ID ссылки (которые не !! в начале)
                for match in RE_GID_FIND.finditer(user_input):
                    gid = int(match.group(1))
                    result = database.get_command_by_global_id(self.db_file, gid)
                    if not result:
                        not_found.append(f"!{gid}")

                if not_found:
                    self.add_block(InfoBlock(f"Error: Commands not found: {', '.join(not_found)}"))
                else:
                    self.add_block(InfoBlock("Error: Unable to resolve command references."))
                return
        else:
            # Обычные команды без ссылок
            self.handle_normal_command(user_input)

    def log_to_history(self, command: str) -> None:
        """
        Записывает команду в файл history.txt, исключая спецкоманды.

        Использует file locking для безопасной записи при одновременной работе
        нескольких копий приложения.
        """
        prefixes = (self.PREFIX_CMD, self.PREFIX_QUERY, self.PREFIX_BANG, self.PREFIX_DOUBLE_BANG, self.PREFIX_TAG, self.PREFIX_PIPE, self.PREFIX_VAR)
        if command.startswith(prefixes):
            return
        last_command = None
        try:
            if os.path.exists(self.FILE_HISTORY):
                try:
                    with open(self.FILE_HISTORY, "r", encoding=self.ENCODING) as f:
                        acquire_file_lock(f, self.FILE_LOCK_TIMEOUT)
                        try:
                            lines = f.readlines()
                            if lines:
                                last_command = lines[-1].strip()
                        finally:
                            release_file_lock(f)
                except FileLockTimeoutError:
                    # Если не получили блокировку для чтения, читаем без неё
                    with open(self.FILE_HISTORY, "r", encoding=self.ENCODING) as f:
                        lines = f.readlines()
                        if lines:
                            last_command = lines[-1].strip()
        except IOError:
            return

        if command != last_command:
            try:
                with open(self.FILE_HISTORY, "a", encoding=self.ENCODING) as f:
                    # Пытаемся получить блокировку для записи
                    try:
                        acquire_file_lock(f, self.FILE_LOCK_TIMEOUT)
                        try:
                            f.write(f"{command}\n")
                        finally:
                            release_file_lock(f)
                    except FileLockTimeoutError:
                        # Если не получили блокировку, пишем без неё
                        # (лучше записать дубликат, чем потерять команду)
                        f.write(f"{command}\n")
            except IOError:
                pass

    def handle_colon_command(self, user_input: str) -> None:
        """Обработка команд управления (:q, :w, :h, :c)."""
        parts = user_input[1:].split()
        if not parts: return
        raw = user_input[1:].strip()
        if raw.startswith("/"):
            self._journal_search(raw[1:])
            return
        command = parts[0]
        if command == self.CMD_QUIT:
            self.exit()
        elif command == self.CMD_WRITE:
            if len(parts) > 1:
                filename = parts[1]
                try:
                    all_blocks = self.query("CommandBlock, InfoBlock")
                    # Удаляем теги форматирования перед записью
                    content_to_write = "\n\n---\n\n".join(
                        self._strip_formatting_tags(block.text_content) for block in all_blocks
                    )
                    with open(filename, "a", encoding=self.ENCODING) as f:
                        f.write(content_to_write)
                    self.add_block(InfoBlock(f"Log content written to '{filename}'"))
                except Exception as e:
                    self.add_block(InfoBlock(f"Error writing to file: {e}"))
            else:
                self.add_block(InfoBlock("Error: Filename required for :w command."))
        elif command == self.CMD_HISTORY:
            try:
                num_lines = int(parts[1]) if len(parts) > 1 else self.history_lines
                with open(self.FILE_HISTORY, "r", encoding=self.ENCODING) as f:
                    lines = f.readlines()
                history = [line.strip() for line in lines[-num_lines:] if line.strip()]
                if not history:
                    self.add_block(InfoBlock(f"{self.FILE_HISTORY} is empty."))
                else:
                    self.add_block(InfoBlock("\n".join(history)))
            except FileNotFoundError:
                self.add_block(InfoBlock(f"{self.FILE_HISTORY} not found."))
            except Exception as e:
                self.add_block(InfoBlock(f"Error reading history: {e}"))
        elif command == self.CMD_CLEAR:
            self.clear_all_blocks()
        elif command == self.CMD_JSON:
            # Открываем JSON viewer
            if len(parts) > 1:
                # Режим с аргументом: открываем JSON из файла
                filename = parts[1]
                self._open_json_file(filename)
            else:
                # Режим без аргументов: открываем JSON из последнего блока
                self._open_json_from_last_block()
        elif command == self.CMD_INGRESS:
            # Kubernetes Ingress Analyzer
            self.handle_ingress_command(user_input[2:].strip())
        elif command == self.CMD_HELP:
            self._show_main_help()
        elif command == self.CMD_CD:
            if len(parts) == 1:
                self.add_block(InfoBlock(f"cwd: {os.getcwd()}"))
            else:
                self._change_cwd(" ".join(parts[1:]))
        elif command == self.CMD_REPLAY:
            self._replay_focused_command()
        elif command == self.CMD_GREP:
            self._journal_search(" ".join(parts[1:]))
        elif command == self.CMD_SEARCH_NEXT:
            self._journal_search(self._search_pattern, direction=1, next_only=True)
        elif command == self.CMD_SEARCH_PREV:
            self._journal_search(self._search_pattern, direction=-1, next_only=True)
        elif command == self.CMD_EXPORT:
            self._export_tag(parts[1:])
        elif command == self.CMD_IMPORT:
            self._import_tag(parts[1:])
        else:
            self.add_block(InfoBlock(f"Unknown command: '{command}'"))

    def _change_cwd(self, path: str) -> None:
        """Меняет cwd процесса приложения (cd / :cd)."""
        if path == "-":
            target = self._old_cwd or os.environ.get("OLDPWD")
            if not target:
                self.add_block(InfoBlock("cd: OLDPWD not set"))
                return
        elif path == "":
            target = os.path.expanduser("~")
        else:
            target = os.path.abspath(os.path.expanduser(path))
        if not os.path.isdir(target):
            self.add_block(InfoBlock(f"cd: {path}: not a directory"))
            return
        old = os.getcwd()
        try:
            os.chdir(target)
        except OSError as e:
            self.add_block(InfoBlock(f"cd: {e}"))
            return
        self._old_cwd = old
        os.environ["OLDPWD"] = old
        os.environ["PWD"] = os.getcwd()
        self.add_block(InfoBlock(f"cwd: {os.getcwd()}"))

    def _command_from_block(self, block: Optional[Static]) -> str:
        if block is None:
            return ""
        cmd = (getattr(block, "source_command", None) or "").strip()
        if cmd:
            return cmd
        header = getattr(block, "header", "") or ""
        if " $ " in header:
            return header.split(" $ ", 1)[1].strip()
        return ""

    def _replay_focused_command(self) -> None:
        """Подставить команду сфокусированного (или последнего) блока во ввод."""
        block = self.focused if isinstance(self.focused, CommandBlock) else None
        if block is None:
            blocks = list(self.query(CommandBlock))
            block = blocks[-1] if blocks else None
        cmd = self._command_from_block(block)
        if not cmd:
            self.add_block(InfoBlock("No command block to replay."))
            return
        self.set_input_draft(cmd)

    def _collect_line_hits(self, lowered: str) -> List[Tuple[Static, int]]:
        """Совпадения (блок, индекс строки) по видимым строкам журнала."""
        hits: List[Tuple[Static, int]] = []
        for block in self._journal_blocks():
            if not isinstance(block, LineNavigable):
                continue
            if isinstance(block, CommandBlock) and getattr(block, "collapsed", False):
                blob = f"{block.header}\n{block.raw_stdout}\n{block.raw_stderr}"
                if lowered not in blob.lower():
                    continue
                block.collapsed = False
                try:
                    block.update(block._format_output())
                except Exception:
                    pass
            for i, line in enumerate(block._nav_lines()):
                plain = self._strip_formatting_tags(line)
                if lowered in plain.lower():
                    hits.append((block, i))
        return hits

    def _journal_search(
        self, pattern: str, direction: int = 1, next_only: bool = False
    ) -> None:
        needle = (pattern or "").strip()
        if not needle:
            if next_only:
                return
            self.add_block(InfoBlock("Usage: :/text  or :g text  (then :n / :N)"))
            return
        lowered = needle.lower()
        if not next_only or lowered != self._search_pattern or not self._search_hits:
            self._search_pattern = lowered
            self._search_hits = self._collect_line_hits(lowered)
            self._search_index = -1
            anchor = self.focused if isinstance(self.focused, LineNavigable) else None
            if anchor is None:
                try:
                    anchor = self._visible_journal_block()
                except Exception:
                    anchor = None
            if isinstance(anchor, LineNavigable):
                for i, (block, _) in enumerate(self._search_hits):
                    if block is anchor:
                        self._search_index = i - 1
                        break
        if not self._search_hits:
            self.add_block(InfoBlock(f"No journal matches for '{needle}'"))
            return
        n = len(self._search_hits)
        step = -1 if direction < 0 else 1
        self._search_index = (self._search_index + step) % n
        chosen, line_idx = self._search_hits[self._search_index]
        self._assign_journal_focus(chosen)
        if isinstance(chosen, LineNavigable):
            chosen.jump_to_line(line_idx, notify=False)
        else:
            try:
                container = self.query_one(f"#{self.ID_RESULTS_CONTAINER}", VerticalScroll)
                container.scroll_to_widget(chosen, animate=False)
            except Exception:
                pass
        self.sub_title = f"search {self._search_index + 1}/{n}"
        self.set_timer(3, self.clear_subtitle)

    def _export_tag(self, args: List[str]) -> None:
        if not args:
            self.add_block(InfoBlock("Usage: :export <tag> [file.json]"))
            return
        tag = args[0]
        path = args[1] if len(args) > 1 else f"{tag}.json"
        try:
            n = database.export_tag_to_file(self.db_file, tag, path)
            self.add_block(InfoBlock(f"Exported {n} command(s) of '{tag}' to {path}"))
        except Exception as e:
            self.add_block(InfoBlock(f"Export error: {e}"))

    def _import_tag(self, args: List[str]) -> None:
        if not args:
            self.add_block(InfoBlock("Usage: :import <file.json>"))
            return
        path = args[0]
        try:
            tag, n = database.import_tag_from_file(self.db_file, path)
            self.add_block(InfoBlock(f"Imported {n} command(s) into tag '{tag}'"))
        except FileNotFoundError:
            self.add_block(InfoBlock(f"Error: file '{path}' not found."))
        except Exception as e:
            self.add_block(InfoBlock(f"Import error: {e}"))

    def handle_ingress_command(self, args: str) -> None:
        """
        Handle Kubernetes Ingress analysis commands.

        Formats:
            :i                  - Show help
            :i list             - List all ingresses
            :i analyze <name>   - Analyze specific ingress
            :i analyze <name> -n <ns>  - Analyze in namespace
            :i check <svc>      - Check service endpoints
        """
        if not args:
            self._show_ingress_help()
            return

        # Lazy initialize analyzer
        if self.ingress_analyzer is None:
            self.ingress_analyzer = IngressAnalyzer(
                timeout=self.COMMAND_TIMEOUT * 3 if self.COMMAND_TIMEOUT else 90
            )

        parts = args.split()
        subcommand = parts[0] if parts else ""

        if subcommand == "list":
            try:
                namespace = self._extract_namespace_from_args(parts)
            except ValueError as e:
                self.add_block(InfoBlock(f"[yellow]{e}[/yellow]"))
                return
            self._list_ingresses(namespace)
        elif subcommand == "ns":
            namespace = parts[1] if len(parts) > 1 else None
            if namespace:
                self._describe_namespace(namespace)
            else:
                self.add_block(InfoBlock("[yellow]Usage: :i ns <namespace>[/yellow]"))
        elif subcommand == "analyze":
            name = parts[1] if len(parts) > 1 else None
            try:
                namespace = self._extract_namespace_from_args(parts)
            except ValueError as e:
                self.add_block(InfoBlock(f"[yellow]{e}[/yellow]"))
                return
            if name:
                self._analyze_ingress(name, namespace)
            else:
                self.add_block(InfoBlock("[yellow]Usage: :i analyze <name> [-n <namespace>][/yellow]"))
        elif subcommand == "check":
            service = parts[1] if len(parts) > 1 else None
            try:
                namespace = self._extract_namespace_from_args(parts)
            except ValueError as e:
                self.add_block(InfoBlock(f"[yellow]{e}[/yellow]"))
                return
            if service:
                self._check_service_endpoints(service, namespace)
            else:
                self.add_block(InfoBlock("[yellow]Usage: :i check <service> [-n <namespace>][/yellow]"))
        else:
            self.add_block(InfoBlock(f"Unknown ingress subcommand: '{subcommand}'"))

    def _extract_namespace_from_args(self, parts: List[str], save_to_var: bool = True) -> Optional[str]:
        """
        Extract -n <namespace> from command arguments and substitute variables.

        Args:
            parts: Command parts
            save_to_var: If True, save namespace to $NS variable

        Returns:
            Namespace string or None

        Raises:
            ValueError: If -n flag is present without a namespace value
        """
        try:
            n_index = parts.index("-n")
            if n_index + 1 < len(parts):
                namespace = parts[n_index + 1]
                if namespace.startswith("-"):
                    raise ValueError("Missing namespace after -n. Usage: -n <namespace>")
                # Substitute variables like $NS
                namespace = self._substitute_variables(namespace)
                # Save to $NS variable for subsequent commands
                if save_to_var and namespace:
                    self.local_env["NS"] = namespace
                    os.environ["NS"] = namespace
                return namespace
            raise ValueError("Missing namespace after -n. Usage: -n <namespace>")
        except ValueError:
            if "-n" in parts:
                raise
        # Fallback to $NS if set and -n not specified
        return self.local_env.get("NS") or os.environ.get("NS")

    def _show_main_help(self) -> None:
        """Show main help for all commands."""
        help_text = """[bold]IDvjPy_term - Commands Help[/bold]

[bold]Application Commands (prefix :)[/bold]
  :?          - Show this help
  :q          - Quit application
  :w <file>   - Write output to file
  :h [N]      - Show shell history as one block (default: 20 lines)
  :c          - Clear all output blocks
  :json       - Open JSON viewer (from last block)
  :json <file>- Open JSON file in viewer
  :i          - Kubernetes Ingress Analyzer (see :i for details)
  :cd [path]  - Show or change the app working directory (also: cd path)
  :r          - Put the focused (or last) block command into the input
  :/text  :g  - Search journal lines; :n / n next, :N / N prev. / on a block starts :/
  :export tag [file] - Write one tag to JSON
  :import file       - Insert commands from that JSON (new tids)

[bold]Kubernetes Commands (prefix :i)[/bold]
  :i list             - List all ingresses
  :i list -n <ns>     - List ingresses in namespace
  :i ns <namespace>   - Describe namespace (JSON viewer)
  :i analyze <name>   - Analyze ingress
  :i check <service>  - Check service endpoints

[bold]Command Prefixes[/bold]
  (none)     - Execute shell command
  > <cmd>    - Suspend TUI and run with a real TTY (htop, vim, ssh, less)
  #<tag>     - Save command to database with tag
  #tag! / #tag!tid - Restore soft-deleted tag / command
  ?          - Query database (? all, ?<tag>, ?? grouped)
  !tag / !tag[tid] - Type ! to list tags [file, kube, log]; Tab picks a tag
               Then commands show as `<id> tag[tid]  full command`; Tab inserts `!tag[tid]`
               Compose pipes/saves: `#file !file[1] | !file[2]` (preview expands refs)
  !N         - Execute command by ID from last query
  |<cmd>     - Pipe focused block output to command
  $VAR=val   - Set environment variable
  aliases    - From ~/.bashrc. If the body has $1 / $2 / $@, args are substituted
               (klogin cluster → tsh kube login cluster). Else the rest of the line
               is appended as in a classic alias.

[bold]Navigation[/bold]
  ↑/↓        - History in input; journal scroll when a block is focused
  Tab        - Focus last journal block (from input), including :h / :?
  Click      - Focus a journal block without jumping to its start
               (needs terminal_mouse: true in settings.yml)
  PgUp/PgDn  - Scroll the journal a page; the visible block becomes active
               (does not jump to the start of the block). From input: enter viewing.
  Esc        - Return to input (see also line-cursor mode)
  Space      - Toggle block collapse
  ← / →      - Collapse / expand focused block
  F3         - Copy full block output to clipboard
  F5         - Open focused (or last command) block in JSON viewer
  F6         - Toggle simple (plain) output
  F2         - Toggle line-cursor mode (see below)
  Shift+Insert / Ctrl+V - Paste into input (does not replace existing text)
               In line-cursor mode Ctrl+V appends the current line instead
  Ctrl+D     - Clear the entire input line
  (JSON) Enter - Insert `jq 'path'` into input; also sets $JSON

[bold]Line-cursor mode[/bold]
  Focus a block (Tab or PgUp), then Enter or F2 to turn the mode on.
  Off by default: ↑/↓ still scroll the journal.
  On: current line is highlighted.
  ↑/↓        - Move by lines inside the block
  Home/End   - First / last line of the block
  Enter      - Copy current line (trailing spaces stripped) and jump to input
               Cursor goes to the end of the input; existing text is not selected
  Shift+Enter / Ctrl+V - Append current line to input, separated by a space
               Stay in the block (can append several lines)
               If Shift+Enter acts like Enter, the terminal does not distinguish
               the keys — use Ctrl+V. While the input is focused, Ctrl+V pastes
  Esc        - Turn mode off, stay on the block; Esc again returns to input
  F2         - Toggle mode on/off
  /          - Start journal search (:/ in the input)
  n / N      - Next / previous search hit (jumps to the matching line)

[bold]Variables[/bold]
  Use $VAR in commands for variable substitution
  $NS is auto-set when using -n in :i commands
  $JSON is set on Enter in JSON viewer (jq path of the selected node)
  Example: jq $JSON test.json
  $VAR also loaded from .bashrc_term and .bashrc_term_<instance>
"""
        self.add_block(InfoBlock(help_text))

    def _show_ingress_help(self) -> None:
        """Show ingress command help."""
        help_text = """[bold]Kubernetes Ingress Analyzer[/bold]

[bold]Usage:[/bold]
  :i list                   - List ingresses (uses $NS if set)
  :i list -n <namespace>    - List in namespace (saves to $NS)
  :i ns <namespace>         - Describe namespace (JSON viewer)
  :i analyze <name>         - Analyze ingress (uses $NS if set)
  :i analyze <name> -n <ns> - Analyze in namespace (saves to $NS)
  :i check <service>        - Check service endpoints (uses $NS)
  :i check <service> -n <ns>- Check in namespace (saves to $NS)

[bold]Namespace persistence:[/bold]
  When -n is specified, namespace is saved to $NS variable.
  Subsequent commands without -n will use $NS automatically.

[bold]Analysis includes:[/bold]
  • Ingress configuration (hosts, paths, TLS)
  • Nginx config from controller (via crossplane)
  • Service and endpoint health
  • Path-to-service mapping

[bold]Prerequisites:[/bold]
  • kubectl configured with cluster access
  • crossplane: pip install crossplane
"""
        self.add_block(InfoBlock(help_text))

    def _list_ingresses(self, namespace: Optional[str] = None) -> None:
        """List ingresses in namespace or all namespaces."""
        ns_display = namespace or "all namespaces"
        def worker():
            try:
                ingresses = self.ingress_analyzer.list_ingresses(namespace)
                self.call_from_thread(self._display_ingress_list, ingresses, namespace)
            except Exception as e:
                self.call_from_thread(
                    self.add_block,
                    InfoBlock(f"[red]Error listing ingresses:[/red] {e}")
                )

        self.add_block(InfoBlock(f"[dim]Listing ingresses in {ns_display}...[/dim]"))
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def _display_ingress_list(self, ingresses, namespace: Optional[str] = None) -> None:
        """Display list of ingresses."""
        ns_display = namespace or "all namespaces"
        if not ingresses:
            self.add_block(InfoBlock(f"[yellow]No ingresses found in '{ns_display}'.[/yellow]"))
            return

        lines = [f"[bold]Found {len(ingresses)} ingresses in '{ns_display}':[/bold]\n"]
        for ing in ingresses:
            hosts = ", ".join(ing.hosts) if ing.hosts else "*"
            paths_count = len(ing.paths)
            # Show namespace only if listing all namespaces
            if namespace:
                lines.append(f"  [cyan]{ing.name}[/cyan] → {hosts} ({paths_count} paths)")
            else:
                lines.append(f"  [cyan]{ing.name}[/cyan] ({ing.namespace}) → {hosts} ({paths_count} paths)")

        lines.append("\n[dim]Use :i analyze <name> -n <namespace> to analyze[/dim]")
        self.add_block(InfoBlock("\n".join(lines)))

    def _analyze_ingress(self, name: str, namespace: Optional[str] = None) -> None:
        """Analyze specific ingress."""
        ns_display = namespace or "default"

        def worker():
            try:
                analysis = self.ingress_analyzer.analyze_ingress(name, namespace)
                self.call_from_thread(self._display_ingress_analysis, analysis)
            except Exception as e:
                self.call_from_thread(
                    self.add_block,
                    InfoBlock(f"[red]Analysis failed:[/red] {e}")
                )

        self.add_block(InfoBlock(f"[dim]Analyzing ingress '{name}' in '{ns_display}'...[/dim]"))
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def _display_ingress_analysis(self, analysis: Dict) -> None:
        """Display ingress analysis results."""
        from ingress_analyzer import format_analysis_summary

        # Show summary as InfoBlock
        summary = format_analysis_summary(analysis)
        self.add_block(InfoBlock(summary))

        # Open JSON viewer for detailed view
        self.push_screen(JSONViewer(analysis))

    def _check_service_endpoints(self, service: str, namespace: Optional[str] = None) -> None:
        """Check service endpoints."""
        ns_display = namespace or "default"

        def worker():
            try:
                svc_info = self.ingress_analyzer.check_service_endpoints(service, namespace)
                self.call_from_thread(self._display_service_info, svc_info)
            except Exception as e:
                self.call_from_thread(
                    self.add_block,
                    InfoBlock(f"[red]Error checking service:[/red] {e}")
                )

        self.add_block(InfoBlock(f"[dim]Checking service '{service}' in '{ns_display}'...[/dim]"))
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def _display_service_info(self, svc_info) -> None:
        """Display service endpoint information."""
        lines = [
            f"[bold]Service: {svc_info.name}[/bold] (namespace: {svc_info.namespace})",
            f"Type: {svc_info.type}",
            f"Selector: {svc_info.selector or 'none'}",
            "",
            f"[bold]Endpoints:[/bold] {svc_info.healthy_endpoints}/{svc_info.total_endpoints} healthy",
        ]

        if svc_info.endpoints:
            for ep in svc_info.endpoints:
                status = "✓" if ep.ready else "✗"
                pod = f" ({ep.pod_name})" if ep.pod_name else ""
                lines.append(f"  {status} {ep.ip}:{ep.port}{pod}")
        else:
            lines.append("  [yellow]No endpoints found[/yellow]")

        self.add_block(InfoBlock("\n".join(lines)))

    def _describe_namespace(self, namespace: str) -> None:
        """Describe namespace and open in JSON viewer."""
        # Substitute variables in namespace
        namespace = self._substitute_variables(namespace)

        def worker():
            try:
                result = subprocess.run(
                    ["kubectl", "get", "namespace", namespace, "-o", "json"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0:
                    data = json.loads(result.stdout)
                    self.call_from_thread(self._show_namespace_json, data)
                else:
                    self.call_from_thread(
                        self.add_block,
                        InfoBlock(f"[red]Error:[/red] {result.stderr}")
                    )
            except Exception as e:
                self.call_from_thread(
                    self.add_block,
                    InfoBlock(f"[red]Error describing namespace:[/red] {e}")
                )

        self.add_block(InfoBlock(f"[dim]Getting namespace '{namespace}'...[/dim]"))
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def _show_namespace_json(self, data: Dict) -> None:
        """Show namespace data in JSON viewer."""
        name = data.get("metadata", {}).get("name", "unknown")
        status = data.get("status", {}).get("phase", "unknown")
        self.add_block(InfoBlock(f"[green]Namespace:[/green] {name} ({status})"))
        self.push_screen(JSONViewer(data))

    def handle_variable_assignment(self, user_input: str) -> None:
        """
        Обработка создания/обновления переменных.
        Синтаксис: $VAR_NAME=VALUE.
        Записывает в .bashrc_term и обновляет self.local_env.

        Использует file locking для безопасной записи при одновременной работе
        нескольких копий приложения.
        """
        assignment = user_input[1:].strip()
        parts = assignment.split('=', 1)

        if len(parts) == 2:
            var_name, var_value = parts
            var_name = var_name.strip()
            var_value = var_value.strip()

            # Простая валидация имени переменной
            if not RE_VAR_NAME.match(var_name):
                self.add_block(InfoBlock(f"Error: Invalid variable name '{var_name}'."))
                return

            # Обновляем в памяти
            self.local_env[var_name] = var_value
            os.environ[var_name] = var_value

            # Перезаписываем файл с блокировкой
            try:
                lines = []
                updated = False

                # Читаем файл с блокировкой
                if os.path.exists(self.FILE_BASHRC):
                    try:
                        with open(self.FILE_BASHRC, "r", encoding=self.ENCODING) as f_read:
                            acquire_file_lock(f_read, self.FILE_LOCK_TIMEOUT)
                            try:
                                lines = f_read.readlines()
                            finally:
                                release_file_lock(f_read)
                    except FileLockTimeoutError:
                        # Если не получили блокировку для чтения, читаем без неё
                        with open(self.FILE_BASHRC, "r", encoding=self.ENCODING) as f:
                            lines = f.readlines()

                # Пишем файл с блокировкой
                with open(self.FILE_BASHRC, "w", encoding=self.ENCODING) as f_write:
                    acquire_file_lock(f_write, self.FILE_LOCK_TIMEOUT)
                    try:
                        for line in lines:
                            # Если переменная уже есть в файле, обновляем её строку
                            if line.startswith(f"export {var_name}="):
                                f_write.write(f'export {var_name}="{var_value}"\n')
                                updated = True
                            else:
                                f_write.write(line)
                        # Если переменной не было, добавляем в конец
                        if not updated:
                            f_write.write(f'export {var_name}="{var_value}"\n')
                    finally:
                        release_file_lock(f_write)

                self.add_block(InfoBlock(f"Variable ${var_name} set to '{var_value}'"))
            except FileLockTimeoutError as e:
                self.add_block(InfoBlock(f"Error: File is locked by another instance. {e}"))
            except Exception as e:
                self.add_block(InfoBlock(f"Error setting variable: {e}"))
        else:
            self.add_block(InfoBlock("Invalid syntax. Use: $VAR_NAME=VALUE"))

    def _resolve_command_references(self, command: str) -> str:
        """
        Раскрывает ссылки на команды в строке (!tag[tid], !ID, !! ...).

        v1.1.9+: Использует CommandParser для надежного разбора команд.

        Заменяет все вхождения:
        - !tag[tid] на текст команды из БД
        - !ID на текст команды из БД
        - !! ... на результат сборки команд

        Args:
            command: Строка команды с возможными ссылками

        Returns:
            Строка команды с раскрытыми ссылками или None при ошибке
        """
        # Парсим команду с помощью CommandParser
        tokens = self.command_parser.parse(command)

        if not tokens:
            return None

        # Определяем функцию для получения команд из БД
        def get_command(**kwargs) -> Optional[str]:
            """Получает команду из БД по tag/tid или global_id."""
            if 'tag' in kwargs and 'tid' in kwargs:
                db_result = database.get_command_by_tid(
                    self.db_file, kwargs['tag'], kwargs['tid']
                )
                return db_result['command'] if db_result else None
            elif 'global_id' in kwargs:
                cmd_id = kwargs['global_id']
                # Сначала проверяем в last_query_results (от команды ?)
                if cmd_id in self.last_query_results:
                    return self.last_query_results[cmd_id]
                # Если нет, ищем в БД по глобальному ID
                db_result = database.get_command_by_global_id(self.db_file, cmd_id)
                if db_result:
                    return db_result['command']
                return None
            return None

        # Собираем команду, раскрывая ссылки
        assembled = self.command_parser.assemble_command(tokens, get_command)

        return assembled

    def _resolve_command_with_steps(self, command: str) -> list:
        """
        Раскрывает ссылки пошагово, возвращая все этапы преобразования.

        Показывает полную цепочку раскрытия ссылок:
        - Шаг 1: исходная команда
        - Шаг 2: после первого раскрытия ссылок
        - Шаг N: финальная полностью раскрытая команда

        Args:
            command: Исходная команда с возможными ссылками

        Returns:
            Список всех этапов раскрытия или пустой список при ошибке
        """
        steps = [command]
        max_iterations = 100  # Защита от бесконечных циклов
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            # Раскрываем ссылки в текущем шаге
            resolved = self._resolve_command_references(steps[-1])

            if resolved is None:
                # Ошибка при раскрытии
                return []

            if resolved == steps[-1]:
                # Ссылок больше нет - завершаем
                break

            steps.append(resolved)

        return steps

    def handle_save_command(self, user_input: str) -> None:
        """
        Обработка сохранения, удаления, редактирования команд и комментариев.

        Поддерживаемые форматы:
        - #tag <cmd>           - сохранить команду с тегом
        - #tag-                - удалить все команды с тегом
        - #tag-tid             - удалить конкретную команду по tid
        - #tag+ID              - редактировать команду (v1.1.9+)
        - #tag+                - редактировать последнюю команду тега (v1.1.9+)
        - #tag=comment         - установить комментарий к тегу
        - #tag=ID=comment      - комментарий к команде (ID = tid или глобальный id)

        Логика парсинга:
        1. Проверка на "=" с двумя знаками -> комментарий к команде
        2. Проверка на "=" с одним знаком -> комментарий к тегу
        3. Проверка на "+" -> редактирование команды
        4. Проверка на "-" -> удаление команд
        5. Иначе -> сохранение новой команды
        """
        content = user_input[1:].strip()

        # Формат: #tag=ID=comment  (ID = tid или глобальный <id> из ??)
        m = re.match(r"^([a-zA-Z_0-9]+)=(\d+)=(.*)$", content)
        if m:
            tag, id_str, comment = m.groups()
            try:
                cmd_id = int(id_str)
                updated = database.set_command_comment(
                    self.db_file, tag, cmd_id, comment.strip()
                )
                if updated:
                    self.add_block(InfoBlock(
                        f"Command {updated['tag']}[{updated['tid']}] "
                        f"comment set to: '{comment.strip()}'"
                    ))
                else:
                    self.add_block(InfoBlock(
                        f"Error: Command {tag}[{cmd_id}] not found "
                        f"(use tid from {tag}[tid] or global id from <id>)."
                    ))
            except Exception as e:
                self.add_block(InfoBlock(f"Database error: {e}"))
            return

        # Формат: #tag=comment
        m = re.match(r"^([a-zA-Z_0-9]+)=(.*)$", content)
        if m:
            tag, comment = m.groups()
            try:
                database.set_tag_comment(self.db_file, tag, comment.strip())
                self.add_block(InfoBlock(f"Tag '{tag}' comment set to: '{comment.strip()}'"))
            except Exception as e:
                self.add_block(InfoBlock(f"Database error: {e}"))
            return

        # Формат: #tag+ID [new_command] или #tag+
        m = re.match(r"^([a-zA-Z_0-9]+)\+(\d+)?(?:\s+(.*))?$", content)
        if m:
            tag, tid_str, new_command = m.groups()
            try:
                if tid_str:
                    tid = int(tid_str)
                    if new_command:
                        result = database.get_command_by_tid(self.db_file, tag, tid)
                        if result:
                            database.update_command_by_tid(self.db_file, tag, tid, new_command.strip())
                            self.add_block(InfoBlock(f"Updated {tag}[{tid}] to: '{new_command.strip()}'"))
                        else:
                            self.add_block(InfoBlock(f"Error: Command {tag}[{tid}] not found."))
                    else:
                        result = database.get_command_by_tid(self.db_file, tag, tid)
                        if result:
                            command_text = result['command']
                            input_widget = self.query_one(f"#{self.ID_INPUT}", Input)
                            input_widget.value = f"#{tag} {command_text}"
                            input_widget.cursor_position = len(f"#{tag} ") + len(command_text)
                            input_widget.focus()
                            self.add_block(InfoBlock(f"Editing {tag}[{tid}]. Edit and press Enter to save."))
                        else:
                            self.add_block(InfoBlock(f"Error: Command {tag}[{tid}] not found."))
                else:
                    all_commands = database.get_commands_by_tag(self.db_file, tag)
                    active_commands = [cmd for cmd in all_commands if not cmd.get('deleted', False)]
                    if active_commands:
                        last_cmd = max(active_commands, key=lambda x: x['tid'])
                        tid = last_cmd['tid']
                        command_text = last_cmd['command']
                        input_widget = self.query_one(f"#{self.ID_INPUT}", Input)
                        input_widget.value = f"#{tag} {command_text}"
                        input_widget.cursor_position = len(f"#{tag} ") + len(command_text)
                        input_widget.focus()
                        self.add_block(InfoBlock(f"Editing {tag}[{tid}] (last command). Edit and press Enter to save."))
                    else:
                        self.add_block(InfoBlock(f"Error: No active commands found for tag '{tag}'"))
            except Exception as e:
                self.add_block(InfoBlock(f"Database error: {e}"))
            return

        # Формат: #tag!  или  #tag!tid  — восстановить soft-delete
        m = re.match(r"^([a-zA-Z_0-9]+)!(?:(\d+))?$", content)
        if m:
            tag, tid_str = m.groups()
            try:
                if tid_str:
                    tid = int(tid_str)
                    if database.restore_command_by_tid(self.db_file, tag, tid):
                        self.add_block(InfoBlock(f"Restored {tag}[{tid}]."))
                    else:
                        self.add_block(InfoBlock(f"Error: deleted command {tag}[{tid}] not found."))
                else:
                    n = database.restore_commands_by_tag(self.db_file, tag)
                    if n:
                        self.add_block(InfoBlock(f"Restored {n} command(s) with tag '{tag}'."))
                    else:
                        self.add_block(InfoBlock(f"No deleted commands for tag '{tag}'."))
            except Exception as e:
                self.add_block(InfoBlock(f"Database error: {e}"))
            return

        # Формат удаления только строго #tag- или #tag-<tid>
        m = re.match(r"^([a-zA-Z_0-9]+)-(\d*)$", content)
        if m:
            tag, identifier = m.groups()
            try:
                if not identifier:
                    database.delete_commands_by_tag(self.db_file, tag)
                    self.add_block(InfoBlock(f"All commands with tag '{tag}' marked as deleted."))
                else:
                    cmd_id = int(identifier)
                    database.delete_command_by_tid(self.db_file, tag, cmd_id)
                    self.add_block(InfoBlock(f"Command {tag}[{cmd_id}] marked as deleted."))
            except Exception as e:
                self.add_block(InfoBlock(f"Database error: {e}"))
            return

        # Если это не удаление и не комментарий, значит сохранение
        parts = content.split(maxsplit=1)
        if len(parts) == 2:
            tag, command_to_save = parts

            # v1.1.9+: Сохраняем команду как есть, БЕЗ раскрытия ссылок
            # Ссылки !tag[tid] и !ID будут раскрываться только при выполнении через !
            try:
                tid = database.add_command(self.db_file, command_to_save, tag)
                self.add_block(InfoBlock(f"Saved: '{command_to_save}' as {tag}[{tid}]"))
            except Exception as e:
                self.add_block(InfoBlock(f"Database error: {e}"))
        else:
            self.add_block(InfoBlock("Invalid syntax. Use: #tag <command> or #tag=<comment>"))

    def _format_tagged_command_line(
        self,
        gid: int,
        tag: str,
        tid: int,
        command: str,
        cmd_comment: str = "",
    ) -> str:
        """Строка для ?? / ?tag. escape, иначе Rich съедает `[tid]` и комментарий."""
        ref = escape(f"{tag}[{tid}]")
        cmd = escape(command or "")
        line = f"  [dim]<{gid}>[/dim] [bold]{ref}[/bold]  {cmd}"
        comment = (cmd_comment or "").strip()
        if comment:
            line += f"  [dim]# {escape(comment)}[/dim]"
        return line

    def handle_query_command(self, user_input: str) -> None:
        """
        Поиск команд в БД.
        ? - список тегов с комментариями.
        ?? - все команды.
        ?tag - команды по тегу.
        ?tag[tid] - показать полную раскрытую команду (v1.1.11+)
        """
        tag_part = user_input[1:].strip()
        self.last_query_results = {}

        # v1.1.11+: Проверка на формат ?tag[tid] для показа раскрытой команды
        tag_tid_match = RE_TAG_TID.match(tag_part)
        if tag_tid_match:
            tag = tag_tid_match.group(1)
            tid = int(tag_tid_match.group(2))

            try:
                result = database.get_command_by_tid(self.db_file, tag, tid)
                if result:
                    original_command = result['command']
                    # Раскрываем ссылки пошагово с показом всех этапов
                    resolution_steps = self._resolve_command_with_steps(original_command)

                    if not resolution_steps:
                        # Ошибка при раскрытии ссылок
                        self.add_block(InfoBlock(f"[bold]Original command:[/bold]\n{original_command}\n\n[dim]Error: Could not resolve command references.[/dim]"))
                    elif len(resolution_steps) == 1:
                        # Ссылок не было
                        self.add_block(InfoBlock(f"[bold]Command:[/bold]\n{original_command}\n\n[dim]No references to resolve.[/dim]"))
                    else:
                        # Ссылки были раскрыты - показываем все шаги
                        content_lines = []
                        for i, step_command in enumerate(resolution_steps, 1):
                            if i == 1:
                                content_lines.append(f"[bold]Step {i} (Original):[/bold]\n{step_command}")
                            elif i == len(resolution_steps):
                                content_lines.append(f"\n[bold]Step {i} (Final):[/bold]\n{step_command}")
                            else:
                                content_lines.append(f"\n[bold]Step {i}:[/bold]\n{step_command}")
                        self.add_block(InfoBlock("\n".join(content_lines)))
                else:
                    self.add_block(InfoBlock(f"Error: Command {tag}[{tid}] not found."))
            except Exception as e:
                self.add_block(InfoBlock(f"Database error: {e}"))
            return

        try:
            if not tag_part:
                tags = database.get_all_tags(self.db_file)
                tags_with_comments = database.get_all_tags_with_comments(self.db_file)
                comments_dict = dict(tags_with_comments)

                content = "Available tags:\n"
                if tags:
                    for tag in sorted(tags):
                        comment = comments_dict.get(tag, "")
                        if comment:
                            content += f"  - {tag}: {comment}\n"
                        else:
                            content += f"  - {tag}\n"
                else:
                    content += "  (None found)"

                content += "\n\nType `? <tag>` to see commands or `??` to see all."
                content += "\nUse #tag=<comment> for tag comments, #tag=ID=<comment> for command comments."
                self.add_block(InfoBlock(content))
            elif tag_part == '?':
                # Вывод всех команд с группировкой по тегам
                all_commands = database.get_all_commands_with_ids(self.db_file)
                content = "All commands by tag:\n"
                commands_by_tag = {}
                for row in all_commands:
                    tag = row['tag']
                    global_id = row['id']
                    tid = row['tid']
                    cmd_text = row['command']
                    cmd_comment = row['comment'] if 'comment' in row.keys() else ''
                    if tag not in commands_by_tag:
                        commands_by_tag[tag] = []
                    commands_by_tag[tag].append((global_id, tid, cmd_text, cmd_comment))
                    # Сохраняем для быстрого доступа по глобальному ID
                    self.last_query_results[global_id] = cmd_text

                if not commands_by_tag:
                    content += "  (None found)"
                else:
                    # Получаем комментарии для всех тегов
                    tags_with_comments = database.get_all_tags_with_comments(self.db_file)
                    comments_dict = dict(tags_with_comments)

                    for tag, items in sorted(commands_by_tag.items()):
                        comment = comments_dict.get(tag, "")
                        if comment:
                            content += f"\n- {tag} ({comment}):\n"
                        else:
                            content += f"\n- {tag}:\n"
                        for gid, tid, cmd, cmd_comment in items:
                            content += self._format_tagged_command_line(
                                gid, tag, tid, cmd, cmd_comment
                            ) + "\n"
                content += "\nUse `!tag[tid]` or `!ID` to execute a command."
                content += "\nUse #tag=<comment> for tag comments, #tag=ID=<comment> for command comments."
                self.add_block(InfoBlock(content))
            else:
                # Поиск по тегу
                commands = database.get_commands_by_tag(self.db_file, tag_part)
                comment = database.get_tag_comment(self.db_file, tag_part)
                content = f"Commands for tag '{tag_part}'"
                if comment:
                    content += f" ({comment})"
                content += ":\n"
                if not commands:
                    content += "  (None found)"
                else:
                    for row in commands:
                        self.last_query_results[row['id']] = row['command']
                    lines = []
                    for row in commands:
                        cmd_comment = ""
                        if "comment" in row.keys() and row["comment"]:
                            cmd_comment = row["comment"]
                        lines.append(
                            self._format_tagged_command_line(
                                row["id"], tag_part, row["tid"], row["command"], cmd_comment
                            )
                        )
                    content += "\n".join(lines)
                    content += "\n\nUse `!{}[<tid>]` or `!ID` to execute.".format(tag_part)
                    content += "\nUse #tag=<comment> for tag comments, #tag=ID=<comment> for command comments."
                self.add_block(InfoBlock(content))
        except Exception as e:
            self.add_block(InfoBlock(f"Database error: {e}"))

    def handle_bang_command(self, user_input: str) -> None:
        """
        Выполнение команды по ID.
        Поддерживает два формата:
        - !tag[tid] - по имени тега и локальному ID (новый)
        - !ID - по глобальному ID (старый, для обратной совместимости)

        v1.1.9+: Если команда содержит ссылки, они автоматически раскрываются
        перед вставкой в поле ввода для удобного выполнения.

        v1.1.10+: Поддержка дополнительного текста после ссылки:
        - !tag[tid] $MYVAR - загрузит команду и добавит переменную
        - !tag[tid] --option=value - загрузит команду и добавит опцию
        """
        command_part = user_input[1:].strip()

        command_text = None
        additional_text = ""

        # Проверяем новый формат: !tag[tid] (с опциональным дополнительным текстом)
        tag_match = RE_TAG_MATCH.match(command_part)
        if tag_match:
            try:
                tag = tag_match.group(1)
                tid = int(tag_match.group(2))

                # Получаем команду из БД
                result = database.get_command_by_tid(self.db_file, tag, tid)
                if result:
                    command_text = result['command']
                else:
                    self.add_block(InfoBlock(f"Error: Command {tag}[{tid}] not found."))
                    return

                # Извлекаем дополнительный текст после ]
                match_end = tag_match.end()
                if match_end < len(command_part):
                    additional_text = command_part[match_end:].strip()

            except (ValueError, IndexError):
                self.add_block(InfoBlock("Invalid syntax. Use: !tag[tid] or !ID"))
                return
        # Проверяем старый формат: !ID (цифра)
        else:
            # Извлекаем числовой ID из начала строки
            match = RE_DIGIT_MATCH.match(command_part)
            if match:
                cmd_id = int(match.group(1))
                result = database.get_command_by_global_id(self.db_file, cmd_id)
                if result:
                    command_text = result['command']
                else:
                    self.add_block(InfoBlock(f"Error: Global ID {cmd_id} not found."))
                    return

                # Извлекаем дополнительный текст после ID
                if len(match.group(1)) < len(command_part):
                    additional_text = command_part[len(match.group(1)):].strip()
            else:
                self.add_block(InfoBlock("Invalid syntax. Use: !tag[tid] or !ID"))
                return

        # Собираем полную команду с дополнительным текстом
        if additional_text:
            # Добавляем пробел между командой и дополнительным текстом
            command_text = f"{command_text} {additional_text}"

        # Вставляем команду в input БЕЗ раскрытия ссылок
        # Раскрытие произойдёт автоматически в handle_normal_command при выполнении
        input_widget = self.query_one(f"#{self.ID_INPUT}", Input)
        input_widget.value = command_text
        input_widget.cursor_position = len(command_text)

    def handle_double_bang_command(self, user_input: str) -> None:
        """
        Сборка нескольких команд по ID с разделителями (!! id1;id2|id3&&id4).
        Поддерживает форматы ID:
        - Числовой: 1, 2, 3 (глобальный ID)
        - Теговый: tag[1], deploy[2] (тег + локальный ID)
        Поддерживает разделители: пробел, ; | && & > <
        Вставляет собранную команду в строку ввода для выполнения.
        """
        command_part = user_input[2:].strip()  # Убираем "!!"

        if not command_part:
            self.add_block(InfoBlock("Invalid syntax. Use: !! <id1>;<tag2>[<tid>]..."))
            return

        # Допустимые разделители (в порядке убывания длины для корректного парсинга)
        separators = ['&&', '||', ';', '|', '>', '<', '&']

        # Парсим строку на токены
        tokens = []
        i = 0
        current_token = ""

        while i < len(command_part):
            # Пропускаем пробелы (разделитель команд по умолчанию)
            if command_part[i] == ' ':
                if current_token:
                    tokens.append(current_token)
                    current_token = ""
                i += 1
                continue

            # Проверяем разделители
            matched_sep = None
            for sep in separators:
                if command_part[i:i+len(sep)] == sep:
                    matched_sep = sep
                    i += len(sep)
                    break

            if matched_sep:
                # Сохраняем накопленный токен
                if current_token:
                    tokens.append(current_token)
                    current_token = ""
                # Добавляем разделитель
                tokens.append(matched_sep)
            else:
                current_token += command_part[i]
                i += 1

        # Добавляем последний токен
        if current_token:
            tokens.append(current_token)

        # Проверяем, что все ID валидны и получаем команды
        cmd_parts = []
        for token in tokens:
            if token in separators:
                cmd_parts.append(token)
            else:
                # Поддержка двух форматов: числовой (!ID) и теговый (!tag[tid])
                command_text = None

                # Формат 1: Числовой ID (например: 1, 2, 3)
                if token.isdigit():
                    cmd_id = int(token)
                    if cmd_id not in self.last_query_results:
                        self.add_block(InfoBlock(f"Error: ID {cmd_id} not found in last query results."))
                        return
                    command_text = self.last_query_results[cmd_id]

                # Формат 2: Теговый ID (например: deploy[1], test[2])
                elif '[' in token and token.endswith(']'):
                    try:
                        tag, tid_part = token.split('[')
                        tid = int(tid_part[:-1])  # Убираем ']'
                        result = database.get_command_by_tid(self.db_file, tag, tid)
                        if result:
                            command_text = result['command']
                        else:
                            self.add_block(InfoBlock(f"Error: Command {tag}[{tid}] not found."))
                            return
                    except (ValueError, IndexError):
                        self.add_block(InfoBlock(f"Error: Invalid ID format '{token}'. Use: !! <id1>;<tag2>[<tid>]..."))
                        return

                # Неверный формат
                else:
                    self.add_block(InfoBlock(f"Error: Invalid ID '{token}'. Use: !! <id1>;<tag2>[<tid>]..."))
                    return

                cmd_parts.append(command_text)

        # Собираем итоговую команду с пробелами между частями
        final_command = " ".join(cmd_parts)

        # Вставляем в input как делает !
        input_widget = self.query_one(f"#{self.ID_INPUT}", Input)
        input_widget.value = final_command
        input_widget.cursor_position = len(input_widget.value)

    def handle_pipe_command(self, user_input: str) -> None:
        """
        Обработка пайпинга.
        Использует активный (выделенный) блок или последний блок.
        """
        pipe_command = user_input[1:].strip()
        if not pipe_command:
            self.add_block(InfoBlock("Error: Pipe command cannot be empty."))
            return

        source_block = self.active_pipe_source if self.active_pipe_source else self.query(CommandBlock).last()

        if source_block is None or not source_block.raw_stdout:
            self.add_block(InfoBlock("Error: No command output available to pipe from."))
            return

        input_for_pipe = source_block.raw_stdout
        self.handle_normal_command(pipe_command, stdin_data=input_for_pipe)

    def handle_tty_command(self, user_input: str) -> None:
        """
        `> cmd` — приостановить TUI и выполнить команду с настоящим TTY.
        Нужно для htop, vim, less, ssh и других интерактивных программ.
        `>>` не перехватывается (это редирект shell).
        """
        command = user_input[1:].strip()
        if not command:
            self.add_block(InfoBlock("Usage: > <command>  (real TTY, e.g. > htop)"))
            return

        if RE_COMMAND_REFS.search(command):
            resolved = self._resolve_command_references(command)
            if not resolved:
                self.add_block(InfoBlock("Error: Unable to resolve command references."))
                return
            command = resolved

        if user_input not in self.session_history:
            self.session_history.append(user_input)
        self.session_history_pos = len(self.session_history)

        final_command = self._expand_aliases(self._substitute_variables(command))
        try:
            return_code = self._run_in_tty(final_command)
        except SuspendNotSupported:
            self.add_block(InfoBlock(
                "Error: this terminal cannot suspend the TUI for interactive commands."
            ))
            return
        except Exception as e:
            self.add_block(InfoBlock(f"TTY error: {e}"))
            return
        self.add_block(InfoBlock(
            f"TTY: {escape(final_command)}\nExit code: {return_code}"
        ))
        self._request_shift_enter_encoding()

    def _run_in_tty(self, command: str) -> int:
        """Отдаёт терминал дочернему процессу (без таймаута и захвата stdout)."""
        with self.suspend():
            completed = subprocess.run(
                command,
                shell=True,
                executable="/bin/bash",
            )
            return completed.returncode

    def handle_normal_command(self, command: str, stdin_data: Optional[str] = None) -> None:
        """
        Обертка для выполнения обычной команды с обновлением истории.

        v1.1.9+: Раскрытие ссылок !tag[tid] и !ID происходит в on_input_submitted,
        поэтому здесь мы просто выполняем уже раскрытую команду.
        """
        if command not in self.session_history:
            self.session_history.append(command)
        self.session_history_pos = len(self.session_history)
        expanded = self._expand_aliases(self._substitute_variables(command))
        cd_path = parse_standalone_cd(expanded)
        if cd_path is not None:
            self._change_cwd(cd_path)
            return
        self.run_command(command, stdin_data)

    def _scroll_results(self, delta: int) -> None:
        """Прокрутка журнала команд (когда фокус не на поле ввода)."""
        container = self.query_one(f"#{self.ID_RESULTS_CONTAINER}", VerticalScroll)
        container.scroll_relative(y=delta, animate=False, immediate=True)

    def action_history_prev(self) -> None:
        """Up: история сессии в input; в журнале — скролл или строки (если line cursor)."""
        input_widget = self.query_one(f"#{self.ID_INPUT}", Input)
        if not input_widget.has_focus:
            if getattr(self, "_completion_list", None) is not None:
                self._completion_list.hide()
            focused = self.focused
            if (
                isinstance(focused, LineNavigable)
                and getattr(focused, "line_nav_active", False)
                and focused.move_line(-1)
            ):
                return
            self._scroll_journal_and_focus(-1)
            return
        if not self.session_history: return
        if self.session_history_pos > 0:
            self.session_history_pos -= 1
            input_widget.value = self.session_history[self.session_history_pos]
            input_widget.cursor_position = len(input_widget.value)

    def action_history_next(self) -> None:
        """Down: история сессии в input; в журнале — скролл или строки (если line cursor)."""
        input_widget = self.query_one(f"#{self.ID_INPUT}", Input)
        if not input_widget.has_focus:
            if getattr(self, "_completion_list", None) is not None:
                self._completion_list.hide()
            focused = self.focused
            if (
                isinstance(focused, LineNavigable)
                and getattr(focused, "line_nav_active", False)
                and focused.move_line(1)
            ):
                return
            self._scroll_journal_and_focus(1)
            return
        if not self.session_history: return
        if self.session_history_pos < len(self.session_history) - 1:
            self.session_history_pos += 1
            input_widget.value = self.session_history[self.session_history_pos]
            input_widget.cursor_position = len(input_widget.value)
        else:
            self.session_history_pos = len(self.session_history)
            input_widget.value = ""
            input_widget.cursor_position = 0

    def _substitute_variables(self, command: str) -> str:
        return substitute_variables(command, self.local_env)

    def _expand_aliases(self, command: str) -> str:
        return expand_aliases(command, self.aliases)

    def _execute_in_thread(self, block: CommandBlock, command: str, stdin_data: Optional[str]) -> None:
        """
        Выполняет команду в отдельном потоке.
        Таймаут отключается при command_timeout: 0 в settings.yml.
        """
        raw_stdout, raw_stderr, return_code = "", "", 0
        if command:
            try:
                kwargs = dict(
                    shell=True,
                    executable="/bin/bash",
                    capture_output=True,
                    text=True,
                    encoding=self.ENCODING,
                    errors="replace",
                    input=stdin_data,
                )
                if self.COMMAND_TIMEOUT and self.COMMAND_TIMEOUT > 0:
                    kwargs["timeout"] = self.COMMAND_TIMEOUT
                process = subprocess.run(command, **kwargs)
                raw_stdout = process.stdout.strip()
                raw_stderr = process.stderr.strip()
                return_code = process.returncode
            except subprocess.TimeoutExpired:
                raw_stderr = self.MSG_TIMEOUT.format(sec=self.COMMAND_TIMEOUT)
                return_code = 124
            except Exception as e:
                raw_stderr = str(e)
                return_code = -1
        self.call_from_thread(block.update_content, raw_stdout, raw_stderr, return_code)

    def run_command(self, command: str, stdin_data: Optional[str] = None) -> None:
        """
        Инициатор выполнения команды.
        Подставляет переменные и запускает поток.
        """
        timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
        cwd = os.getcwd()
        
        # Шаг 1: Подставляем переменные в строку команды
        final_command = self._substitute_variables(command)
        # Шаг 2: Раскрываем алиасы
        final_command = self._expand_aliases(final_command)
        
        header = f"{timestamp} ({cwd}) $ {final_command}"

        block = CommandBlock(
            header=header,
            raw_stdout="[Executing...]",
            raw_stderr="",
            return_code=0,
            source_command=command,
        )
        initial_text = self._pending_block_display(block)
        block.text_content = initial_text
        block.update(initial_text)
        
        self.add_block(block)
        
        # Запускаем в отдельном потоке, чтобы UI не завис
        thread = threading.Thread(
            target=self._execute_in_thread, 
            args=(block, final_command, stdin_data),
            daemon=True
        )
        thread.start()

    def _settings_terminal_mouse(self) -> bool:
        """
        Включает протокол xterm-mouse в драйвере Textual.

        True — колесо и клики обрабатывает приложение (как раньше).
        False — терминал снова может выделять текст мышью; прокрутка журнала: PgUp/PgDn.
        Если ключа нет в settings.yml, остаётся True (обратная совместимость).
        """
        try:
            with open(self.FILE_SETTINGS, "r", encoding=self.ENCODING) as f:
                settings = yaml.safe_load(f)
            if isinstance(settings, dict) and "terminal_mouse" in settings:
                return bool(settings["terminal_mouse"])
        except Exception:
            pass
        return True

    def run(self, **kwargs: Any) -> Any:
        if "mouse" not in kwargs:
            kwargs["mouse"] = self._settings_terminal_mouse()
        return super().run(**kwargs)

if __name__ == "__main__":
    args = parse_arguments()
    INSTANCE_NAME = args.instance_name
    CommandRunner.FILE_BASHRC = f".bashrc_term_{INSTANCE_NAME}"
    app = CommandRunner()
    app.run()
