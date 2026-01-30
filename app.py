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
    import pyperclip
    import database_v2 as database
    import threading
    import re
    import time
    import portalocker
    from typing import List, Optional, Dict
    from command_parser_v2 import CommandParser
    from textual.app import App, ComposeResult
    from textual.widgets import Header, Footer, Input, Static
    from textual.containers import VerticalScroll, Vertical
except ImportError as e:
    print(f"Error: Missing dependency - {e}", file=sys.stderr)
    print("Please install required dependencies:", file=sys.stderr)
    print("  pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)


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
        self.text_content = f"{self.header}\n{display_output}".rstrip() + "\n\n"
        
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
        final_content = f"{self.header}\n{display_output}".rstrip() + "\n\n"
        self.update(final_content)

    def on_focus(self) -> None:
        """
        Событие получения фокуса.
        Запоминает этот блок как активный источник для пайпинга.
        """
        if hasattr(self.app, 'active_pipe_source'):
            self.app.active_pipe_source = self

class ClickableCommand(Static):
    """Кликабельный виджет для отображения команды с возможностью клика."""

    def __init__(self, command_ref: str, tag: str, tid: int, **kwargs):
        """
        Инициализация кликабельной команды.

        Args:
            command_ref: Ссылка на команду (например, "!deploy[2]")
            tag: Имя тега
            tid: Локальный ID
        """
        self.command_ref = command_ref
        self.tag = tag
        self.tid = tid
        super().__init__(command_ref, **kwargs)

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
    VERSION = "v1.1.8" # Cross-platform file locking with portalocker

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
    MSG_TIMEOUT = "Process timed out (likely waiting for interactive input). Process killed."
    
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
        yield Input(placeholder="Enter command, #tag, #tag+, ??, !!, $VAR=val, or :q/:w", id=self.ID_INPUT)
        yield VerticalScroll(id=self.ID_RESULTS_CONTAINER)
        yield Footer()

    def action_focus_input(self) -> None:
        """Переводит фокус в строку ввода."""
        self.query_one(f"#{self.ID_INPUT}", Input).focus()

    # Словарь для хранения команд, доступных для клика
    _clickable_commands: Dict[str, str] = {}

    def action_insert_command(self, command_key: str) -> None:
        """
        Вставляет команду в строку ввода по ключу.

        Args:
            command_key: Ключ команды в словаре _clickable_commands
        """
        command = self._clickable_commands.get(command_key, "")
        if command:
            input_widget = self.query_one(f"#{self.ID_INPUT}", Input)
            input_widget.value = command
            input_widget.cursor_position = len(command)
            input_widget.focus()

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
        import re
        has_command_refs = bool(re.search(r'(?<!!)!([a-zA-Z_0-9]+)\[(\d+)\]|(?<!!)!(\d+)', user_input))

        # v1.1.9+: Проверяем, содержит ли команда shell-операторы
        has_shell_operators = bool(re.search(r'[&|;]', user_input))

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
                import re
                not_found = []
                # Ищем все !tag[tid] ссылки
                for match in re.finditer(r'!([a-zA-Z_0-9]+)\[(\d+)\]', user_input):
                    tag, tid = match.group(1), int(match.group(2))
                    result = database.get_command_by_tid(self.db_file, tag, tid)
                    if not result:
                        not_found.append(f"{tag}[{tid}]")
                # Ищем все !ID ссылки (которые не !! в начале)
                for match in re.finditer(r'(?<!!)!(\d+)', user_input):
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
        elif command == self.CMD_CLEAR:
            self.clear_all_blocks()
        else:
            self.add_block(InfoBlock(f"Unknown command: '{command}'"))

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
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', var_name):
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
        """
        tag_part = user_input[1:].strip()
        self.last_query_results = {}
        # Очищаем словарь кликабельных команд перед новым запросом
        self._clickable_commands = {}

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
                content += "\n💡 Tip: Click on [bold]tag[tid][/bold] commands to insert them into input."
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
                            # tag[tid] - кликабельная ссылка
                            cmd_ref = f"!{tag}[{tid}]"
                            cmd_key = f"{tag}_{tid}"
                            # Сохраняем команду в словаре для клика
                            self._clickable_commands[cmd_key] = cmd_ref
                            if cmd_comment:
                                content += f"  [dim]<{gid}>[/] [link=@action_insert_command({cmd_key})]{tag}[{tid}][/link]  {cmd}  # {cmd_comment}\n"
                            else:
                                content += f"  [dim]<{gid}>[/] [link=@action_insert_command({cmd_key})]{tag}[{tid}][/link]  {cmd}\n"
                content += "\nUse `!<tag>[<tid>]` or `!<<id>>` to execute a command."
                content += "\n💡 Click on [bold]tag[tid][/bold] to insert into input."
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
                        cmd_ref = f"!{tag_part}[{row['tid']}]"
                        cmd_key = f"{tag_part}_{row['tid']}"
                        # Сохраняем команду в словаре для клика
                        self._clickable_commands[cmd_key] = cmd_ref
                        comment_part = f"  # {row['comment']}" if 'comment' in row.keys() and row['comment'] else ""
                        lines.append(f"  [dim]<{row['id']}>[/] [link=@action_insert_command({cmd_key})]{tag_part}[{row['tid']}][/link]  {row['command']}{comment_part}")
                    content += "\n".join(lines)
                    content += "\n\nUse `!{}[<tid>]` or `!<<id>>` to execute.".format(tag_part)
                    content += "\n💡 Click on [bold]{}[tid][/bold] to insert into input.".format(tag_part)
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
        """
        command_part = user_input[1:].strip()

        command_text = None

        # Проверяем новый формат: !tag[tid]
        if '[' in command_part and command_part.endswith(']'):
            try:
                # Парсим tag[tid]
                tag, tid_part = command_part.split('[')
                tid = int(tid_part[:-1])  # Убираем ']'

                # Получаем команду из БД
                result = database.get_command_by_tid(self.db_file, tag, tid)
                if result:
                    command_text = result['command']
                else:
                    self.add_block(InfoBlock(f"Error: Command {tag}[{tid}] not found."))
                    return
            except (ValueError, IndexError):
                self.add_block(InfoBlock("Invalid syntax. Use: !<tag>[<tid>] or !<id>"))
                return
        # Проверяем старый формат: !ID (цифра)
        elif command_part.isdigit():
            cmd_id = int(command_part)
            result = database.get_command_by_global_id(self.db_file, cmd_id)
            if result:
                command_text = result['command']
            else:
                self.add_block(InfoBlock(f"Error: Global ID {cmd_id} not found."))
                return
        else:
            self.add_block(InfoBlock("Invalid syntax. Use: !<tag>[<tid>] or !<id>"))
            return

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
        """
        raw_stdout, raw_stderr, return_code = "", "", 0
        if command:
            try:
                # Алиасы уже раскрыты в run_command через _expand_aliases
                # Выполняем команду в bash
                process = subprocess.run(
                    command, shell=True, executable="/bin/bash",
                    capture_output=True, text=True,
                    encoding=self.ENCODING, errors='replace',
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
