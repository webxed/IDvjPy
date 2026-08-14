# IDvjPy_term — Compact Summary

TUI на Textual для запуска shell-команд с тегированной историей в SQLite. Версия: **v1.1.18**.

Запуск: `python3 app.py`. Тесты: `python3 -m pytest tests/ -v`.

---

## Commands

| Prefix | Action |
|--------|--------|
| (none) | Execute shell command |
| `#tag cmd` | Save (literal text; refs `!tag[tid]` not expanded on save) |
| `#tag=` / `#tag=ID=` | Tag / command comment |
| `#tag+` / `#tag+ID` | Edit last / by tid |
| `#tag-` / `#tag-tid` | Soft-delete (strict `#tag-` only, not `-` inside cmd) |
| `?` / `??` / `?tag` / `?tag[tid]` | Query tags / all / by tag / resolve preview |
| `!tag[tid]` / `!N` | Insert command into input (does not run) |
| `!! …` | Assemble into input. `tag[tid]` → SQL; numeric id → `last_query_results` cache |
| `:` | `:q` `:w` `:h` `:c` `:json` `:i` `:?` |
| `\|` | Pipe focused/last block stdout |
| `$VAR=val` | Set local env (also `$ VAR=val`) |

Hotkeys: `F3` JSON viewer, `F5` copy full stdout, `F6` simple output, `Shift+Insert`/`Ctrl+V` paste, `PgUp`/`PgDn` blocks, `Up`/`Down` session history (if completion list closed).

---

## Database read path

Details: `DATABASE.md`. Module: **`database_v2.py`** (`database.py` unused). File: `settings.yml` → `database_tags_file` (`history_v2.db`).

- Two IDs: global `id` (`!1`, `!! 1`) and per-tag `tid` (`!deploy[1]`).
- Each call opens SQLite, queries, closes. Filter `deleted = 0`.
- In-memory cache `last_query_results`: `{global_id: command}`. Filled on start, every 5s, and replaced on `?`/`??`/`?tag`.
- `!! tag[tid]` hits DB immediately. `!! 1` needs cache (start load, `??`, or 5s reload).
- Tab completion: `command LIKE prefix%` plus session history plus cwd files.

---

## Key features (current)

### JSON Viewer
- All branches expanded on open; live filter (`/`, `Ctrl+F`) on key/value/jq-path; `n`/`N`, `F6`.
- `Enter` (tree focused, after Down): copy jq-path, set `$JSON`, close. Guard against double `pop_screen`.
- Right-arrow uses manual child move (`Tree.action_cursor_child` missing in Textual 7.3).

### Path completion
- Path context: `./` `../` `/` `~` or argument after space.
- Tab replaces **token only**, keeps the rest of the line; dirs get `/` and list reopens.
- Scrollable list (16 visible) + `... and N more`. Filenames escaped for Rich markup.

### Output
- `MAX_DISPLAY_LINES = 300` (UI). Full text stays in `raw_stdout`; F5 copies full output.
- `command_timeout` from `settings.yml` (default 10s; tests use 5s).

### Tags / vars
- `#` parser: strict regex so `ping -c` / `A=B` save instead of delete/comment.
- `$JSON` set from viewer; `$NS` persisted from `:i … -n`.
- `-n` without value → explicit error (no silent fallback).

### CLI
- `--instance-name` parsed only in `__main__` (pytest can import `app.py`).
- `.bashrc_term_{instance}`.

---

## Tests

| File | Coverage |
|------|----------|
| `test_cmd.md` | Manual plan v1.4, aligned with v1.1.18 |
| `tests/test_cmd_scenarios.py` | Sections of `test_cmd.md` (Pilot keypresses) |
| `tests/test_commands.py` | echo, history, vars, paste, `:c`/`:q` |
| `tests/test_tags.py` | save with `-`/`=`, bang, delete |
| `tests/test_completion.py` | Tab path, dir `/`, scroll |
| `tests/test_json_viewer.py` | expand, search, F3, `$JSON` |

Isolated tmp cwd + test DB. `submit()` clears input, dismisses completion, then Enter.

---

## Files

| File | Purpose |
|------|---------|
| `app.py` | TUI (`CommandRunner`) |
| `database_v2.py` | SQLite tagged history |
| `json_viewer.py` | JSON tree modal |
| `ingress_analyzer.py` | `:i` k8s |
| `command_parser_v2.py` | `!tag[tid]` / `!ID` assembly |
| `app.css` | Styles |
| `settings.yml` | DB path, timeout, `terminal_mouse` |
| `DATABASE.md` | How commands are read from SQLite |
| `test_cmd.md` | Manual test script |

---

## This session
- Pilot autotests for TUI; `test_cmd.md` updated; `DATABASE.md` written.
- Completion markup escape; argparse not at import; paste/`$JSON`/tag parser already in tree.
- Version documented: v1.1.18.
