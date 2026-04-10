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

# Parse arguments first
args = parse_arguments()
INSTANCE_NAME = args.instance_name

# Check dependencies before importing
try:
    import yaml
    import datetime
    import os
    import json
    import pyperclip
    import database_v2 as database
    import threading
    import re
    import time
    import portalocker
    from typing import List, Optional, Dict
    from command_parser_v2 import CommandParser
    from textual import events
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.widgets import Header, Footer, Input, Static
    from rich.text import Text
    from textual.containers import VerticalScroll, Vertical
    from json_viewer import JSONViewer
    from ingress_analyzer import IngressAnalyzer
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
RE_VAR_SUBST = re.compile(r'\$([a-zA-Z_][a-zA-Z0-9_]*)\b')
RE_COMMAND_REFS = re.compile(r'(?<!!)!([a-zA-Z_0-9]+)\[(\d+)\]|(?<!!)!(\d+)')
RE_SHELL_OPERATORS = re.compile(r'[&|;]')
RE_VAR_NAME = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')
RE_TAG_TID = re.compile(r'^([a-zA-Z_0-9]+)\[(\d+)\]$')
RE_TAG_MATCH = re.compile(r'^([a-zA-Z_0-9]+)\[(\d+)\]')
RE_DIGIT_MATCH = re.compile(r'^(\d+)')
RE_FORMATTING_TAGS = re.compile(
    r'\[(?:\/)?(?:dim|bold|italic|underline|strike|code|link|inverse|on|off)\]|\[\/\]'
)
RE_TAG_TID_FIND = re.compile(r'!([a-zA-Z_0-9]+)\[(\d+)\]')
RE_GID_FIND = re.compile(r'(?<!!)!(\d+)')


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


class CommandBlock(Static):
    """Виджет для отображения одной команды и её вывода."""

    MAX_DISPLAY_LINES = 50  # Максимум строк для отображения

    def __init__(self, header: str, raw_stdout: str, raw_stderr: str, return_code: int, **kwargs):
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
        self.collapsed = False
        self._truncated = False  # Флаг: вывод был обрезан

        # Формируем отображаемый контент
        self.text_content = self._format_output()
        super().__init__(self.text_content, **kwargs)
        self.can_focus = True

    def _truncate_output(self, text: str) -> str:
        """Обрезает вывод до MAX_DISPLAY_LINES."""
        lines = text.split('\n')
        if len(lines) <= self.MAX_DISPLAY_LINES:
            return text
        self._truncated = True
        # Показываем последние строки (более релевантны)
        truncated = '\n'.join(lines[-self.MAX_DISPLAY_LINES:])
        return f"[dim](...{len(lines) - self.MAX_DISPLAY_LINES} lines truncated, F5 to copy full output)[/dim]\n{truncated}"

    def _format_output(self) -> str:
        """Форматирует вывод команды."""
        if self.collapsed:
            # Свернутый вид — только заголовок
            indicator = "[dim]▶[/dim]"
            return f"{indicator} {self.header}\n"

        parts = [self.header]

        # Основной вывод (с обрезкой если нужно)
        if self.raw_stdout:
            stdout_display = self._truncate_output(self.raw_stdout.rstrip())
            parts.append(stdout_display)

        # Stderr внизу с подсветкой ошибки
        if self.raw_stderr and self.raw_stderr.strip():
            parts.append(f"[bold red]STDERR:[/bold red]\n{self.raw_stderr.rstrip()}")

        # Return code если != 0
        if self.return_code != 0:
            parts.append(f"[bold yellow]Exit code: {self.return_code}[/bold yellow]")

        return "\n".join(parts) + "\n\n"

    def toggle_collapse(self) -> None:
        """Переключает состояние сворачивания."""
        self.collapsed = not self.collapsed
        try:
            self.update(self._format_output())
        except Exception:
            # При очень большом выводе может быть ошибка рендеринга
            # В этом случае оставляем блок свернутым
            if not self.collapsed:
                self.collapsed = True
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
        self.update(self._format_output())

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

class InfoBlock(Static):
    """Виджет для отображения информационных сообщений (не от команд)."""

    def __init__(self, text_content: str, **kwargs):
        """
        Инициализация информационного блока.

        Args:
            text_content: Текст для отображения.
        """
        self.text_content = text_content.rstrip() + "\n\n"
        super().__init__(self.text_content, **kwargs)
        self.can_focus = True


class CompletionList(Static):
    """Выпадающий список подсказок для автодополнения."""

    DEFAULT_CSS = """
    CompletionList {
        layer: overlay;
        background: $surface;
        border: heavy $accent;
        width: auto;
        max-width: 80;
        height: auto;
        max-height: 12;
        overflow: hidden;
        padding: 0 1;
        display: none;
        offset-y: 3;  /* Сместить ниже input */
    }
    CompletionList .selected {
        background: $accent;
        color: $text;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.candidates: List[str] = []
        self.selected_index: int = 0

    def update_candidates(self, candidates: List[str]) -> None:
        """Обновить список кандидатов."""
        self.candidates = candidates[:10]  # max 10 items
        self.selected_index = 0
        if self.candidates:
            self._render_list()
            self.styles.display = "block"
        else:
            self.styles.display = "none"

    def _render_list(self) -> None:
        """Отрисовать список."""
        lines = []
        for i, cmd in enumerate(self.candidates):
            if i == self.selected_index:
                lines.append(f"[bold reverse] {cmd} [/bold reverse]")
            else:
                lines.append(f" {cmd}")
        self.update("\n".join(lines))

    def next_item(self) -> None:
        """Следующий элемент."""
        if self.candidates:
            self.selected_index = (self.selected_index + 1) % len(self.candidates)
            self._render_list()

    def prev_item(self) -> None:
        """Предыдущий элемент."""
        if self.candidates:
            self.selected_index = (self.selected_index - 1) % len(self.candidates)
            self._render_list()

    def get_selected(self) -> Optional[str]:
        """Получить выбранный элемент."""
        if self.candidates and 0 <= self.selected_index < len(self.candidates):
            return self.candidates[self.selected_index]
        return None

    def is_visible(self) -> bool:
        """Видим ли список."""
        return bool(self.candidates)

    def hide(self) -> None:
        """Скрыть список."""
        self.candidates = []
        self.styles.display = "none"


class CommandInput(Input):
    """Поле ввода с автодополнением по Tab из БД и истории сессии."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._completion_list: Optional[CompletionList] = None
        self._applying_completion: bool = False  # Флаг: применяем completion

    def set_completion_list(self, completion_list: 'CompletionList') -> None:
        """Привязать список подсказок (вызывается из App.on_mount)."""
        self._completion_list = completion_list

    def on_key(self, event: events.Key) -> None:
        """Обработка клавиш для автодополнения."""
        if not self._completion_list:
            return

        # Tab на пустой строке не должен переводить фокус
        if event.key == "tab" and not self.value.strip():
            event.stop()
            return

        # Навигация по списку
        if self._completion_list.is_visible():
            if event.key == "down":
                self._completion_list.next_item()
                event.stop()
                return
            elif event.key == "up":
                self._completion_list.prev_item()
                event.stop()
                return
            elif event.key == "tab" or event.key == "enter":
                selected = self._completion_list.get_selected()
                if selected:
                    self._applying_completion = True  # Устанавливаем флаг
                    self.value = selected
                    self.cursor_position = len(selected)
                    self._completion_list.hide()
                    event.stop()
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

        prefix = self.value.strip()
        is_path_context = hasattr(app, "_is_path_context") and app._is_path_context(self.value)
        if len(prefix) < 2 and not is_path_context:
            self._completion_list.hide()
            return

        candidates = app.get_completion_candidates(prefix)
        if candidates:
            # Если точное совпадение — не показываем (команда уже выбрана, пользователь добавляет аргументы)
            if len(candidates) == 1 and candidates[0] == prefix:
                self._completion_list.hide()
                return
            self._completion_list.update_candidates(candidates)
        else:
            self._completion_list.hide()


class QueryResultsBlock(Static):
    """
    Виджет для отображения результатов запроса с кликабельными командами.

    Отображает команды в формате:
    <global_id> tag[tid]  command_text
    где tag[tid] является кликабельным.
    """

    def __init__(self, content: str, **kwargs):
        """
        Инициализация блока результатов запроса.

        Args:
            content: Текст для отображения (без кликабельных элементов).
        """
        self.text_content = content.rstrip() + "\n\n"
        super().__init__(self.text_content, **kwargs)
        self.can_focus = True


class CommandRunner(App):
    """Textual приложение для запуска shell команд с поддержкой переменных."""

    CSS_PATH = "app.css"
    BINDINGS = [
        ("d", "toggle_dark", "Toggle dark mode"),
        Binding("up", "history_prev", "Previous command", priority=False),
        Binding("down", "history_next", "Next command", priority=False),
        ("pageup", "focus_previous", "Prev Block"),
        ("pagedown", "focus_next", "Next Block"),
        ("f5", "copy_block", "Copy Block"),
        ("f3", "open_json_viewer", "JSON Viewer"),
        Binding("shift+insert", "paste_clipboard", "Paste", show=False),
        Binding("ctrl+v", "paste_clipboard", "Paste", show=False),
        ("escape", "focus_input", "Focus Input"),
        Binding("space", "toggle_block_collapse", "Collapse", show=False),
        Binding("left", "collapse_block", "← Collapse", show=False),
        Binding("right", "expand_block", "→ Expand", show=False),
    ]

    TITLE = "IDvjPy_term"
    VERSION = "v1.1.16" # Truncate large output (max 500 lines), F5 copies full

    # --- Конфигурация и константы ---
    FILE_SETTINGS = "settings.yml"
    FILE_HISTORY = "history.txt"
    FILE_DATABASE = "history.db"
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
    
    CMD_QUIT = "q"
    CMD_WRITE = "w"
    CMD_HISTORY = "h"
    CMD_CLEAR = "c"
    CMD_JSON = "json"
    CMD_INGRESS = "i"
    CMD_HELP = "?"

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
        # Словарь локальных переменных окружения (имеют приоритет над os.environ)
        self.local_env: Dict[str, str] = {}
        # Словарь для хранения алиасов {alias: command}
        self.aliases: Dict[str, str] = {}
        # v1.1.9+: Парсер команд с поддержкой ссылок
        self.command_parser = CommandParser()
        # Kubernetes Ingress Analyzer
        self.ingress_analyzer: Optional[IngressAnalyzer] = None

    def _extract_path_token(self, text: str) -> str:
        """Возвращает последний токен для path completion."""
        if not text:
            return ""
        if text.endswith(" "):
            return ""
        parts = text.split()
        return parts[-1] if parts else text

    def _is_path_context(self, text: str) -> bool:
        """
        Проверяет, что ввод находится в path-контексте:
        - есть хотя бы один аргумент после команды, либо
        - последний токен явно похож на путь.
        """
        stripped = text.rstrip()
        if not stripped:
            return False

        parts = stripped.split()
        if len(parts) >= 2:
            return True

        token = self._extract_path_token(stripped)
        return token.startswith(("./", "../", "/", "~")) or token in (".", "..", "~")

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

        try:
            entries = os.listdir(parent)
        except Exception:
            return []

        suggestions: List[str] = []
        for name in entries:
            if base_prefix and not name.startswith(base_prefix):
                continue
            full_path = os.path.join(parent, name)
            candidate_path = os.path.join(parent, name) if parent != "." else name
            if token.startswith("~"):
                home = os.path.expanduser("~")
                if candidate_path.startswith(home):
                    candidate_path = "~" + candidate_path[len(home):]
            if os.path.isdir(full_path):
                candidate_path += "/"
            suggestions.append(candidate_path)

        return sorted(suggestions)

    def get_completion_candidates(self, prefix: str) -> List[str]:
        """
        Возвращает список команд из БД и истории сессии по префиксу.
        Для выпадающего списка подсказок.
        """
        raw_prefix = prefix
        prefix = prefix.strip()
        if not raw_prefix:
            return []
        candidates: List[str] = []
        try:
            from_db = database.get_commands_by_prefix(self.db_file, prefix)
            candidates.extend(from_db)
        except Exception:
            pass
        for cmd in self.session_history:
            if cmd.strip().startswith(prefix):
                candidates.append(cmd.strip())
        # Подсказки по файлам текущей директории (path-context).
        candidates.extend(self._get_file_completion_candidates(raw_prefix))
        # Уникальные, отсортированные, максимум 20
        return sorted(set(candidates))[:20]

    def on_key(self, event: events.Key) -> None:
        """Перехват клавиш для автофокуса на поле ввода."""
        # Явная вставка из буфера для терминалов, где Shift+Insert ловится нестабильно.
        if event.key in ("shift+insert", "ctrl+v"):
            self.action_paste_clipboard()
            event.stop()
            return

        # Если нажата печатаемая клавиша и фокус не на input — переводим фокус
        # Но не перехватываем если фокус на CommandBlock (для сворачивания Space)
        focused = self.focused
        if event.is_printable and not isinstance(focused, CommandBlock):
            input_widget = self.query_one(f"#{self.ID_INPUT}", Input)
            if not input_widget.has_focus:
                input_widget.focus()
                # Клавиша обработается input'ом автоматически

    def action_paste_clipboard(self) -> None:
        """Вставляет текст из буфера обмена в command input."""
        try:
            clip = pyperclip.paste()
        except Exception:
            return

        if clip is None:
            return

        input_widget = self.query_one(f"#{self.ID_INPUT}", Input)
        input_widget.focus()

        pos = input_widget.cursor_position
        current = input_widget.value or ""
        input_widget.value = current[:pos] + clip + current[pos:]
        input_widget.cursor_position = pos + len(clip)

    def on_mouse_scroll_down(self, event) -> None:
        """Скролл вниз всегда идёт в контейнер вывода."""
        container = self.query_one(f"#{self.ID_RESULTS_CONTAINER}", VerticalScroll)
        container.scroll_relative(1)

    def on_mouse_scroll_up(self, event) -> None:
        """Скролл вверх всегда идёт в контейнер вывода."""
        container = self.query_one(f"#{self.ID_RESULTS_CONTAINER}", VerticalScroll)
        container.scroll_relative(-1)

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

        # 2. Инициализация базы данных
        try:
            database.init_db(self.db_file)
        except Exception as e:
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

    def load_bashrc(self) -> None:
        """
        Читает файл .bashrc_term, парсит строки export VAR="VAL"
        и заполняет словарь self.local_env.
        Также обновляет os.environ для текущего процесса.

        Использует file locking для безопасного чтения при одновременной работе
        нескольких копий приложения.
        """
        # Создаем файл, если его нет (с блокировкой)
        if not os.path.exists(self.FILE_BASHRC):
            try:
                with open(self.FILE_BASHRC, "w", encoding=self.ENCODING) as f:
                    acquire_file_lock(f, self.FILE_LOCK_TIMEOUT)
                    f.write("# Terminal-specific environment variables\n")
                    release_file_lock(f)
            except FileLockTimeoutError:
                # Если не можем получить блокировку при создании, это не критично
                with open(self.FILE_BASHRC, "w", encoding=self.ENCODING) as f:
                    f.write("# Terminal-specific environment variables\n")
            except Exception as e:
                self.add_block(InfoBlock(f"Error creating {self.FILE_BASHRC}: {e}"))
                return

        try:
            # Пытаемся прочитать из файлов по порядку
            # Приоритет: .bashrc_term_{INSTANCE_NAME}, затем .bashrc_term (для обратной совместимости)
            bashrc_files = [self.FILE_BASHRC]
            if self.FILE_BASHRC != ".bashrc_term" and os.path.exists(".bashrc_term"):
                bashrc_files.append(".bashrc_term")

            for bashrc_file in bashrc_files:
                if not os.path.exists(bashrc_file):
                    continue

                with open(bashrc_file, "r", encoding=self.ENCODING) as f:
                    # Пытаемся получить блокировку для чтения
                    try:
                        acquire_file_lock(f, self.FILE_LOCK_TIMEOUT)
                    except FileLockTimeoutError:
                        # Если не удалось получить блокировку, читаем без неё
                        # (лучше прочитать без блокировки, чем вообще не прочитать)
                        pass

                    try:
                        for line in f:
                            line = line.strip()
                            # Ищем строки, начинающиеся с export и содержащие =
                            if line.startswith("export ") and "=" in line:
                                # Убираем "export "
                                assignment = line[7:]
                                # Разделяем на имя и значение (только по первому знаку =)
                                key, value = assignment.split("=", 1)
                                # Очищаем значение от кавычек
                                value = value.strip('"').strip("'")
                                self.local_env[key] = value
                                # Добавляем в окружение процесса, чтобы subprocess видел их
                                os.environ[key] = value
                    finally:
                        # Всегда освобождаем блокировку, если получили её
                        try:
                            release_file_lock(f)
                        except:
                            pass

                # Если нашли файл и прочитали переменные, выходим (приоритет первому файлу)
                if self.local_env:
                    break

        except Exception as e:
            # Если файл есть, но прочитать не удалось, сообщаем
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
            with open(alias_file, "r", encoding=self.ENCODING) as f:
                for line in f:
                    line = line.strip()
                    # Ищем строки, начинающиеся с alias
                    if line.startswith("alias ") and "=" in line:
                        # Убираем "alias "
                        alias_def = line[6:]
                        # Разделяем на имя и значение (только по первому знаку =)
                        parts = alias_def.split("=", 1)
                        if len(parts) == 2:
                            alias_name = parts[0].strip()
                            # Очищаем значение от кавычек (одинарных или двойных)
                            alias_value = parts[1].strip().strip('"').strip("'")
                            self.aliases[alias_name] = alias_value
        except Exception as e:
            self.add_block(InfoBlock(f"Warning: Error loading aliases from {alias_file}: {e}"))

    def on_ready(self) -> None:
        """Приветственное сообщение после загрузки UI."""
        self.add_block(InfoBlock(f"--- {self.TITLE} {self.VERSION} ---"))

    def compose(self) -> ComposeResult:
        """Построение UI."""
        yield Header()
        self._completion_list = CompletionList()
        yield self._completion_list
        yield CommandInput(placeholder="Enter command (type 2+ chars for completion)", id=self.ID_INPUT)
        yield VerticalScroll(id=self.ID_RESULTS_CONTAINER)
        yield Footer()

    def action_focus_input(self) -> None:
        """Переводит фокус в строку ввода."""
        self.query_one(f"#{self.ID_INPUT}", Input).focus()

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

                pyperclip.copy(text_to_copy)
                self.sub_title = self.MSG_COPIED
                self.set_timer(self.TIMER_DELAY, self.clear_subtitle)
            except Exception:
                self.sub_title = "Error copying to clipboard."
                self.set_timer(self.TIMER_DELAY, self.clear_subtitle)
        elif isinstance(focused, InfoBlock):
            try:
                # Для InfoBlock копируем весь текст
                clean_text = self._strip_formatting_tags(focused.text_content)
                pyperclip.copy(clean_text)
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
        Открывает JSON viewer для последнего блока (F3).
        Работает аналогично команде :json.
        """
        all_blocks = self.query("CommandBlock, InfoBlock")
        if all_blocks:
            # Берём последний блок
            last_block = list(all_blocks)[-1]

            # Извлекаем JSON
            try:
                # Для CommandBlock используем raw_stdout, для InfoBlock - text_content
                if isinstance(last_block, CommandBlock):
                    text_to_parse = last_block.raw_stdout
                else:
                    text_to_parse = self._strip_formatting_tags(last_block.text_content)

                json_data = self._extract_json(text_to_parse)

                if json_data is not None:
                    self.push_screen(JSONViewer(json_data))
                    self.sub_title = "JSON viewer opened! Press Escape to close."
                    self.set_timer(2, self.clear_subtitle)
                else:
                    self.sub_title = "No valid JSON found in last block."
                    self.set_timer(self.TIMER_DELAY, self.clear_subtitle)
            except Exception as e:
                self.sub_title = f"Error parsing JSON: {e}"
                self.set_timer(self.TIMER_DELAY, self.clear_subtitle)
        else:
            self.sub_title = "No blocks found."
            self.set_timer(self.TIMER_DELAY, self.clear_subtitle)

    def _extract_json(self, text: str) -> Optional[dict]:
        """
        Извлекает JSON из текста.

        Пытается найти и распарсить JSON в тексте. Поскольку вывод команды
        может содержать дополнительный текст (например, временную метку),
        ищем первый валидный JSON объект.

        Args:
            text: Текст для поиска JSON

        Returns:
            Распаршенные JSON данные или None если не найден
        """
        import json

        # Сначала пробуем распарсить весь текст как есть
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        # Если не получилось, ищем JSON в тексте
        # Находим первую открывающую скобку { или [
        first_brace_pos = -1
        for i, char in enumerate(text):
            if char in '{[':
                first_brace_pos = i
                break

        if first_brace_pos == -1:
            return None

        # Находим соответствующую закрывающую скобку
        bracket_count = 0
        start_char = text[first_brace_pos]
        end_char = '}' if start_char == '{' else ']'

        in_string = False
        escape_next = False

        for i in range(first_brace_pos, len(text)):
            char = text[i]

            if escape_next:
                escape_next = False
                continue

            if char == '\\':
                escape_next = True
                continue

            if char == '"' and not escape_next:
                in_string = not in_string
                continue

            if not in_string:
                if char == start_char:
                    bracket_count += 1
                elif char == end_char:
                    bracket_count -= 1
                    if bracket_count == 0:
                        # Нашли конец JSON
                        json_text = text[first_brace_pos:i+1]
                        try:
                            return json.loads(json_text)
                        except json.JSONDecodeError:
                            # Если не получилось парсить, продолжаем поиск
                            break

        # Если не получилось с точным подсчётом, пробуем более простой подход
        # Ищем строки, начинающиеся с { или [
        lines = text.split('\n')
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if line_stripped.startswith('{') or line_stripped.startswith('['):
                # Собираем от этой строки до конца
                candidate = '\n'.join(lines[i:])
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    # Пробуем добавлять строки по одной
                    for j in range(i + 1, len(lines) + 1):
                        candidate = '\n'.join(lines[i:j])
                        try:
                            return json.loads(candidate)
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
        """Открывает JSON viewer для последнего блока."""
        all_blocks = self.query("CommandBlock, InfoBlock")
        if all_blocks:
            # Берём последний блок
            last_block = list(all_blocks)[-1]

            # Извлекаем JSON
            try:
                # Для CommandBlock используем raw_stdout, для InfoBlock - text_content
                if isinstance(last_block, CommandBlock):
                    text_to_parse = last_block.raw_stdout
                else:
                    text_to_parse = self._strip_formatting_tags(last_block.text_content)

                json_data = self._extract_json(text_to_parse)

                if json_data is not None:
                    self.push_screen(JSONViewer(json_data))
                    self.sub_title = "JSON viewer opened! Press Escape to close."
                    self.set_timer(2, self.clear_subtitle)
                else:
                    self.add_block(InfoBlock("No valid JSON found in last block."))
            except Exception as e:
                self.add_block(InfoBlock(f"Error parsing JSON: {e}"))
        else:
            self.add_block(InfoBlock("[bold]ERROR:[/bold] No blocks found."))

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
                for line in lines[-num_lines:]:
                    self.add_block(InfoBlock(line.strip()))
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
        else:
            self.add_block(InfoBlock(f"Unknown command: '{command}'"))

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
  :h [N]      - Show shell history (default: 20 lines)
  :c          - Clear all output blocks
  :json       - Open JSON viewer (from last block)
  :json <file>- Open JSON file in viewer
  :i          - Kubernetes Ingress Analyzer (see :i for details)

[bold]Kubernetes Commands (prefix :i)[/bold]
  :i list             - List all ingresses
  :i list -n <ns>     - List ingresses in namespace
  :i ns <namespace>   - Describe namespace (JSON viewer)
  :i analyze <name>   - Analyze ingress
  :i check <service>  - Check service endpoints

[bold]Command Prefixes[/bold]
  (none)     - Execute shell command
  #<tag>     - Save command to database with tag
  ?          - Query database (? all, ?<tag>, ?? grouped)
  !N         - Execute command by ID from last query
  |<cmd>     - Pipe focused block output to command
  $VAR=val   - Set environment variable

[bold]Navigation[/bold]
  ↑/↓        - Command history (when input focused)
  PgUp/PgDn  - Navigate output blocks
  Space      - Toggle block collapse
  F3         - Open focused block in JSON viewer
  F5         - Copy full output to clipboard

[bold]Variables[/bold]
  Use $VAR in commands for variable substitution
  $NS is auto-set when using -n in :i commands
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
        - #tag=ID=comment      - установить комментарий к конкретной команде (v1.1.2+)

        Логика парсинга:
        1. Проверка на "=" с двумя знаками -> комментарий к команде
        2. Проверка на "=" с одним знаком -> комментарий к тегу
        3. Проверка на "+" -> редактирование команды
        4. Проверка на "-" -> удаление команд
        5. Иначе -> сохранение новой команды
        """
        content = user_input[1:].strip()

        # === Секция 1: Обработка комментариев ===
        # Проверяем на наличие "=" (комментарий к тегу или к команде)
        if '=' in content and not content.startswith('-'):
            # Подсекция 1.1: Комментарий к конкретной команде
            # Формат: #tag=ID=comment (два знака "=")
            if content.count('=') >= 2:
                # Парсим строку: tag=ID=comment -> [tag, ID, comment]
                parts = content.split('=', 2)
                tag = parts[0].strip()
                tid_str = parts[1].strip()
                comment = parts[2].strip() if len(parts) > 2 else ""

                # Валидация: tag должен быть непустым, ID - числом
                if not tag or not tid_str.isdigit():
                    self.add_block(InfoBlock("Invalid syntax. Use: #tag=ID=<comment>"))
                    return

                try:
                    tid = int(tid_str)
                    # Обновляем комментарий в БД
                    database.set_command_comment(self.db_file, tag, tid, comment)
                    self.add_block(InfoBlock(f"Command {tag}[{tid}] comment set to: '{comment}'"))
                except Exception as e:
                    self.add_block(InfoBlock(f"Database error: {e}"))
                return

            # Подсекция 1.2: Комментарий к тегу
            # Формат: #tag=comment (один знак "=")
            else:
                parts = content.split('=', 1)
                tag = parts[0].strip()
                comment = parts[1].strip() if len(parts) > 1 else ""

                if not tag:
                    self.add_block(InfoBlock("Invalid syntax. Use: #tag=<comment>"))
                    return

                try:
                    database.set_tag_comment(self.db_file, tag, comment)
                    self.add_block(InfoBlock(f"Tag '{tag}' comment set to: '{comment}'"))
                except Exception as e:
                    self.add_block(InfoBlock(f"Database error: {e}"))
                return

        # === Секция 1.3: Редактирование команд ===
        # Проверяем на наличие "+" после тега (редактирование)
        # Формат: #tag+ID (редактировать команду) или #tag+ (редактировать последнюю)
        # Формат с заменой: #tag+ID новая_команда (сразу заменить команду)
        if '+' in content:
            parts = content.split('+', 1)
            tag = parts[0].strip()
            identifier_and_more = parts[1].strip() if len(parts) > 1 else None

            if not tag:
                self.add_block(InfoBlock("Invalid syntax. Use: #tag+<ID> to edit command"))
                return

            try:
                # Проверяем, есть ли дополнительный текст после ID
                if identifier_and_more:
                    # Разделяем identifier и новую команду (если есть)
                    id_parts = identifier_and_more.split(maxsplit=1)
                    identifier = id_parts[0]
                    new_command = id_parts[1].strip() if len(id_parts) > 1 else None

                    if identifier.isdigit():
                        tid = int(identifier)

                        # Если указана новая команда - сразу обновляем
                        if new_command:
                            result = database.get_command_by_tid(self.db_file, tag, tid)
                            if result:
                                database.update_command_by_tid(self.db_file, tag, tid, new_command)
                                self.add_block(InfoBlock(f"Updated {tag}[{tid}] to: '{new_command}'"))
                            else:
                                self.add_block(InfoBlock(f"Error: Command {tag}[{tid}] not found."))
                        else:
                            # Иначе загружаем в input для редактирования
                            result = database.get_command_by_tid(self.db_file, tag, tid)
                            if result:
                                command_text = result['command']
                                # Вставляем команду в input для редактирования
                                input_widget = self.query_one(f"#{self.ID_INPUT}", Input)
                                input_widget.value = f"#{tag} {command_text}"
                                input_widget.cursor_position = len(f"#{tag} ") + len(command_text)
                                input_widget.focus()
                                self.add_block(InfoBlock(f"Editing {tag}[{tid}]. Edit and press Enter to save."))
                            else:
                                self.add_block(InfoBlock(f"Error: Command {tag}[{tid}] not found."))
                    else:
                        self.add_block(InfoBlock("Invalid syntax. Use: #tag+<ID> or #tag+ to edit"))
                else:
                    # Редактирование последней команды тега: #deploy+
                    # Получаем все команды тега и находим последнюю (по tid)
                    all_commands = database.get_commands_by_tag(self.db_file, tag)
                    active_commands = [cmd for cmd in all_commands if not cmd.get('deleted', False)]

                    if active_commands:
                        # Сортируем по tid убыванию и берем последнюю
                        last_cmd = max(active_commands, key=lambda x: x['tid'])
                        tid = last_cmd['tid']
                        command_text = last_cmd['command']
                        # Вставляем команду в input для редактирования
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

        # === Секция 2: Обработка удаления команд ===
        # Проверяем на наличие дефиса (сигнал удаления)
        if '-' in content:
            parts = content.split('-', 1)
            tag = parts[0]
            identifier = parts[1]

            try:
                if not identifier:
                    # Случай: #deploy-
                    database.delete_commands_by_tag(self.db_file, tag)
                    self.add_block(InfoBlock(f"All commands with tag '{tag}' marked as deleted."))
                elif identifier.isdigit():
                    # Случай: #deploy-5
                    cmd_id = int(identifier)
                    database.delete_command_by_tid(self.db_file, tag, cmd_id)
                    self.add_block(InfoBlock(f"Command {tag}[{cmd_id}] marked as deleted."))
                else:
                    self.add_block(InfoBlock("Invalid delete syntax. Use #tag- or #tag-tid"))
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
                            # Глобальный ID в угловых скобках с dim-стилем для менее яркого цвета
                            if cmd_comment:
                                content += f"  [dim]<{gid}>[/] [bold]{tag}[{tid}][/bold]  {cmd}  # {cmd_comment}\n"
                            else:
                                content += f"  [dim]<{gid}>[/] [bold]{tag}[{tid}][/bold]  {cmd}\n"
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
                        comment_part = f"  # {row['comment']}" if 'comment' in row.keys() and row['comment'] else ""
                        lines.append(f"  [dim]<{row['id']}>[/] [bold]{tag_part}[{row['tid']}][/bold]  {row['command']}{comment_part}")
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
            
    def handle_normal_command(self, command: str, stdin_data: Optional[str] = None) -> None:
        """
        Обертка для выполнения обычной команды с обновлением истории.

        v1.1.9+: Раскрытие ссылок !tag[tid] и !ID происходит в on_input_submitted,
        поэтому здесь мы просто выполняем уже раскрытую команду.
        """
        if command not in self.session_history:
            self.session_history.append(command)
        self.session_history_pos = len(self.session_history)
        self.run_command(command, stdin_data)

    def action_history_prev(self) -> None:
        """Навигация истории назад (только если фокус на input)."""
        input_widget = self.query_one(f"#{self.ID_INPUT}", Input)
        if not input_widget.has_focus:
            return  # Не перехватываем если фокус на контейнере вывода
        if not self.session_history: return
        if self.session_history_pos > 0:
            self.session_history_pos -= 1
            input_widget.value = self.session_history[self.session_history_pos]
            input_widget.cursor_position = len(input_widget.value)

    def action_history_next(self) -> None:
        """Навигация истории вперед (только если фокус на input)."""
        input_widget = self.query_one(f"#{self.ID_INPUT}", Input)
        if not input_widget.has_focus:
            return  # Не перехватываем если фокус на контейнере вывода
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
        """
        Заменяет переменные вида $VAR_NAME на значения.
        Приоритет: self.local_env > os.environ.
        """
        def replacer(match):
            var_name = match.group(1)
            if var_name in self.local_env:
                return self.local_env[var_name]
            if var_name in os.environ:
                return os.environ[var_name]
            # Если переменной нет нигде, оставляем $NAME как есть (чтобы shell сам вывел ошибку)
            return match.group(0)

        return RE_VAR_SUBST.sub(replacer, command)

    def _expand_aliases(self, command: str) -> str:
        """
        Заменяет алиасы в команде на их значения.
        Работает с первым словом команды.
        """
        # Разбиваем команду на части, сохраняя кавычки
        parts = command.strip().split(None, 1) if command.strip() else []
        if not parts:
            return command

        first_word = parts[0]
        # Проверяем, является ли первое слово алиасом
        if first_word in self.aliases:
            alias_value = self.aliases[first_word]
            # Если есть остаток команды, добавляем его
            if len(parts) > 1:
                return f"{alias_value} {parts[1]}"
            return alias_value

        return command

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
        
        initial_text = f"{header}\n[Executing...]\n(Waiting for output or timeout...)"
        block = CommandBlock(
            header=header, 
            raw_stdout="[Executing...]", 
            raw_stderr="", 
            return_code=0
        )
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
        
if __name__ == "__main__":
    app = CommandRunner()
    app.run()
