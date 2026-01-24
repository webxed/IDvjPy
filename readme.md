```
  _____                      _____                    _ _           _ 
 |  __ \                    / ____|                  | (_)         | |
 | |  | | ___  ___ ___  ___| (___   ___  _ __   __ _ | |_ _ __   __| |
 | |  | |/ _ \/ __/ __|/ _ \\___ \ / _ \| '_ \ / _` || | | '_ \ / _` |
 | |__| |  __/\__ \__ \  __/____) | (_) | | | | (_| || | | | | | (_| |
 |_____/ \___||___/___/\___|_____/ \___/|_| |_|\__, ||_|_|_| |_|\__,_|
                                               __/ |                
                                              |___/                 
v1.0
```

## DevOps Terminal v1

This is a custom terminal-like application built with Python and the Textual TUI framework. It provides a simple, keyboard-driven interface for running shell commands and managing a persistent, tagged history of your favorite commands, with a focus on DevOps workflows.

### Core Features

*   **Dual-pane Interface**: A familiar layout with a command input at the top and a scrollable output area at the bottom.
*   **Block-based Output**: Each command and its result are contained in a separate, focusable block.
*   **Persistent Command History**: Save your favorite or most-used commands to an SQLite database with custom tags.
*   **Session History**: Cycle through commands run in the current session using the `Up` and `Down` arrow keys.
*   **Vim-like Controls**:
    *   `:q` to quit the application.
    *   `:w <filename>` to write the entire output of the current session to a file.
*   **Keyboard-driven Workflow**:
    *   **Navigate Blocks**: Use `PageUp` and `PageDown` to select different command blocks.
    *   **Copy to Clipboard**: Press `F5` to copy the entire content of the currently focused block.
    *   **Dark Mode**: Press `Ctrl+D` to toggle dark mode.

### Command Syntax

The application uses several command prefixes to unlock its features:

| Prefix    | Example               | Description                                                               |
|-----------|-----------------------|---------------------------------------------------------------------------|
| (none)    | `ls -l`               | Executes a standard shell command. Added to session history.              |
| `#`       | `#git git status`     | Saves the command (`git status`) to the persistent history with a tag (`git`). |
| `?`       | `?`                   | Shows a list of all unique tags saved in the history database.            |
| `? <tag>` | `? git`               | Shows a list of all commands saved with the specified tag.                |
| `!`       | `! 1`                 | Executes the command corresponding to the number from the last `?` query.    |
| `:`       | `:q` or `:w log.txt`  | Executes an application command (quit or write to file).                  |
