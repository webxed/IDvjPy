# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with this repository.

## Project Overview

IDvjPy_term (v1.24) is a Python terminal application (TUI) built with the Textual framework. It provides a keyboard-driven interface for running shell commands with persistent, tagged command history stored in SQLite.

Philosophy: tags are variables holding command templates; the app assembles them into command lines (`!tag[tid]`, `!!`).

## Running the Application

```bash
python3 app.py
python3 app.py --instance-name=user1   # .bashrc_term_user1 и history_user1.txt
python3 app.py --demo                  # короткий тур (Esc — стоп)
python3 app.py --demo ip               # myip → jq .cc → F2 copy → Wiki URL → hello pipe → echo Hello, $OUT
python3 app.py --demo full --demo-quit # длинный тур и выход (удобно для asciinema)
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

## Layout

- **`src/`** — TUI, CSS, seed scripts, `.bashrc_term.example`
- **cwd** — `settings.yml`, SQLite command DB, `.bashrc_term*`, `history_<instance>.txt`
- Root **`app.py`** / **`backup_db.py`** are launchers
- Empty command DB: welcome InfoBlock lists handbook seeds (`src/seed_catalog.py`). After `--seed`, type `??` or wait ~5s
- Seeds: `python3 src/seed_linux_commands.py --seed`, `python3 src/seed_k8s_chains.py --seed` ([`K8S_CHAINS.md`](K8S_CHAINS.md)), `python3 src/seed_git.py --seed`, `python3 src/seed_ops.py --seed` (all ops except linux / k8s / git). Each `--seed` replaces only its own tags

## Architecture

The TUI lives mainly in `src/app.py` (root `app.py` is a launcher). Key types:

- **`CommandRunner`** (App): command routing and UI orchestration
- **`JournalScroll`** (`VerticalScroll`): journal container; keyboard scroll activates the visible block
- **`CommandBlock`** / **`InfoBlock`** / **`QueryResultsBlock`**: journal widgets (`LineNavigable` for line-cursor)
- **`CommandInput`**: top input with completion and mouse-wheel → journal scroll

### Supporting Modules

- **`src/database_v2.py`**: SQLite tagged history (`database.py` is unused)
- **`src/command_parser_v2.py`**: `!tag[tid]` / `!ID` / `!!` assembly
- **`src/clipboard.py`**: CLIPBOARD / PRIMARY / OSC 52
- **`src/shell_env.py`**: `.bashrc_term` vars, `~/.bashrc` aliases, `$1` substitution
- **`src/json_viewer.py`**: JSON tree modal
- **`src/demo.py`**: `--demo` YAML player (`src/demos/*.yml`)
- **`src/ingress_analyzer.py`**: `:i` Kubernetes helper
- **`src/app.css`**: Textual styling
- **`settings.yml`**: buffer limits, timeout, DB file, `terminal_mouse` (cwd)
- **`.bashrc_term` / `.bashrc_term_<instance>`**: env vars from `$VAR=val` (cwd; template `src/.bashrc_term.example`)

### Command Prefix System

| Prefix | Purpose |
|--------|---------|
| (none) | Execute shell command via subprocess, add to session history |
| `> cmd` | Suspend TUI (`App.suspend()`), run with a real TTY (`htop`, `vim`, `ssh`). No timeout, stdout not captured. `>>` is left to the shell. |
| `#tag cmd` | Save command to database with tag (literal text; refs not expanded on save) |
| `# command` | Park the line in `history_<instance>.txt` and the journal; do not run (`#` + space, like bash) |
| `#tag=` / `#tag=ID=` | Tag / command comment (ID = tid or global `<id>`) |
| `#tag+` / `#tag+ID` | Load last / by tid into input for editing |
| `#tag-` / `#tag-tid` | Soft-delete |
| `#name--` / `#name!!` | Hide / restore a handbook's tags (`ansible`, `linux`, `k8s`, …) |
| `#tag!` / `#tag!tid` | Restore soft-deleted tag / command |
| `?` / `??` / `?tag` / `?tag[tid]` | Query tags / all / by tag / resolve preview |
| `!tag[tid]` / `!N` | Insert command into input (does not run) |
| `!! …` | Assemble refs into the input line |
| `:` | App commands (`:q`, `:w file`, `:h [N]`, `:h /text`, `:c`, `:json`, `:i`, `:?`, `:cd`, `:r`, `:/`, `:n`, `:N`, `:export`) |
| `\| cmd` | Pipe stdout from the focused block, add to history |
| `$OUT` | On demand: last line of focused/last block (not stored in `.bashrc_term`) |
| `$VAR=val` | Set env in `.bashrc_term_<instance>` and the current session |

`!` / `!!` only insert text. Run with a separate Enter.

Aliases load from `~/.bashrc`. If the body contains `$1` / `$2` / `$@` / `$*`, arguments are substituted (like a shell function). Otherwise the rest of the line is appended (classic alias).

### Key Behaviors

1. **Shell history**: Up/Down in the input walk `history_<instance>.txt` (plus this session). Typed text filters matches; empty input walks all lines (newest at the end). `:h /text` lists unique matching lines in the completion dropdown (newest first). Legacy `history.txt` is copied once if the instance file is missing.
2. **Journal**: PgUp/PgDn / arrows (when a block is focused) scroll the journal; the **visible** block becomes active (no jump to its first line). Click a block to focus it (`terminal_mouse: true`)
3. **Tab** from the input focuses the last journal block (`:h` / `:?` included)
4. **Focused block as pipe source**: `|` uses the focused block's stdout. `$OUT` is that block's last non-empty line, computed only when the command contains `$OUT` / `${OUT}`
5. **Bash aliases**: loaded at startup; `$1` positional substitution supported
6. **Background execution**: shell commands run in threads so the UI stays responsive
7. **Line-cursor (F2 / Enter on a focused block)**: copy or append individual output lines. **Ctrl+C** copies the whole input draft, or the focused journal block (same as F3).
8. **Bang-ref completion**: type `!` to list tags, then commands as `<id> tag[tid]`; Tab inserts `!tag[tid]`

### Database Schema

File: `settings.yml` → `database_tags_file` (default `mytags.db`).

- Global `id` (`!1`, `!! 1`) and per-tag `tid` (`!deploy[1]`)
- Soft-delete flag (`deleted = 0` in queries). `#name--` / `#name!!` hide/restore a seed handbook's tags. Hidden tags appear in `??` / `?`, not in `!` completion.
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
- `database_tags_file`: SQLite filename (default: `mytags.db`)
- `command_timeout`: seconds; `0` = no timeout (default: 10)
- `terminal_mouse`: `true` — click focuses a block, wheel scrolls the journal; `false` — OS text selection (clicks do not focus)
- `theme`: Textual theme name (`textual-dark` default). `d` toggles dark/light and writes this key; `:theme nord` picks a named theme
