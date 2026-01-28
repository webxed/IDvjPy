# Authors: markovskiy.pavel, Gemini (Google)
import subprocess
import yaml
import datetime
import os
import pyperclip
import database
import threading
from typing import List, Optional
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, Static
from textual.containers import VerticalScroll

class CommandBlock(Static):
    """Виджет для отображения одной команды и её вывода."""
    
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
        
        # Формируем строку, имитирующую результат subprocess.run
        display_output = (
            f"CompletedProcess(returncode={self.return_code}, "
            f"stdout='{self.raw_stdout}', stderr='{self.raw_stderr}')"
        )
        self.text_content = f"{self.header}\n{display_output}".rstrip() + "\n"
        
        super().__init__(self.text_content, **kwargs)
        self.can_focus = True

    def update_content(self, raw_stdout: str, raw_stderr: str, return_code: int) -> None:
        """
        Обновляет содержимое блока после завершения выполнения команды в фоновом потоке.
        Этот метод безопасно вызывается из другого потока через call_from_thread.
        """
        self.raw_stdout = raw_stdout
        self.raw_stderr = raw_stderr
        self.return_code = return_code
        
        display_output = (
            f"CompletedProcess(returncode={self.return_code}, "
            f"stdout='{self.raw_stdout}', stderr='{self.raw_stderr}')"
        )
        final_content = f"{self.header}\n{display_output}".rstrip() + "\n"
        
        # Используем метод update родительского класса для перерисовки
        self.update(final_content)

    def on_focus(self) -> None:
        """
        Событие получения фокуса.
        Запоминает этот блок как активный источник для пайпинга.
        """
        if hasattr(self.app, 'active_pipe_source'):
            self.app.active_pipe_source = self

class InfoBlock(Static):
    """Виджет для отображения информационных сообщений (не от команд)."""
    
    def __init__(self, text_content: str, **kwargs):
        self.text_content = text_content
        super().__init__(text_content, **kwargs)
        self.can_focus = True

class CommandRunner(App):
    """Textual приложение для запуска shell команд с защитой от зависания."""

    CSS_PATH = "app.css"
    BINDINGS = [
        ("d", "toggle_dark", "Toggle dark mode"),
        ("up", "history_prev", "Previous command"),
        ("down", "history_next", "Next command"),
        ("pageup", "focus_previous", "Prev Block"),
        ("pagedown", "focus_next", "Next Block"),
        ("f5", "copy_block", "Copy Block"),
        ("escape", "focus_input", "Focus Input"),
    ]

    TITLE = "IDvjPy_term"
    VERSION = "v1.0.5" # Timeout protection

    # --- Константы ---
    FILE_SETTINGS = "settings.yml"
    FILE_HISTORY = "history.txt"
    FILE_DATABASE = "history.db" # Файл БД по умолчанию
    ID_INPUT = "command-input"
    ID_RESULTS_CONTAINER = "results-container"
    KEY_HISTORY_LINES = "history_lines"
    ENCODING = "utf-8"
    TIMER_DELAY = 2
    
    # Время ожидания команды (в секундах). 
    COMMAND_TIMEOUT = 10 
    
    MSG_COPIED = "Copied to clipboard!"
    MSG_NO_FOCUS = "No command block focused."
    MSG_TIMEOUT = "Process timed out (likely waiting for interactive input). Process killed."
    
    PREFIX_CMD = ":"
    PREFIX_TAG = "#"
    PREFIX_QUERY = "?"
    PREFIX_BANG = "!"
    PREFIX_PIPE = "|"
    
    CMD_QUIT = "q"
    CMD_WRITE = "w"
    CMD_HISTORY = "h"

    def __init__(self):
        """Инициализация состояния приложения."""
        super().__init__()
        self.session_history: List[str] = []
        self.session_history_pos: int = 0
        self.last_query_results: List[str] = []
        self.history_lines: int = 20
        self.db_file = self.FILE_DATABASE # Инициализируем путь к БД
        self.active_pipe_source: Optional[CommandBlock] = None

    def on_mount(self) -> None:
        """Настройка приложения при запуске."""
        # Загрузка настроек
        try:
            with open(self.FILE_SETTINGS, "r", encoding=self.ENCODING) as f:
                settings = yaml.safe_load(f)
                if settings:
                    self.history_lines = settings.get(self.KEY_HISTORY_LINES, 20)
                    self.COMMAND_TIMEOUT = settings.get("command_timeout", 10)
                    # Загружаем путь к БД из настроек, если указан
                    self.db_file = settings.get("database_tags_file", self.FILE_DATABASE)
        except (FileNotFoundError, KeyError, yaml.YAMLError):
            pass

        # Инициализация БД с корректным путем
        try:
            database.init_db(self.db_file)
        except Exception as e:
            self.sub_title = f"DB Error: {e}"
            self.set_timer(5, self.clear_subtitle)

    def on_ready(self) -> None:
        """Приветственное сообщение."""
        self.add_block(InfoBlock(f"--- {self.TITLE} {self.VERSION} ---"))

    def compose(self) -> ComposeResult:
        """Построение UI."""
        yield Header()
        yield Input(placeholder="Enter command, #tag <cmd>, ? <tag>, or :q/:w", id=self.ID_INPUT)
        yield VerticalScroll(id=self.ID_RESULTS_CONTAINER)
        yield Footer()

    def action_focus_input(self) -> None:
        """Фокус на поле ввода."""
        self.query_one(f"#{self.ID_INPUT}", Input).focus()

    def add_block(self, block: Static) -> None:
        """
        Добавляет блок в UI.
        Важно: кратковременно передает фокус блоку, чтобы обновился active_pipe_source,
        затем возвращает фокус в Input.
        """
        container = self.query_one(f"#{self.ID_RESULTS_CONTAINER}", VerticalScroll)
        container.mount(block)
        block.focus()
        self.query_one(f"#{self.ID_INPUT}", Input).focus()
        container.scroll_end()

    def clear_subtitle(self) -> None:
        """Очистка статусной строки."""
        self.sub_title = ""

    def action_copy_block(self) -> None:
        """Копирование содержимого блока в буфер обмена."""
        focused = self.focused
        if isinstance(focused, (CommandBlock, InfoBlock)):
            try:
                pyperclip.copy(focused.text_content)
                self.sub_title = self.MSG_COPIED
                self.set_timer(self.TIMER_DELAY, self.clear_subtitle)
            except Exception:
                self.sub_title = "Error copying to clipboard."
                self.set_timer(self.TIMER_DELAY, self.clear_subtitle)
        else:
            self.sub_title = self.MSG_NO_FOCUS
            self.set_timer(self.TIMER_DELAY, self.clear_subtitle)

    def on_input_submitted(self, message: Input.Submitted) -> None:
        """Главный диспетчер команд."""
        user_input = message.value.strip()
        input_widget = self.query_one(f"#{self.ID_INPUT}", Input)
        input_widget.value = ""

        if not user_input:
            return

        self.log_to_history(user_input)

        # Маршрутизация по префиксам
        if user_input.startswith(self.PREFIX_CMD):
            self.handle_colon_command(user_input)
        elif user_input.startswith(self.PREFIX_TAG):
            self.handle_save_command(user_input)
        elif user_input.startswith(self.PREFIX_QUERY):
            self.handle_query_command(user_input)
        elif user_input.startswith(self.PREFIX_BANG):
            self.handle_bang_command(user_input)
        elif user_input.startswith(self.PREFIX_PIPE):
            self.handle_pipe_command(user_input)
        else:
            self.handle_normal_command(user_input)

    def log_to_history(self, command: str) -> None:
        """Запись команды в файл истории (игнорируя спецкоманды и дубликаты)."""
        prefixes = (self.PREFIX_CMD, self.PREFIX_QUERY, self.PREFIX_BANG, self.PREFIX_TAG, self.PREFIX_PIPE)
        if command.startswith(prefixes):
            return

        last_command = None
        try:
            if os.path.exists(self.FILE_HISTORY):
                with open(self.FILE_HISTORY, "r", encoding=self.ENCODING) as f:
                    lines = f.readlines()
                    if lines:
                        last_command = lines[-1].strip()
        except IOError:
            return

        if command != last_command:
            try:
                with open(self.FILE_HISTORY, "a", encoding=self.ENCODING) as f:
                    f.write(f"{command}\n")
            except IOError:
                pass

    def handle_colon_command(self, user_input: str) -> None:
        """Обработка метакоманд (:q, :w, :h)."""
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
                    content_to_write = "\n\n---\n\n".join(block.text_content for block in all_blocks)
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
        else:
            self.add_block(InfoBlock(f"Unknown command: '{command}'"))

    def handle_save_command(self, user_input: str) -> None:
        """Сохранение команды в БД."""
        content = user_input[1:].strip()
        parts = content.split(maxsplit=1)
        if len(parts) == 2:
            tag, command_to_save = parts
            try:
                # ИСПРАВЛЕНО: Добавлен self.db_file
                database.add_command(self.db_file, command_to_save, tag)
                self.add_block(InfoBlock(f"Saved: '{command_to_save}' with tag '{tag}'"))
            except Exception as e:
                self.add_block(InfoBlock(f"Database error: {e}"))
        else:
            self.add_block(InfoBlock("Invalid syntax. Use: #tag <command>"))

    def handle_query_command(self, user_input: str) -> None:
        """Поиск команд в БД."""
        tag_part = user_input[1:].strip()
        self.last_query_results = []
        try:
            if not tag_part:
                # ИСПРАВЛЕНО: Добавлен self.db_file
                tags = database.get_all_tags(self.db_file)
                content = "Available tags:\n" + ("\n".join(f"  - {tag}" for tag in tags) if tags else "  (None found)")
                content += "\n\nType `? <tag>` to see commands."
                self.add_block(InfoBlock(content))
            else:
                # ИСПРАВЛЕНО: Добавлен self.db_file
                commands = database.get_commands_by_tag(self.db_file, tag_part)
                content = f"Commands for tag '{tag_part}':\n"
                if not commands:
                    content += "  (None found)"
                else:
                    # Преобразуем список кортежей (id, command) в список строк команд
                    # или используем индексацию, как в database.py возвращается List[Row]
                    # Предполагаем, что database.get_commands_by_tag возвращает [{'id': ..., 'command': ...}, ...]
                    # или список строк. Исходя из database.py -> cursor.fetchall() с row_factory=sqlite3.Row
                    # commands будет списком объектов Row.
                    
                    self.last_query_results = [row['command'] for row in commands]
                    content += "\n".join(f"  [{row['id']}] {row['command']}" for row in commands)
                    content += "\n\nUse `! <id>` to execute."
                self.add_block(InfoBlock(content))
        except Exception as e:
            self.add_block(InfoBlock(f"Database error: {e}"))

    def handle_bang_command(self, user_input: str) -> None:
        """Выполнение команды из результата поиска."""
        command_part = user_input[1:].strip()
        
        # Поддержка как числового индекса (старый стиль), так и ID из БД
        if command_part.isdigit():
            idx = int(command_part)
            
            # Пробуем найти по индексу в списке последних результатов (совместимость с версией без ID)
            if 0 <= idx - 1 < len(self.last_query_results):
                 input_widget = self.query_one(f"#{self.ID_INPUT}", Input)
                 input_widget.value = self.last_query_results[idx - 1]
                 input_widget.cursor_position = len(input_widget.value)
                 return
            
            # Если не нашли по индексу, пробуем найти по ID (новый стиль)
            # Для этого нужно было бы хранить словарь {id: command}, но у нас список.
            # Для упрощения оставим поиск по индексу списка, как в handle_query_command
            # там я заполнил last_query_results списком команд.
            
            self.add_block(InfoBlock("Error: Invalid number."))
        else:
            self.add_block(InfoBlock("Invalid syntax. Use: ! <number>"))

    def handle_pipe_command(self, user_input: str) -> None:
        """
        Обработка пайпинга (| cmd).
        Логика выбора источника:
        1. Если пользователь выделил блок навигацией (PageUp/PageDown), используем его.
        2. Иначе используем самый последний выполненный блок.
        """
        pipe_command = user_input[1:].strip()
        if not pipe_command:
            self.add_block(InfoBlock("Error: Pipe command cannot be empty."))
            return

        source_block = self.active_pipe_source if self.active_pipe_source else self.query(CommandBlock).last()

        if source_block is None:
            self.add_block(InfoBlock("Error: No command output available to pipe from."))
            return
            
        input_for_pipe = source_block.raw_stdout
        self.handle_normal_command(pipe_command, stdin_data=input_for_pipe)
            
    def handle_normal_command(self, command: str, stdin_data: Optional[str] = None) -> None:
        """Обертка для запуска команды (обновляет историю сессии)."""
        if command not in self.session_history:
            self.session_history.append(command)
        self.session_history_pos = len(self.session_history)
        self.run_command(command, stdin_data)

    def action_history_prev(self) -> None:
        """Навигация по истории ввода (назад)."""
        if not self.session_history: return
        input_widget = self.query_one(f"#{self.ID_INPUT}", Input)
        if self.session_history_pos > 0:
            self.session_history_pos -= 1
            input_widget.value = self.session_history[self.session_history_pos]
            input_widget.cursor_position = len(input_widget.value)

    def action_history_next(self) -> None:
        """Навигация по истории ввода (вперед)."""
        if not self.session_history: return
        input_widget = self.query_one(f"#{self.ID_INPUT}", Input)
        if self.session_history_pos < len(self.session_history) - 1:
            self.session_history_pos += 1
            input_widget.value = self.session_history[self.session_history_pos]
            input_widget.cursor_position = len(input_widget.value)
        else:
            self.session_history_pos = len(self.session_history)
            input_widget.value = ""
            input_widget.cursor_position = 0

    def _execute_in_thread(self, block: CommandBlock, command: str, stdin_data: Optional[str]) -> None:
        """
        Функция, запускаемая в отдельном потоке.
        """
        raw_stdout, raw_stderr, return_code = "", "", 0
        
        if command:
            try:
                process = subprocess.run(
                    command, shell=True, capture_output=True, text=True,
                    encoding=self.ENCODING, errors='replace', input=stdin_data,
                    timeout=self.COMMAND_TIMEOUT 
                )
                raw_stdout = process.stdout.strip()
                raw_stderr = process.stderr.strip()
                return_code = process.returncode
                
            except subprocess.TimeoutExpired:
                raw_stderr = f"{self.MSG_TIMEOUT}"
                return_code = -124 
            except Exception as e:
                raw_stderr = str(e)
                return_code = -1
        
        self.call_from_thread(block.update_content, raw_stdout, raw_stderr, return_code)

    def run_command(self, command: str, stdin_data: Optional[str] = None) -> None:
        """
        Инициатор выполнения команды.
        """
        timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
        cwd = os.getcwd()
        header = f"{timestamp} ({cwd}) $ {command}"
        
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
        
        thread = threading.Thread(
            target=self._execute_in_thread, 
            args=(block, command, stdin_data),
            daemon=True
        )
        thread.start()
        
if __name__ == "__main__":
    app = CommandRunner()
    app.run()
