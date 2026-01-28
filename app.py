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

# Check dependencies before importing
try:
    import yaml
    import datetime
    import os
    import pyperclip
    import database
    import threading
    import re
    from typing import List, Optional, Dict
    from textual.app import App, ComposeResult
    from textual.widgets import Header, Footer, Input, Static
    from textual.containers import VerticalScroll
except ImportError as e:
    print(f"Error: Missing dependency - {e}", file=sys.stderr)
    print("Please install required dependencies:", file=sys.stderr)
    print("  pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)

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
        Безопасно вызывается через call_from_thread.
        """
        self.raw_stdout = raw_stdout
        self.raw_stderr = raw_stderr
        self.return_code = return_code
        
        display_output = (
            f"CompletedProcess(returncode={self.return_code}, "
            f"stdout='{self.raw_stdout}', stderr='{self.raw_stderr}')"
        )
        final_content = f"{self.header}\n{display_output}".rstrip() + "\n"
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
        """
        Инициализация информационного блока.
        
        Args:
            text_content: Текст для отображения.
        """
        self.text_content = text_content
        super().__init__(text_content, **kwargs)
        self.can_focus = True

class CommandRunner(App):
    """Textual приложение для запуска shell команд с поддержкой переменных."""

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
    VERSION = "v1.0.8" # Variables Support

    # --- Конфигурация и константы ---
    FILE_SETTINGS = "settings.yml"
    FILE_HISTORY = "history.txt"
    FILE_DATABASE = "history.db"
    FILE_BASHRC = ".bashrc_term" # Файл для хранения локальных переменных
    FILE_BASH_ALIASES = ".bashrc" # Системный файл алиасов
    
    ID_INPUT = "command-input"
    ID_RESULTS_CONTAINER = "results-container"
    KEY_HISTORY_LINES = "history_lines"
    ENCODING = "utf-8"
    TIMER_DELAY = 2
    COMMAND_TIMEOUT = 10 
    
    MSG_COPIED = "Copied to clipboard!"
    MSG_NO_FOCUS = "No command block focused."
    MSG_TIMEOUT = "Process timed out (likely waiting for interactive input). Process killed."
    
    # Префиксы команд
    PREFIX_CMD = ":"
    PREFIX_TAG = "#"
    PREFIX_QUERY = "?"
    PREFIX_BANG = "!"
    PREFIX_PIPE = "|"
    PREFIX_VAR = "$" # Новый префикс для переменных
    
    CMD_QUIT = "q"
    CMD_WRITE = "w"
    CMD_HISTORY = "h"

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

    def on_mount(self) -> None:
        """
        Вызывается при старте приложения.
        Загружает настройки, базу данных и переменные окружения.
        """
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

        # 3. Загрузка переменных из файла .bashrc_term
        self.load_bashrc()

    def load_bashrc(self) -> None:
        """
        Читает файл .bashrc_term, парсит строки export VAR="VAL"
        и заполняет словарь self.local_env.
        Также обновляет os.environ для текущего процесса.
        """
        # Создаем файл, если его нет
        if not os.path.exists(self.FILE_BASHRC):
            with open(self.FILE_BASHRC, "w", encoding=self.ENCODING) as f:
                f.write("# Terminal-specific environment variables\n")
        
        try:
            with open(self.FILE_BASHRC, "r", encoding=self.ENCODING) as f:
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
        except Exception as e:
            # Если файл есть, но прочитать не удалось, сообщаем
            self.add_block(InfoBlock(f"Error loading {self.FILE_BASHRC}: {e}"))

    def on_ready(self) -> None:
        """Приветственное сообщение после загрузки UI."""
        self.add_block(InfoBlock(f"--- {self.TITLE} {self.VERSION} ---"))

    def compose(self) -> ComposeResult:
        """Построение UI."""
        yield Header()
        yield Input(placeholder="Enter command, #tag, ?*, $VAR=val, or :q/:w", id=self.ID_INPUT)
        yield VerticalScroll(id=self.ID_RESULTS_CONTAINER)
        yield Footer()

    def action_focus_input(self) -> None:
        """Переводит фокус в строку ввода."""
        self.query_one(f"#{self.ID_INPUT}", Input).focus()

    def add_block(self, block: Static) -> None:
        """
        Добавляет блок в UI, прокручивает вниз и возвращает фокус во ввод.
        """
        container = self.query_one(f"#{self.ID_RESULTS_CONTAINER}", VerticalScroll)
        container.mount(block)
        block.focus() # Кратковременно фокусируем, чтобы обновить active_pipe_source
        self.query_one(f"#{self.ID_INPUT}", Input).focus()
        container.scroll_end()

    def clear_subtitle(self) -> None:
        """Очищает подзаголовок (статус-бар)."""
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
        Главный диспетчер команд.
        Анализирует первый символ и перенаправляет выполнение.
        """
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
        elif user_input.startswith(self.PREFIX_VAR):
            self.handle_variable_assignment(user_input)
        else:
            self.handle_normal_command(user_input)

    def log_to_history(self, command: str) -> None:
        """Записывает команду в файл history.txt, исключая спецкоманды."""
        prefixes = (self.PREFIX_CMD, self.PREFIX_QUERY, self.PREFIX_BANG, self.PREFIX_TAG, self.PREFIX_PIPE, self.PREFIX_VAR)
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
        """Обработка команд управления (:q, :w, :h)."""
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

    def handle_variable_assignment(self, user_input: str) -> None:
        """
        Обработка создания/обновления переменных.
        Синтаксис: $VAR_NAME=VALUE.
        Записывает в .bashrc_term и обновляет self.local_env.
        """
        assignment = user_input[1:].strip()
        parts = assignment.split('=', 1)
        
        if len(parts) == 2:
            var_name, var_value = parts
            var_name = var_name.strip()
            var_value = var_value.strip()
            
            # Простая валидация имени переменной
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', var_name):
                self.add_block(InfoBlock(f"Error: Invalid variable name '{var_name}'."))
                return

            # Обновляем в памяти
            self.local_env[var_name] = var_value
            os.environ[var_name] = var_value
            
            # Перезаписываем файл
            try:
                lines = []
                updated = False
                if os.path.exists(self.FILE_BASHRC):
                    with open(self.FILE_BASHRC, "r", encoding=self.ENCODING) as f:
                        lines = f.readlines()
                
                with open(self.FILE_BASHRC, "w", encoding=self.ENCODING) as f:
                    for line in lines:
                        # Если переменная уже есть в файле, обновляем её строку
                        if line.startswith(f"export {var_name}="):
                            f.write(f'export {var_name}="{var_value}"\n')
                            updated = True
                        else:
                            f.write(line)
                    # Если переменной не было, добавляем в конец
                    if not updated:
                        f.write(f'export {var_name}="{var_value}"\n')
                
                self.add_block(InfoBlock(f"Variable ${var_name} set to '{var_value}'"))
            except Exception as e:
                self.add_block(InfoBlock(f"Error setting variable: {e}"))
        else:
            self.add_block(InfoBlock("Invalid syntax. Use: $VAR_NAME=VALUE"))

    def handle_save_command(self, user_input: str) -> None:
        """
        Обработка сохранения и удаления команд по тегу.
        #tag <cmd> - сохранить.
        #tag- - удалить все по тегу.
        #tag-ID - удалить конкретную команду.
        """
        content = user_input[1:].strip()
        
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
                    database.delete_command_by_id(self.db_file, cmd_id)
                    self.add_block(InfoBlock(f"Command with ID {cmd_id} marked as deleted."))
                else:
                    self.add_block(InfoBlock("Invalid delete syntax. Use #tag- or #tag-ID"))
            except Exception as e:
                self.add_block(InfoBlock(f"Database error: {e}"))
            return

        # Если это не удаление, значит сохранение
        parts = content.split(maxsplit=1)
        if len(parts) == 2:
            tag, command_to_save = parts
            try:
                database.add_command(self.db_file, command_to_save, tag)
                self.add_block(InfoBlock(f"Saved: '{command_to_save}' with tag '{tag}'"))
            except Exception as e:
                self.add_block(InfoBlock(f"Database error: {e}"))
        else:
            self.add_block(InfoBlock("Invalid syntax. Use: #tag <command>"))

    def handle_query_command(self, user_input: str) -> None:
        """
        Поиск команд в БД.
        ? - список тегов.
        ?* - все команды.
        ?tag - команды по тегу.
        """
        tag_part = user_input[1:].strip()
        self.last_query_results = {} 
        try:
            if not tag_part:
                tags = database.get_all_tags(self.db_file)
                content = "Available tags:\n" + ("\n".join(f"  - {tag}" for tag in tags) if tags else "  (None found)")
                content += "\n\nType `? <tag>` to see commands or `?*` to see all."
                self.add_block(InfoBlock(content))
            elif tag_part == '*':
                # Вывод всех команд с группировкой по тегам
                all_commands = database.get_all_commands_with_ids(self.db_file)
                content = "All commands by tag:\n"
                commands_by_tag = {}
                for row in all_commands:
                    tag = row['tag']
                    cmd_id = row['id']
                    cmd_text = row['command']
                    if tag not in commands_by_tag:
                        commands_by_tag[tag] = []
                    commands_by_tag[tag].append((cmd_id, cmd_text))
                    # Заполняем словарь для быстрого выполнения через !
                    self.last_query_results[cmd_id] = cmd_text
                
                if not commands_by_tag:
                    content += "  (None found)"
                else:
                    for tag, items in sorted(commands_by_tag.items()):
                        content += f"\n- {tag}:\n"
                        for cid, cmd in items:
                            content += f"  [{cid}] {cmd}\n"
                content += "\nUse `! <id>` to execute a command."
                self.add_block(InfoBlock(content))
            else:
                # Поиск по тегу
                commands = database.get_commands_by_tag(self.db_file, tag_part)
                content = f"Commands for tag '{tag_part}':\n"
                if not commands:
                    content += "  (None found)"
                else:
                    for row in commands:
                        self.last_query_results[row['id']] = row['command']
                    content += "\n".join(f"  [{row['id']}] {row['command']}" for row in commands)
                    content += "\n\nUse `! <id>` to execute."
                self.add_block(InfoBlock(content))
        except Exception as e:
            self.add_block(InfoBlock(f"Database error: {e}"))

    def handle_bang_command(self, user_input: str) -> None:
        """Выполнение команды по ID из последнего поиска (!<id>)."""
        command_part = user_input[1:].strip()
        if command_part.isdigit():
            cmd_id = int(command_part)
            if cmd_id in self.last_query_results:
                input_widget = self.query_one(f"#{self.ID_INPUT}", Input)
                input_widget.value = self.last_query_results[cmd_id]
                input_widget.cursor_position = len(input_widget.value)
            else:
                self.add_block(InfoBlock(f"Error: ID {cmd_id} not found in last query results."))
        else:
            self.add_block(InfoBlock("Invalid syntax. Use: ! <id>"))

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
        """Обертка для выполнения обычной команды с обновлением истории."""
        if command not in self.session_history:
            self.session_history.append(command)
        self.session_history_pos = len(self.session_history)
        self.run_command(command, stdin_data)

    def action_history_prev(self) -> None:
        """Навигация истории назад."""
        if not self.session_history: return
        input_widget = self.query_one(f"#{self.ID_INPUT}", Input)
        if self.session_history_pos > 0:
            self.session_history_pos -= 1
            input_widget.value = self.session_history[self.session_history_pos]
            input_widget.cursor_position = len(input_widget.value)

    def action_history_next(self) -> None:
        """Навигация истории вперед."""
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

    def _substitute_variables(self, command: str) -> str:
        """
        Заменяет переменные вида $VAR_NAME на значения.
        Приоритет: self.local_env > os.environ.
        """
        # Регулярное выражение ищет $NAME, где NAME - валидный идентификатор
        pattern = re.compile(r'\$([a-zA-Z_][a-zA-Z0-9_]*)\b')
        
        def replacer(match):
            var_name = match.group(1)
            if var_name in self.local_env:
                return self.local_env[var_name]
            if var_name in os.environ:
                return os.environ[var_name]
            # Если переменной нет нигде, оставляем $NAME как есть (чтобы shell сам вывел ошибку)
            return match.group(0)
        
        return pattern.sub(replacer, command)

    def _execute_in_thread(self, block: CommandBlock, command: str, stdin_data: Optional[str]) -> None:
        """
        Выполняет команду в отдельном потоке.
        """
        raw_stdout, raw_stderr, return_code = "", "", 0
        if command:
            try:
                # Для работы алиасов нужно использовать интерактивный режим
                # Подключаем ~/.bashrc и выполняем команду в bash -i -c
                home_dir = os.path.expanduser("~")
                alias_file = os.path.join(home_dir, self.FILE_BASH_ALIASES)

                # Собираем полную команду для выполнения в интерактивном bash
                # -i включает интерактивный режим (для алиасов)
                # -c выполняет команду из строки
                if os.path.exists(alias_file):
                    full_command = f"source {alias_file} && {command}"
                else:
                    full_command = command

                process = subprocess.run(
                    ["bash", "-i", "-c", full_command],
                    capture_output=True,
                    text=True,
                    encoding=self.ENCODING,
                    errors='replace',
                    input=stdin_data,
                    timeout=self.COMMAND_TIMEOUT
                )
                raw_stdout = process.stdout.strip()
                raw_stderr = process.stderr.strip()
                return_code = process.returncode
            except subprocess.TimeoutExpired:
                raw_stderr = f"{self.MSG_TIMEOUT}"
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
