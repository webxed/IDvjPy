# Authors: markovskiy.pavel, Gemini (Google)
import subprocess
import yaml
import datetime
import os
import pyperclip
import database
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, Static, Label
from textual.containers import VerticalScroll

class CommandBlock(Static):
    """A widget to display a single command and its output."""
    def __init__(self, text_content: str, **kwargs):
        super().__init__(text_content, **kwargs)
        self.text_content = text_content
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
    ]

    TITLE = "DevOps Terminal v1" # <--- Add this line
    

    TITLE = "DevOps Terminal v1" # <--- Add this line

    def __init__(self):
        super().__init__()
        self.session_history = []
        self.session_history_pos = 0
        self.last_query_results = []

    def on_mount(self) -> None:
        """Called when the app is mounted."""
        database.init_db()

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield Input(placeholder="Enter command, #tag <cmd>, or ? <tag>", id="command-input")
        yield VerticalScroll(id="results-container")
        yield Footer()

    def add_new_block(self, text_content: str):
        """Adds a new CommandBlock to the results container."""
        container = self.query_one("#results-container", VerticalScroll)
        new_block = CommandBlock(text_content)
        container.mount(new_block)
        # Focus the main input so the user can keep typing
        self.query_one("#command-input", Input).focus()
        container.scroll_end()

    def clear_subtitle(self) -> None:
        """Clears the app's subtitle."""
        self.sub_title = ""

    def action_copy_block(self) -> None:
        """Copies the content of the currently focused block."""
        focused = self.focused
        if isinstance(focused, CommandBlock):
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
        input_widget.value = "" # Clear input immediately

        if not user_input:
            return

        # --- Command Dispatch ---
        if user_input.startswith(':'):
            self.handle_colon_command(user_input)
        elif user_input.startswith('#'):
            self.handle_save_command(user_input)
        elif user_input.startswith('?'):
            self.handle_query_command(user_input)
        elif user_input.startswith('!'):
            self.handle_bang_command(user_input)
        else:
            self.handle_normal_command(user_input)

    def handle_colon_command(self, user_input: str):
        """Handles vim-like commands starting with ':'."""
        parts = user_input[1:].split()
        if not parts:
            return
        
        command = parts[0]
        if command == "q":
            self.exit()
        elif command == "w":
            if len(parts) > 1:
                filename = parts[1]
                try:
                    all_blocks = self.query(CommandBlock)
                    content_to_write = "\n\n---\n\n".join(block.text_content for block in all_blocks)
                    with open(filename, "w", encoding="utf-8") as f:
                        f.write(content_to_write)
                    self.add_new_block(f"Log content written to '{filename}'")
                except Exception as e:
                    self.add_new_block(f"Error writing to file: {e}")
            else:
                self.add_new_block("Error: Filename required for :w command.")
        else:
            self.add_new_block(f"Unknown command: '{command}'")

    def handle_save_command(self, user_input: str):
        """Handles the #tag <command> syntax."""
        content = user_input[1:].strip()
        parts = content.split(maxsplit=1)
        if len(parts) == 2:
            tag, command_to_save = parts
            database.add_command(command_to_save, tag)
            self.add_new_block(f"Saved: '{command_to_save}' with tag '{tag}'")
        else:
            self.add_new_block("Invalid syntax. Use: #tag <command>")

    def handle_query_command(self, user_input: str):
        """Handles the ? <tag> syntax."""
        tag_part = user_input[1:].strip()
        self.last_query_results = []

        if not tag_part: # Just '?'
            tags = database.get_all_tags()
            content = "Available tags:\n"
            if not tags:
                content += "  (None found)"
            else:
                content += "\n".join(f"  - {tag}" for tag in tags)
            content += "\n\nType `? <tag>` to see commands."
            self.add_new_block(content)
        else: # '? <tag>'
            tag = tag_part
            commands = database.get_commands_by_tag(tag)
            content = f"Commands for tag '{tag}':\n"
            if not commands:
                content += "  (None found)"
            else:
                self.last_query_results = commands
                content += "\n".join(f"  [{i}] {cmd}" for i, cmd in enumerate(commands, 1))
                content += "\n\nUse `! <number>` to execute."
            self.add_new_block(content)

    def handle_bang_command(self, user_input: str):
        """Handles the ! <number> syntax."""
        command_part = user_input[1:].strip()
        if command_part.isdigit():
            index = int(command_part) - 1
            if 0 <= index < len(self.last_query_results):
                command_to_run = self.last_query_results[index]
                self.handle_normal_command(command_to_run)
            else:
                self.add_new_block("Error: Invalid number.")
        else:
            self.add_new_block("Invalid syntax. Use: ! <number>")
            
    def handle_normal_command(self, command: str):
        """Handles a normal command execution."""
        if command not in self.session_history:
            self.session_history.append(command)
        self.session_history_pos = len(self.session_history)
        self.run_command(command)

    def action_history_prev(self) -> None:
        """Go to the previous command in session history."""
        if not self.session_history:
            return
        input_widget = self.query_one("#command-input", Input)
        if self.session_history_pos > 0:
            self.session_history_pos -= 1
            input_widget.value = self.session_history[self.session_history_pos]
            input_widget.cursor_position = len(input_widget.value)

    def action_history_next(self) -> None:
        """Go to the next command in session history."""
        if not self.session_history:
            return
        input_widget = self.query_one("#command-input", Input)
        if self.session_history_pos < len(self.session_history) - 1:
            self.session_history_pos += 1
            input_widget.value = self.session_history[self.session_history_pos]
            input_widget.cursor_position = len(input_widget.value)
        else:
            self.session_history_pos = len(self.session_history)
            input_widget.value = ""
            input_widget.cursor_position = 0

    def run_command(self, command: str) -> None:
        """Runs a command and displays the output in a new block."""
        timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
        cwd = os.getcwd()
        header = f"{timestamp} ({cwd}) $ {command}"
        
        output_content = ""
        if command:
            try:
                process = subprocess.run(
                    command, shell=True, capture_output=True, text=True,
                    encoding='utf-8', errors='replace'
                )
                stdout = process.stdout.strip()
                stderr = process.stderr.strip()
                output_content = (
                    f"CompletedProcess(returncode={process.returncode}, "
                    f"stdout='{stdout}', stderr='{stderr}')"
                )
            except Exception as e:
                output_content = f"Error: {e}"
        
        full_block_text = f"{header}\n{output_content}".rstrip() + "\n"
        self.add_new_block(full_block_text)
        
if __name__ == "__main__":
    app = CommandRunner()
    app.run()

