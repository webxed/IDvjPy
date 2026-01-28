# Authors: markovskiy.pavel, Gemini (Google)
import subprocess
import yaml
import datetime
import os
import pyperclip
import database
from typing import List, Optional, Dict, Any
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, Static
from textual.containers import VerticalScroll

class CommandBlock(Static):
    """Виджет для отображения одной команды и её вывода."""
    
    def __init__(self, header: str, raw_stdout: str, raw_stderr: str, return_code: int, **kwargs):
        """
        Инициализация блока команды.
        
        Args:
            header: Заголовок с меткой времени и самой командой.
            raw_stdout: Стандартный вывод команды.
            raw_stderr: Стандартный вывод ошибок.
            return_code: Код возврата процесса.
        """
        self.header = header
        self.raw_stdout = raw_stdout
        self.raw_stderr = raw_stderr
        self.return_code = return_code
        
        # Формируем строку вывода, имитирующую объект CompletedProcess
        display_output = (
            f"CompletedProcess(returncode={self.return_code}, "
            f"stdout='{self.raw_stdout}', stderr='{self.raw_stderr}')"
        )
        self.text_content = f"{self.header}\n{display_output}".rstrip() + "\n"
        
        super().__init__(self.text_content, **kwargs)
        self.can_focus = True

class InfoBlock(Static):
    """Виджет для отображения информационных сообщений (не от команд)."""
    
    def __init__(self, text_content: str, **kwargs):
        """
        Инициализация информационного блока.
        
        Args:
            text_content: Текст для отображения.
        """
        self.text_content = text_content
        super().__init__(text_content, **kwargs)
        self.can_focus = True

class CommandRunner(App):
    """Textual приложение для запуска shell команд."""

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
    VERSION = "v1.0.4"

    # --- Конфигурация и константы ---
    
    # Файлы
    FILE_SETTINGS = "settings.yml"
    FILE_HISTORY = "history.txt"
    
    # ID виджетов для Textual query selector
    ID_INPUT = "command-input"
    ID_RESULTS_CONTAINER = "results-container"
    
    # Настройки
    KEY_HISTORY_LINES = "history_lines"
    ENCODING = "utf-8"
    TIMER_DELAY = 2  # Задержка в секундах для очистки сообщений
    
    # Соинщения пользователю
    MSG_COPIED = "Copied to clipboard!"
    MSG_NO_FOCUS = "No command block focused."
    
    # Префиксы команд
    PREFIX_CMD = ":"
    PREFIX_TAG = "#"
    PREFIX_QUERY = "?"
    PREFIX_BANG = "!"
    PREFIX_PIPE = "|"
    
    # Внутренние команды (для префикса :)
    CMD_QUIT = "q"
    CMD_WRITE = "w"
    CMD_HISTORY = "h"

    def __init__(self):
        """Инициализирует приложение и переменные состояния сессии."""
        super().__init__()
        self.session_history: List[str] = []       # История команд текущей сессии
        self.session_history_pos: int = 0           # Текущая позиция в истории
        self.last_query_results: List[str] = []    # Результаты последнего поиска по тегам
        self.history_lines: int = 20               # Лимит строк истории

    def on_mount(self) -> None:
        """
        Вызывается при старте приложения.
        Загружает настройки из YAML файла и инициализирует БД.
        """
        try:
            database.init_db()
        except Exception as e:
            self.sub_title = f"DB Error: {e}"
            self.set_timer(5, self.clear_subtitle)

        try:
            with open(self.FILE_SETTINGS, "r", encoding=self.ENCODING) as f:
                settings = yaml.safe_load(f)
                if settings:
                    self.history_lines = settings.get(self.KEY_HISTORY_LINES, 20)
        except (FileNotFoundError, KeyError, yaml.YAMLError):
            pass # Оставляем значения по умолчанию

    def on_ready(self) -> None:
        """Вызывается, когда UI полностью готов. Отображает приветствие."""
        self.add_block(InfoBlock(f"--- {self.TITLE} {self.VERSION} ---"))

    def compose(self) -> ComposeResult:
        """Создает структуру виджетов приложения."""
        yield Header()
        yield Input(placeholder="Enter command, #tag <cmd>, ? <tag>, or :q/:w", id=self.ID_INPUT)
        yield VerticalScroll(id=self.ID_RESULTS_CONTAINER)
        yield Footer()

    def action_focus_input(self) -> None:
        """Переводит фокус в строку ввода."""
        self.query_one(f"#{self.ID_INPUT}", Input).focus()

    def add_block(self, block: Static) -> None:
        """
        Добавляет блок в контейнер, прокручивает вниз и возвращает фокус на ввод.
        
        Args:
            block: Экземпляр CommandBlock или InfoBlock.
        """
        container = self.query_one(f"#{self.ID_RESULTS_CONTAINER}", VerticalScroll)
        container.mount(block)
        
        # Кратковременно фокусируем новый блок, чтобы он считался "активным" для навигации/копирования
        block.focus()
        # Сразу возвращаем фокус ввод, чтобы пользователь мог продолжить работу
        self.query_one(f"#{self.ID_INPUT}", Input).focus()
        
        container.scroll_end()

    def clear_subtitle(self) -> None:
        """Удаляет текст из подзаголовка (статус-бара)."""
        self.sub_title = ""

    def action_copy_block(self) -> None:
        """Копирует содержимое сфокусированного блока в буфер обмена."""
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
        """
        Обработчик нажатия Enter в поле ввода.
        Анализирует префикс и маршрутизирует команду.
        """
        user_input = message.value.strip()
        input_widget = self.query_one(f"#{self.ID_INPUT}", Input)
        input_widget.value = ""

        if not user_input:
            return

        self.log_to_history(user_input)

        # Маршрутизация на основе префикса
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
        """
        Записывает команду в файл history.txt.
        Игнорирует служебные команды и дубликаты.
        """
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
        """Обработчик команд управления (quit, write, history)."""
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
        """Обработчик сохранения команды в базу по тегу (#tag <cmd>)."""
        content = user_input[1:].strip()
        parts = content.split(maxsplit=1)
        
        if len(parts) == 2:
            tag, command_to_save = parts
            try:
                database.add_command(command_to_save, tag)
                self.add_block(InfoBlock(f"Saved: '{command_to_save}' with tag '{tag}'"))
            except Exception as e:
                self.add_block(InfoBlock(f"Database error: {e}"))
        else:
            self.add_block(InfoBlock("Invalid syntax. Use: #tag <command>"))

    def handle_query_command(self, user_input: str) -> None:
        """Обработчик поиска команд (?<tag>)."""
        tag_part = user_input[1:].strip()
        self.last_query_results = []
        
        try:
            if not tag_part:
                tags = database.get_all_tags()
                content = "Available tags:\n" + ("\n".join(f"  - {tag}" for tag in tags) if tags else "  (None found)")
                content += "\n\nType `? <tag>` to see commands."
                self.add_block(InfoBlock(content))
            else:
                commands = database.get_commands_by_tag(tag_part)
                content = f"Commands for tag '{tag_part}':\n"
                if not commands:
                    content += "  (None found)"
                else:
                    self.last_query_results = commands
                    content += "\n".join(f"  [{i}] {cmd}" for i, cmd in enumerate(commands, 1))
                    content += "\n\nUse `! <number>` to execute."
                self.add_block(InfoBlock(content))
        except Exception as e:
            self.add_block(InfoBlock(f"Database error: {e}"))

    def handle_bang_command(self, user_input: str) -> None:
        """Обработчик выполнения команды из списка поиска (!<number>)."""
        command_part = user_input[1:].strip()
        if command_part.isdigit():
            index = int(command_part) - 1
            if 0 <= index < len(self.last_query_results):
                input_widget = self.query_one(f"#{self.ID_INPUT}", Input)
                input_widget.value = self.last_query_results[index]
                input_widget.cursor_position = len(input_widget.value)
            else:
                self.add_block(InfoBlock("Error: Invalid number."))
        else:
            self.add_block(InfoBlock("Invalid syntax. Use: ! <number>"))

    def handle_pipe_command(self, user_input: str) -> None:
        """Обработчик пайпинга (конвейера) (|<command>)."""
        pipe_command = user_input[1:].strip()
        if not pipe_command:
            self.add_block(InfoBlock("Error: Pipe command cannot be empty."))
            return
            
        last_command_block = self.query(CommandBlock).last()
        if last_command_block is None:
            self.add_block(InfoBlock("Error: No previous command output to pipe from."))
            return
            
        input_for_pipe = last_command_block.raw_stdout
        self.handle_normal_command(pipe_command, stdin_data=input_for_pipe)
            
    def handle_normal_command(self, command: str, stdin_data: Optional[str] = None) -> None:
        """Оболочка для выполнения обычной команды с обновлением истории."""
        if command not in self.session_history:
            self.session_history.append(command)
        self.session_history_pos = len(self.session_history)
        self.run_command(command, stdin_data)

    def action_history_prev(self) -> None:
        """Навигация истории: предыдущая команда."""
        if not self.session_history: return
        input_widget = self.query_one(f"#{self.ID_INPUT}", Input)
        if self.session_history_pos > 0:
            self.session_history_pos -= 1
            input_widget.value = self.session_history[self.session_history_pos]
            input_widget.cursor_position = len(input_widget.value)

    def action_history_next(self) -> None:
        """Навигация истории: следующая команда."""
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

    def run_command(self, command: str, stdin_data: Optional[str] = None) -> None:
        """
        Выполняет shell команду через subprocess.
        
        Args:
            command: Строка команды для выполнения.
            stdin_data: Данные для передачи в стандартный ввод процесса.
        """
        timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
        cwd = os.getcwd()
        header = f"{timestamp} ({cwd}) $ {command}"
        
        raw_stdout, raw_stderr, return_code = "", "", 0
        if command:
            try:
                # shell=True позволяет использовать пайпы и алиасы, но требует доверия к вводу
                process = subprocess.run(
                    command, shell=True, capture_output=True, text=True,
                    encoding=self.ENCODING, errors='replace', input=stdin_data
                )
                raw_stdout = process.stdout.strip()
                raw_stderr = process.stderr.strip()
                return_code = process.returncode
            except Exception as e:
                raw_stderr = str(e)
                return_code = -1
        
        new_block = CommandBlock(
            header=header, 
            raw_stdout=raw_stdout, 
            raw_stderr=raw_stderr, 
            return_code=return_code
        )
        self.add_block(new_block)
        
if __name__ == "__main__":
    app = CommandRunner()
    app.run()
