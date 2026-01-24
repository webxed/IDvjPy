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
    """A widget to display a single command and its output."""
    def __init__(self, header: str, raw_stdout: str, raw_stderr: str, return_code: int, **kwargs):
        self.header = header
        self.raw_stdout = raw_stdout
        self.raw_stderr = raw_stderr
        self.return_code = return_code
        
        display_output = (
            f"CompletedProcess(returncode={self.return_code}, "
            f"stdout='{self.raw_stdout}', stderr='{self.raw_stderr}')"
        )
        self.text_content = f"{self.header}\n{display_output}".rstrip() + "\n"
        
        super().__init__(self.text_content, **kwargs)
        self.can_focus = True

class InfoBlock(Static):
    """A widget to display informational text, not from a command."""
    def __init__(self, text_content: str, **kwargs):
        self.text_content = text_content
        super().__init__(text_content, **kwargs)
        self.can_focus = True

class CommandRunner(App):
    """A Textual app to run shell commands."""

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

    def __init__(self):
        super().__init__()
        self.session_history = []
        self.session_history_pos = 0
        self.last_query_results = []

    def on_mount(self) -> None:
        """Called when the app is mounted."""
        database.init_db()

    def on_ready(self) -> None:
        """Called when the app is ready."""
        self.add_block(InfoBlock(f"--- {self.TITLE} v1.0.1 ---"))

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield Input(placeholder="Enter command, #tag <cmd>, ? <tag>, or :q/:w", id="command-input")
        yield VerticalScroll(id="results-container")
        yield Footer()

    def action_focus_input(self) -> None:
        """Focus the main command input."""
        self.query_one("#command-input", Input).focus()

    def add_block(self, block: Static):
        """Adds a new block widget to the results container."""
        container = self.query_one("#results-container", VerticalScroll)
        container.mount(block)
        block.focus()
        self.query_one("#command-input", Input).focus()
        container.scroll_end()

    def clear_subtitle(self) -> None:
        """Clears the app's subtitle."""
        self.sub_title = ""

    def action_copy_block(self) -> None:
        """Copies the content of the currently focused block."""
        focused = self.focused
        if isinstance(focused, (CommandBlock, InfoBlock)):
            pyperclip.copy(focused.text_content)
            self.sub_title = "Copied to clipboard!"
            self.set_timer(2, self.clear_subtitle)
        else:
            self.sub_title = "No command block focused."
            self.set_timer(2, self.clear_subtitle)

    def on_input_submitted(self, message: Input.Submitted) -> None:
        """Called when the user presses Enter in the Input widget."""
        user_input = message.value.strip()
        input_widget = self.query_one("#command-input", Input)
        input_widget.value = ""

        if not user_input:
            return

        if user_input.startswith(':'):
            self.handle_colon_command(user_input)
        elif user_input.startswith('#'):
            self.handle_save_command(user_input)
        elif user_input.startswith('?'):
            self.handle_query_command(user_input)
        elif user_input.startswith('!'):
            self.handle_bang_command(user_input)
        elif user_input.startswith('|'):
            self.handle_pipe_command(user_input)
        else:
            self.handle_normal_command(user_input)

    def handle_colon_command(self, user_input: str):
        parts = user_input[1:].split()
        if not parts: return
        
        command = parts[0]
        if command == "q":
            self.exit()
        elif command == "w":
            if len(parts) > 1:
                filename = parts[1]
                try:
                    # Query for the specific block types using a CSS selector string
                    all_blocks = self.query("CommandBlock, InfoBlock")
                    content_to_write = "\n\n---\n\n".join(block.text_content for block in all_blocks)
                    with open(filename, "a", encoding="utf-8") as f: # Changed 'w' to 'a'
                        f.write(content_to_write)
                    self.add_block(InfoBlock(f"Log content written to '{filename}'"))
                except Exception as e:
                    self.add_block(InfoBlock(f"Error writing to file: {e}"))
            else:
                self.add_block(InfoBlock("Error: Filename required for :w command."))
        else:
            self.add_block(InfoBlock(f"Unknown command: '{command}'"))

    def handle_save_command(self, user_input: str):
        content = user_input[1:].strip()
        parts = content.split(maxsplit=1)
        if len(parts) == 2:
            tag, command_to_save = parts
            database.add_command(command_to_save, tag)
            self.add_block(InfoBlock(f"Saved: '{command_to_save}' with tag '{tag}'"))
        else:
            self.add_block(InfoBlock("Invalid syntax. Use: #tag <command>"))

    def handle_query_command(self, user_input: str):
        tag_part = user_input[1:].strip()
        self.last_query_results = []
        if not tag_part:
            tags = database.get_all_tags()
            content = "Available tags:\n" + ("\n".join(f"  - {tag}" for tag in tags) if tags else "  (None found)")
            content += "\n\nType `? <tag>` to see commands."
            self.add_block(InfoBlock(content))
        else:
            tag = tag_part
            commands = database.get_commands_by_tag(tag)
            content = f"Commands for tag '{tag}':\n"
            if not commands:
                content += "  (None found)"
            else:
                self.last_query_results = commands
                content += "\n".join(f"  [{i}] {cmd}" for i, cmd in enumerate(commands, 1))
                content += "\n\nUse `! <number>` to execute."
            self.add_block(InfoBlock(content))

    def handle_bang_command(self, user_input: str):
        command_part = user_input[1:].strip()
        if command_part.isdigit():
            index = int(command_part) - 1
            if 0 <= index < len(self.last_query_results):
                self.handle_normal_command(self.last_query_results[index])
            else:
                self.add_block(InfoBlock("Error: Invalid number."))
        else:
            self.add_block(InfoBlock("Invalid syntax. Use: ! <number>"))

    def handle_pipe_command(self, user_input: str):
        pipe_command = user_input[1:].strip()
        if not pipe_command:
            self.add_block(InfoBlock("Error: Pipe command cannot be empty."))
            return
            
        last_command_block = self.query(CommandBlock).last()
        if last_command_block is None:
            self.add_block(InfoBlock("Error: No previous command output to pipe from."))
            return
            
        input_for_pipe = last_command_block.raw_stdout
        self.run_command(pipe_command, stdin_data=input_for_pipe)
            
    def handle_normal_command(self, command: str):
        if command not in self.session_history:
            self.session_history.append(command)
        self.session_history_pos = len(self.session_history)
        self.run_command(command)

    def action_history_prev(self) -> None:
        if not self.session_history: return
        input_widget = self.query_one("#command-input", Input)
        if self.session_history_pos > 0:
            self.session_history_pos -= 1
            input_widget.value = self.session_history[self.session_history_pos]
            input_widget.cursor_position = len(input_widget.value)

    def action_history_next(self) -> None:
        if not self.session_history: return
        input_widget = self.query_one("#command-input", Input)
        if self.session_history_pos < len(self.session_history) - 1:
            self.session_history_pos += 1
            input_widget.value = self.session_history[self.session_history_pos]
            input_widget.cursor_position = len(input_widget.value)
        else:
            self.session_history_pos = len(self.session_history)
            input_widget.value = ""
            input_widget.cursor_position = 0

    def run_command(self, command: str, stdin_data: str = None) -> None:
        """Runs a command and displays the output in a new block."""
        timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
        cwd = os.getcwd()
        header = f"{timestamp} ({cwd}) $ {command}"
        
        raw_stdout, raw_stderr, return_code = "", "", 0
        if command:
            try:
                process = subprocess.run(
                    command, shell=True, capture_output=True, text=True,
                    encoding='utf-8', errors='replace', input=stdin_data
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