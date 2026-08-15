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
*   **Keyboard-driven Workflow** (v1.1.49):
    *   **Journal**: `PageUp` / `PageDown` scroll a page and activate the visible block (no jump to its start). Click a block to focus it (`terminal_mouse: true`).
    *   **Copy to Clipboard**: `F3` copies the focused block. `F5` opens the JSON viewer. `F2` toggles line-cursor mode.
    *   **Clear input**: `Ctrl+D`. Dark mode: `d`.
    *   **Real TTY**: `> htop` / `> vim file` suspends the TUI.

Current Russian docs: [`README.md`](README.md), [`COMPACT_SUMMARY.md`](COMPACT_SUMMARY.md). In-app: `:?`.

### Command Syntax

The application uses several command prefixes to unlock its features:

| Prefix    | Example               | Description                                                               |
|-----------|-----------------------|---------------------------------------------------------------------------|
| (none)    | `ls -l`               | Executes a standard shell command. Added to session history.              |
| `>`       | `> htop`              | Suspends the TUI and runs with a real TTY (`htop`, `vim`, `ssh`).         |
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
| `:h [X]`    | `:h` or `:h 5`        | Shows the last X lines of command history from `history.txt` as one multiline block. If X is not specified, it defaults to the value of `history_lines` in `settings.yml`. |
| `:json <file>` | `:json data.json` | Opens JSON file in tree viewer. Also works with F5 on a command block that output JSON. |
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

### JSON Viewer (v1.1.13+)

View JSON output in a navigable tree structure with lazy loading for large files:

```bash
# View JSON from command output
echo '{"users": [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]}'
# Focus the output block and press F5

# Open JSON files directly
:json k8sdesc.json

# Navigate the tree and press Enter to copy jq path
# The path is automatically wrapped in single quotes for bash:
# jq '.users[0].name'

# Use the copied path immediately
jq '.users[0].name' < data.json
```

**Features:**
- **Lazy Loading**: Large JSON files open instantly - only the first level is loaded, children load on-demand when you expand nodes
- **Smart Navigation**:
  - `↑↓` - Navigate between nodes
  - `←→` - Collapse/expand and move to parent/first child
  - `Space` - Toggle expand/collapse
  - `Enter` - Copy jq path and close viewer
  - `Escape` or `q` - Close viewer
- **Bracket Notation**: Keys with special characters (dots, slashes, quotes) are automatically escaped using proper bracket notation
- **Clipboard Integration**: JQ paths are wrapped in single quotes when copied, ready for immediate use in bash commands

**JQ Path Examples:**
```
.users[0].name                    - Simple access
.items[0].metadata.annotations["checksum/config-envs"]  - Special chars handled
```

**Performance:**
- Small files (< 1MB): Opens instantly
- Large files (> 3MB with 60k+ lines): Opens instantly with lazy loading

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
    
    This application supports bash aliases from `~/.bashrc`. Bodies with `$1` / `$2` / `$@` substitute arguments (`klogin cluster` → `tsh kube login cluster`); otherwise the rest of the line is appended.
    ```