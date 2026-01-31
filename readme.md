```
```
 ___ ____  _      _  ____  _    _   ______                    _
|_ _|  _ \/ \    / |/ __ \| |  | | |  ____|                  | |
 | || | |/ _ \  / /| |  | | |  | | | |__ __ _ _ __  _ __   ___| |
 | || | |/ ___ \/ / | |  | | |  | | |  __/ _` | '_ \| '_ \ / _ \ |
 | || |_|/ /   \/ /  | |__| | |__| | | | | (_| | |_) | |_) |  __/ |
|___|____/_/   \_/  \___\_\\____/  |_|  \__,_| .__/| .__/ \___|_|
   (idi v jopy terminal)                     | |   | |
                                             |_|   | |
```

## IDvjPy_term

A custom terminal-like application for those who are tired of the old ways. Built with Python and the Textual TUI framework, it provides a simple, keyboard-driven interface for running shell commands and managing a persistent, tagged history of your favorite commands.

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
| `#tag-`   | `#git-`               | Marks all commands with the specified tag as deleted.                     |
| `#tag-ID` | `#git-1`              | Marks a specific command by local ID as deleted.                           |
| `#tag+ID`  | `#git+1`              | Edit a specific command by local ID (loads into input for editing). Add text after ID to update directly: `#git+1 new command` |
| `#tag+`   | `#git+`               | Edit the last command in the tag (highest local ID).                     |
| `?`       | `?`                   | Shows a list of all unique tags saved in the history database.            |
| `? <tag>` | `? git`               | Shows a list of all commands saved with the specified tag.                |
| `??`      | `??`                  | Shows all commands from the database, grouped by tag.                     |
| `!`       | `! 1`                 | Executes the command corresponding to the number from the last `?` query.    |
| `:`       | `:q` or `:w log.txt`  | Executes an application command (quit or write to file).                  |
| `:h [X]`    | `:h` or `:h 5`        | Shows the last X lines of command history from `history.txt`. If X is not specified, it defaults to the value of `history_lines` in `settings.yml`. |
| `|`       | `| jq .`              | Pipes the `stdout` of the most recent command block as `stdin` to the specified command. |
| `$`       | `$MY_VAR=hello`      | Creates or updates an environment variable in `.bashrc_term` and the current session. |

### Tag Execution with Variables (v1.1.10+)

You can append additional text, options, or variables after tag references:

```bash
# Save a base command
#deploy nginx -t

# Execute with additional parameters
!deploy[1] --config=/etc/nginx/test.conf    # → nginx -t --config=/etc/nginx/test.conf

# Using variables
$CONF_FILE=/etc/nginx/prod.conf
!deploy[1] --config=$CONF_FILE              # → nginx -t --config=/etc/nginx/prod.conf

# Works with global IDs too
!5 --verbose                                 # Loads command ID 5 and appends --verbose

# Multiple arguments
!deploy[2] && echo "Deployment completed"
```

### Command Preview with Reference Resolution (v1.1.12+)

Preview all intermediate resolution steps when commands contain nested references:

```bash
# If commands are chained:
# deploy[3] = "!deploy[2] && echo 'step 3'"
# deploy[2] = "!deploy[1] && echo 'step 2'"
# deploy[1] = "systemctl restart nginx"

?deploy[3]
# Output:
# Step 1 (Original):
# !deploy[2] && echo 'step 3'
#
# Step 2:
# !deploy[1] && echo 'step 2' && echo 'step 3'
#
# Step 3 (Final):
# systemctl restart nginx && echo 'step 2' && echo 'step 3'
```

This shows the complete transformation chain when executing commands with nested `!tag[tid]`, `!ID`, and `!!` references.

### Setup on Linux/Debian

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd Idivjopy
    ```

2.  **Run the setup script:**
    ```bash
    ./setup.sh
    ```

3.  **Run the application:**
    ```bash
        python app.py
        ```
    
    ### Bash Alias Support
    
    This application supports bash aliases. It will automatically source the `.bashrc` file in your home directory if it exists. This feature is intended for Linux/Debian environments.
    ```