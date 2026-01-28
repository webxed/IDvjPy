# Authors: markovskiy.pavel, Gemini (Google)
import subprocess
import yaml
import datetime
import os
import pyperclip
import database
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
        # Сохраняем полный текст для копирования и отображения
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

    # Константы для путей к файлам
    FILE_SETTINGS = "settings.yml"
    FILE_HISTORY = "history.txt"
    
    # Константы для ID виджетов
    ID_INPUT = "command-input"
    ID_RESULTS_CONTAINER = "results-container"
    
    # Ключи настроек
    KEY_HISTORY_LINES = "history_lines"
    
    # Общие константы
    ENCODING = "utf-8"
    
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
        self.session_history = []       # История команд, введенных в текущей сессии
        self.session_history_pos = 0    # Текущая позиция в истории сессии
        self.last_query_results = []    # Результаты последнего поиска по тегам
        self.history_lines = 20         # Количество строк истории для вывода по умолчанию

    def on_mount(self) -> None:
        """
        Вызывается при монтировании приложения.
        Инициализирует базу данных и загружает настройки из файла YAML.
        """
        database.init_db()
        try:
            with open(self.FILE_SETTINGS, "r", encoding=self.ENCODING) as f:
                settings = yaml.safe_load(f)
                self.history_lines = settings.get(self.KEY_HISTORY_LINES, 20)
        except (FileNotFoundError, KeyError):
            pass # Если файл настроек не найден или ключ отсутствует, используем значения по умолчанию

    def on_ready(self) -> None:
        """Вызывается когда приложение готово к работе. Выводит приветственное сообщение."""
        self.add_block(InfoBlock(f"--- {self.TITLE} {self.VERSION} ---"))

    def compose(self) -> ComposeResult:
        """
        Создает дочерние виджеты приложения (UI).
        Определяет структуру: заголовок, поле ввода, контейнер для вывода, подвал.
        """
        yield Header()
        yield Input(placeholder="Enter command, #tag <cmd>, ? <tag>, or :q/:w", id=self.ID_INPUT)
        yield VerticalScroll(id=self.ID_RESULTS_CONTAINER)
        yield Footer()

    def action_focus_input(self) -> None:
        """Устанавливает фокус на поле ввода команд."""
        self.query_one(f"#{self.ID_INPUT}", Input).focus()

    def add_block(self, block: Static):
        """
        Добавляет новый блок (CommandBlock или InfoBlock) в контейнер результатов.
        Также автоматически прокручивает список вниз и возвращает фокус во ввод.
        """
        container = self.query_one(f"#{self.ID_RESULTS_CONTAINER}", VerticalScroll)
        container.mount(block)
        # Кратковременно фокусируем блок (например, чтобы он появился в области видимости или для навигации)
        block.focus()
        # Сразу возвращаем фокус в input, чтобы пользователь мог продолжить ввод
        self.query_one(f"#{self.ID_INPUT}", Input).focus()
        container.scroll_end()

    def clear_subtitle(self) -> None:
        """Очищает подзаголовок приложения (используется для временных сообщений)."""
        self.sub_title = ""

    def action_copy_block(self) -> None:
        """
        Копирует содержимое текущего сфокусированного блока в буфер обмена.
        Показывает временное уведомление в подзаголовке.
        """
        focused = self.focused
        if isinstance(focused, (CommandBlock, InfoBlock)):
            pyperclip.copy(focused.text_content)
            self.sub_title = "Copied to clipboard!"
            self.set_timer(2, self.clear_subtitle)
        else:
            self.sub_title = "No command block focused."
            self.set_timer(2, self.clear_subtitle)

    def on_input_submitted(self, message: Input.Submitted) -> None:
        """
        Главный обработчик ввода. Вызывается при нажатии Enter.
        Анализирует префикс команды и перенаправляет выполнение соответствующему обработчику.
        """
        user_input = message.value.strip()
        input_widget = self.query_one(f"#{self.ID_INPUT}", Input)
        input_widget.value = ""

        if not user_input:
            return

        # Логируем команду в файл истории (если это не спецкоманда)
        self.log_to_history(user_input)

        # Роутинг команд на основе префикса
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

    def log_to_history(self, command: str):
        """
        Добавляет команду в файл history.txt.
        Пропускает команды, начинающиеся со спецсимволов, и дубликаты последней команды.
        """
        if command.startswith((self.PREFIX_CMD, self.PREFIX_QUERY, self.PREFIX_BANG, self.PREFIX_TAG, self.PREFIX_PIPE)):
            return

        last_command = None
        try:
            with open(self.FILE_HISTORY, "r", encoding=self.ENCODING) as f:
                lines = f.readlines()
                if lines:
                    last_command = lines[-1].strip()
        except FileNotFoundError:
            pass

        # Записываем только если команда отличается от последней записанной
        if command != last_command:
            with open(self.FILE_HISTORY, "a", encoding=self.ENCODING) as f:
                f.write(f"{command}\n")

    def handle_colon_command(self, user_input: str):
        """
        Обрабатывает метакоманды (начинаются с :).
        :q - выход
        :w <filename> - запись логов в файл
        :h [n] - показать историю из файла (последние n строк)
        """
        parts = user_input[1:].split()
        if not parts: return
        
        command = parts[0]
        if command == self.CMD_QUIT:
            self.exit()
        elif command == self.CMD_WRITE:
            if len(parts) > 1:
                filename = parts[1]
                try:
                    # Собираем текст из всех блоков в контейнере
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
                # Определяем количество строк: аргумент или значение из настроек
                num_lines = int(parts[1]) if len(parts) > 1 else self.history_lines
                with open(self.FILE_HISTORY, "r", encoding=self.ENCODING) as f:
                    lines = f.readlines()
                # Выводим последние n строк по отдельности
                for line in lines[-num_lines:]:
                    self.add_block(InfoBlock(line.strip()))
            except FileNotFoundError:
                self.add_block(InfoBlock(f"{self.FILE_HISTORY} not found."))
            except Exception as e:
                self.add_block(InfoBlock(f"Error reading history: {e}"))
        else:
            self.add_block(InfoBlock(f"Unknown command: '{command}'"))

    def handle_save_command(self, user_input: str):
        """
        Обрабатывает сохранение команды по тегу (синтаксис: #tag <command>).
        Сохраняет в базу данных.
        """
        content = user_input[1:].strip()
        parts = content.split(maxsplit=1)
        if len(parts) == 2:
            tag, command_to_save = parts
            database.add_command(command_to_save, tag)
            self.add_block(InfoBlock(f"Saved: '{command_to_save}' with tag '{tag}'"))
        else:
            self.add_block(InfoBlock("Invalid syntax. Use: #tag <command>"))

    def handle_query_command(self, user_input: str):
        """
        Обрабатывает поиск команд по тегу (синтаксис: ?<tag>).
        Без аргументов выводит список всех тегов.
        """
        tag_part = user_input[1:].strip()
        self.last_query_results = [] # Сбрасываем результаты предыдущего поиска
        
        if not tag_part:
            # Если тег не указан, выводим список доступных тегов
            tags = database.get_all_tags()
            content = "Available tags:\n" + ("\n".join(f"  - {tag}" for tag in tags) if tags else "  (None found)")
            content += "\n\nType `? <tag>` to see commands."
            self.add_block(InfoBlock(content))
        else:
            # Ищем команды по тегу
            tag = tag_part
            commands = database.get_commands_by_tag(tag)
            content = f"Commands for tag '{tag}':\n"
            if not commands:
                content += "  (None found)"
            else:
                self.last_query_results = commands # Сохраняем для выполнения через !
                content += "\n".join(f"  [{i}] {cmd}" for i, cmd in enumerate(commands, 1))
                content += "\n\nUse `! <number>` to execute."
            self.add_block(InfoBlock(content))

    def handle_bang_command(self, user_input: str):
        """
        Обрабатывает выполнение команды из списка результатов поиска (синтаксис: !<number>).
        Вставляет команду в поле ввода.
        """
        command_part = user_input[1:].strip()
        if command_part.isdigit():
            index = int(command_part) - 1 # Преобразуем в 0-based индекс
            if 0 <= index < len(self.last_query_results):
                input_widget = self.query_one(f"#{self.ID_INPUT}", Input)
                input_widget.value = self.last_query_results[index]
                input_widget.cursor_position = len(input_widget.value)
            else:
                self.add_block(InfoBlock("Error: Invalid number."))
        else:
            self.add_block(InfoBlock("Invalid syntax. Use: ! <number>"))

    def handle_pipe_command(self, user_input: str):
        """
        Обрабатывает передачу вывода последней команды в новую команду (синтаксис: |<command>).
        Stdout последнего CommandBlock передается как Stdin новой команды.
        """
        pipe_command = user_input[1:].strip()
        if not pipe_command:
            self.add_block(InfoBlock("Error: Pipe command cannot be empty."))
            return
            
        # Ищем последний блок с результатом команды
        last_command_block = self.query(CommandBlock).last()
        if last_command_block is None:
            self.add_block(InfoBlock("Error: No previous command output to pipe from."))
            return
            
        input_for_pipe = last_command_block.raw_stdout
        # Передаем данные в stdin новой команды и добавляем её в историю сессии
        self.handle_normal_command(pipe_command, stdin_data=input_for_pipe)
            
    def handle_normal_command(self, command: str, stdin_data: str = None):
        """
        Обычный запуск команды.
        Обновляет историю сессии и вызывает run_command.
        """
        if command not in self.session_history:
            self.session_history.append(command)
        self.session_history_pos = len(self.session_history)
        self.run_command(command, stdin_data)

    def action_history_prev(self) -> None:
        """
        Навигация по истории сессии вверх.
        Заменяет содержимое поля ввода на предыдущую команду.
        """
        if not self.session_history: return
        input_widget = self.query_one(f"#{self.ID_INPUT}", Input)
        if self.session_history_pos > 0:
            self.session_history_pos -= 1
            input_widget.value = self.session_history[self.session_history_pos]
            input_widget.cursor_position = len(input_widget.value)

    def action_history_next(self) -> None:
        """
        Навигация по истории сессии вниз.
        Заменяет содержимое поля ввода на следующую команду или очищает его.
        """
        if not self.session_history: return
        input_widget = self.query_one(f"#{self.ID_INPUT}", Input)
        if self.session_history_pos < len(self.session_history) - 1:
            self.session_history_pos += 1
            input_widget.value = self.session_history[self.session_history_pos]
            input_widget.cursor_position = len(input_widget.value)
        else:
            # Если мы в конце истории, сбрасываем позицию и очищаем поле
            self.session_history_pos = len(self.session_history)
            input_widget.value = ""
            input_widget.cursor_position = 0

    def run_command(self, command: str, stdin_data: str = None) -> None:
        """
        Непосредственный запуск shell команды через subprocess.
        Формирует заголовок, запускает процесс, обрабатывает вывод и создает CommandBlock.
        """
        timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
        cwd = os.getcwd()
        header = f"{timestamp} ({cwd}) $ {command}"
        
        raw_stdout, raw_stderr, return_code = "", "", 0
        if command:
            try:
                # Запуск процесса. capture_output=True перехватывает stdout/stderr.
                # text=True возвращает строки вместо bytes.
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
        
        # Создаем и отображаем блок с результатом
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