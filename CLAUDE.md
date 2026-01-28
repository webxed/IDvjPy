# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

IDvjPy_term is a Python terminal application (TUI) built with the Textual framework. It provides a keyboard-driven interface for running shell commands with persistent, tagged command history stored in SQLite.

## Running the Application

```bash
python app.py
```

## Setup

```bash
./setup.sh
```

The setup script handles dependencies and configuration.

## Architecture

### Single-File Application Structure

The application is primarily contained in `app.py` (~1000+ lines) with three main classes:

- **`CommandRunner`** (App): Main Textual application, handles command routing and UI orchestration
- **`CommandBlock`** (Static): Widget displaying individual command execution results
- **`InfoBlock`** (Static): Widget for informational messages

### Supporting Modules

- **`database.py`**: SQLite operations for tagged command history
- **`app.css`**: Textual styling for the TUI
- **`settings.yml`**: Configuration (max buffer lines, history display lines, database file name)
- **`.bashrc_term`**: Environment variables persisted by the `$` prefix command

### Command Prefix System

The application parses command prefixes to route to different behaviors:

| Prefix | Purpose |
|--------|---------|
| (none) | Execute shell command via subprocess, add to session history |
| `#` | Save command to database with tag |
| `#tag-` or `#tag-ID` | Mark database commands as deleted |
| `?` | Query database (all tags, specific tag, or all grouped) |
| `! N` | Execute command by ID from last query |
| `:` | Application commands (`:q` quit, `:w file` write, `:h [N]` shell history) |
| `\| cmd` | Pipe stdout from focused block to another command |
| `$ VAR=val` | Set environment variable in `.bashrc_term` and current session |

### Key Behaviors

1. **Session History**: Up/Down arrows navigate commands in current session
2. **Block Navigation**: PageUp/PageDown move focus between command blocks
3. **Focused Block as Pipe Source**: The focused block becomes the stdin source for `|` commands
4. **Bash Integration**: Sources `~/.bashrc` on startup for alias support
5. **Background Execution**: Commands run in threads to avoid blocking UI

### Database Schema

Commands are stored in `exeds_tags.db` (configurable via settings.yml) with:
- Tag identifier
- Command text
- Deleted flag (for soft delete)

## Dependencies

Install from `requirements.txt`:
- `textual==7.3.0` - TUI framework
- `rich==14.3.0` - Text formatting
- `pyperclip==1.11.0` - Clipboard operations
- `PyYAML==6.0.3` - Settings parsing
- `Pygments==2.19.2` - Syntax highlighting
- `markdown-it-py` plugins - Markdown parsing

## Key Configuration

Edit `settings.yml`:
- `max_lines`: Output buffer limit (default: 100000)
- `history_lines`: Default lines for `:h` command (default: 20)
- `database_tags_file`: SQLite database filename (default: exeds_tags.db)
