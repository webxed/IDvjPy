# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with this repository.

## Project Overview

IDvjPy_term (v1.1.49) is a Python terminal application (TUI) built with the Textual framework. It provides a keyboard-driven interface for running shell commands with persistent, tagged command history stored in SQLite.

Philosophy: tags are variables holding command templates; the app assembles them into command lines (`!tag[tid]`, `!!`).

## Running the Application

```bash
python3 app.py
python3 app.py --instance-name=user1   # separate .bashrc_term_user1
```

Tests:

```bash
python3 -m pytest tests/ -v
```

In-app help: `:?`.

## Setup

```bash
./setup.sh
```

The setup script handles dependencies and configuration. On Linux, clipboard needs `xclip`/`xsel` (Wayland: `wl-clipboard`).

## Architecture

The TUI lives mainly in `app.py`. Key types:

- **`CommandRunner`** (App): command routing and UI orchestration
- **`JournalScroll`** (`VerticalScroll`): journal container; keyboard scroll activates the visible block
- **`CommandBlock`** / **`InfoBlock`** / **`QueryResultsBlock`**: journal widgets (`LineNavigable` for line-cursor)
- **`CommandInput`**: top input with completion and mouse-wheel → journal scroll

### Supporting Modules

- **`database_v2.py`**: SQLite tagged history (`database.py` is unused)
- **`command_parser_v2.py`**: `!tag[tid]` / `!ID` / `!!` assembly
- **`json_viewer.py`**: JSON tree modal
- **`ingress_analyzer.py`**: `:i` Kubernetes helper
- **`app.css`**: Textual styling
- **`settings.yml`**: buffer limits, timeout, DB file, `terminal_mouse`
- **`.bashrc_term` / `.bashrc_term_<instance>`**: env vars from `$VAR=val`

### Command Prefix System

| Prefix | Purpose |
|--------|---------|
| (none) | Execute shell command via subprocess, add to session history |
| `> cmd` | Suspend TUI (`App.suspend()`), run with a real TTY (`htop`, `vim`, `ssh`). No timeout, stdout not captured. `>>` is left to the shell. |
| `#tag cmd` | Save command to database with tag (literal text; refs not expanded on save) |
| `#tag=` / `#tag=ID=` | Tag / command comment (ID = tid or global `<id>`) |
| `#tag+` / `#tag+ID` | Load last / by tid into input for editing |
| `#tag-` / `#tag-tid` | Soft-delete |
| `?` / `??` / `?tag` / `?tag[tid]` | Query tags / all / by tag / resolve preview |
| `!tag[tid]` / `!N` | Insert command into input (does not run) |
| `!! …` | Assemble refs into the input line |
| `:` | App commands (`:q`, `:w file`, `:h [N]`, `:c`, `:json`, `:i`, `:?`) |
| `\| cmd` | Pipe stdout from the focused block |
| `$VAR=val` | Set env in `.bashrc_term_<instance>` and the current session |

`!` / `!!` only insert text. Run with a separate Enter.

Aliases load from `~/.bashrc`. If the body contains `$1` / `$2` / `$@` / `$*`, arguments are substituted (like a shell function). Otherwise the rest of the line is appended (classic alias).

### Key Behaviors

1. **Session history**: Up/Down in the input cycle commands from the current session
2. **Journal**: PgUp/PgDn / arrows (when a block is focused) scroll the journal; the **visible** block becomes active (no jump to its first line). Click a block to focus it (`terminal_mouse: true`)
3. **Tab** from the input focuses the last journal block (`:h` / `:?` included)
4. **Focused block as pipe source**: `|` uses the focused block's stdout
5. **Bash aliases**: loaded at startup; `$1` positional substitution supported
6. **Background execution**: shell commands run in threads so the UI stays responsive
7. **Line-cursor (F2 / Enter on a focused block)**: copy or append individual output lines
8. **Bang-ref completion**: type `!` to list tags, then commands as `<id> tag[tid]`; Tab inserts `!tag[tid]`

### Database Schema

File: `settings.yml` → `database_tags_file` (default `history_v2.db`).

- Global `id` (`!1`, `!! 1`) and per-tag `tid` (`!deploy[1]`)
- Soft-delete flag (`deleted = 0` in queries)
- In-memory cache `last_query_results` filled on start, every 5s, and on `?`/`??`/`?tag`

Details: `DATABASE.md`. User-facing summary: `COMPACT_SUMMARY.md`, `README.md`.

## Dependencies

Install from `requirements.txt`:
- `textual==7.3.0` - TUI framework
- `rich==14.3.0` - Text formatting
- `pyperclip==1.11.0` - Clipboard operations
- `PyYAML==6.0.3` - Settings parsing
- `Pygments==2.19.2` - Syntax highlighting
- `portalocker` - file locking

## Key Configuration

Edit `settings.yml`:
- `max_lines`: Output buffer limit (default: 100000)
- `history_lines`: Default lines for `:h` (default: 20)
- `database_tags_file`: SQLite filename (default: `history_v2.db`)
- `command_timeout`: seconds; `0` = no timeout (default: 10)
- `terminal_mouse`: `true` — click focuses a block, wheel scrolls the journal; `false` — OS text selection (clicks do not focus)
