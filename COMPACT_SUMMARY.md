# IDvjPy_term — Compact Summary

TUI на Textual для запуска shell-команд с тегированной историей в SQLite. Версия: **v1.1.45**.

Запуск: `python3 app.py`. Тесты: `python3 -m pytest tests/ -v`.

Параллельный порт: `Idivjopy_rust` (ratatui). Поведение ниже — про Python, если не сказано иное.

---

## Commands

| Prefix | Action |
|--------|--------|
| (none) | Execute shell command |
| `#tag cmd` | Save (literal text; refs `!tag[tid]` not expanded on save) |
| `#tag=` / `#tag=ID=` | Tag / command comment (ID = tid or global `<id>`) |
| `#tag+` / `#tag+ID` | Edit last / by tid |
| `#tag-` / `#tag-tid` | Soft-delete (strict `#tag-` only, not `-` inside cmd) |
| `?` / `??` / `?tag` / `?tag[tid]` | Query tags / all / by tag / resolve preview |
| `!tag[tid]` / `!N` | Insert command into input (does not run) |
| `!! …` | Assemble into input. `tag[tid]` → SQL; numeric id → `last_query_results` cache |
| `:` | `:q` `:w` `:h` `:c` `:json` `:i` `:?` |
| `\|` | Pipe focused/last block stdout |
| `$VAR=val` | Set local env (also `$ VAR=val`); writes `.bashrc_term_<instance>` |

Hotkeys: `Tab` input → output (Esc back); `F3` copy block; `F5` JSON; `F6` simple output; `F2` line-cursor mode; `Shift+Insert`/`Ctrl+V` paste in the input (does not replace existing text); in line-cursor mode `Ctrl+V` appends the current line; `Ctrl+D` clears the input line; `PgUp`/`PgDn` blocks; `Up`/`Down` session history in input, journal scroll when a block is focused (line-by-line in line-cursor mode).

---

## Database read path

Details: `DATABASE.md`. Module: **`database_v2.py`** (`database.py` unused). File: `settings.yml` → `database_tags_file` (`history_v2.db`).

- Two IDs: global `id` (`!1`, `!! 1`) and per-tag `tid` (`!deploy[1]`).
- Each call opens SQLite, queries, closes. Filter `deleted = 0`.
- In-memory cache `last_query_results`: `{global_id: command}`. Filled on start, every 5s, and replaced on `?`/`??`/`?tag`.
- `!! tag[tid]` hits DB immediately. `!! 1` needs cache (start load, `??`, or 5s reload).
- Tab completion: DB `command LIKE prefix%` + session history; path context uses cwd files only (not mixed with full commands). Typing `!file` / `!kube` lists tagged commands (`<id> tag[tid]  cmd`) and inserts `!tag[tid]` only.

---

## Key features (current)

### Focus / journal
- `Tab` in the input focuses the last journal block in display order (`:h` / `:?` InfoBlocks included, not only the last CommandBlock). Completion list, if open, still consumes Tab to apply a candidate.
- `Esc` returns to input (in line-cursor mode: first Esc exits the mode, second Esc goes to input).
- `Ctrl+D` in the input clears the entire line (and hides the completion list).
- Completion list is **in-flow under the input** (not overlay); height grows with the candidate count and terminal size (6–24 rows, journal kept); footer always shows `n/n all` or `1–12 / 40 ↓28 more`. `can_focus = False`. PgUp/PgDn hide the list then move block focus.
- Input `select_on_focus = False`: returning from a block does not select-all, so paste/typing does not wipe the draft.

### Line-cursor mode (F2 / Enter on a focused block)
- **Off by default.** Focus a block (`Tab` / `PgUp`), then `Enter` or `F2` to turn it on. Current line is highlighted (`[reverse]` + left accent border).
- Off: `↑/↓` scroll the journal. On: `↑/↓` move by lines; `Home`/`End` first/last line. At the edge, arrows scroll the journal again.
- `Enter`: copy the current line (trailing spaces stripped) to CLIPBOARD + PRIMARY + Textual/OSC 52, then jump to input (cursor at end, no selection).
- `Shift+Enter` / `Ctrl+V`: append the line to the input, separated by a space; stay in the block (can append several lines). If the terminal sends Shift+Enter as plain Enter, use **Ctrl+V**. While the input is focused, `Ctrl+V` still pastes from the clipboard. The app requests kitty CSI-u / xterm `modifyOtherKeys`.
- Many terminals deliver Ctrl+V as a **Paste** event rather than a `ctrl+v` key; line-cursor mode treats that Paste as append (same as the key).
- `Esc`: turn mode off, stay on the block. `F2`: toggle.
- Documented in `:?` under **Line-cursor mode**.

### `:h` history
- `:h [N]` shows the last N lines of `history.txt` as **one** multiline `InfoBlock` (line-cursor can copy/append individual commands). Empty file → one info message.

### JSON Viewer (F5 / `:json` / `:json file`)
- F5 uses the **focused** block (`raw_stdout`); if focus is the input — last `CommandBlock`.
- Pretty-print, arrays at root, keys with `[` are safe (no Rich markup on user keys).
- `Enter` on a node: close viewer, set `$JSON`, clipboard, **insert draft into input**:
  - from a command block: `| jq '.path'`
  - from `:json file`: `jq '.path'`
- `$JSON` remains set for custom commands, e.g. `jq $JSON test.json` (`:?` documents this).

### Path / command completion
- Path context: `./` `../` `/` `~`, token with `/`, `cd`/`pushd`, or a non-flag argument after the command.
- Tab replaces **token only** for paths; full history/DB commands replace the **whole line** (prevents `cat cat json.file`).
- Trailing slash (`ls ~/`, `./`, `/usr/`): first candidate is the directory itself; Enter runs it; Tab keeps it; Down+Tab drills in.
- Exact full-line match hides the list so Enter submits instead of re-applying.
- **Trailing space** (`ls   `): list hides; Enter runs the typed command, not a longer candidate (`ls -la`). Tab (without trailing space) still applies the candidate.
- After apply: space → Backspace → Enter must not duplicate the command.

### Bang-ref completion (`!file`, `!kube`)
- Type `!` to list tags (`[file, kube, log]` header + selectable rows). Tab inserts `!file` and then lists that tag's commands.
- Current token `!tag` / `!tag[` lists commands as `<139> file[1]  ls -la`.
- Tab/Enter insert only `!file[1]` (replace the `!tag` token, keep `#pack ` / `|` around it).
- Live preview line `→ ls -la | cat x` expands already-typed `!tag[tid]` while composing `#file !file[1] | !file[2]` (save still stores refs literally).
- Unique tag prefix (`!fi` when only `file` exists) lists that tag's commands. Several matching tags → pick a tag first.

### Clipboard / paste
- Copy (F3, line Enter, JSON path) writes system CLIPBOARD, X11/Wayland PRIMARY, and Textual internal + OSC 52 (so Shift+Insert in the terminal matches mouse paste).
- `Shift+Insert` / `Ctrl+V` in the input paste from those buffers and **do not replace** existing text (insert at cursor / end if a leftover selection exists). In line-cursor mode `Ctrl+V` / Paste appends the current journal line instead.

### Output
- `MAX_DISPLAY_LINES = 300` (UI). Full text stays in `raw_stdout`; F3 copies full output.
- `F6` toggles simple output (no Rich tags).
- `command_timeout` from `settings.yml` (default 10s; tests use 5s).
- `terminal_mouse: false` lets the terminal select/copy text; scroll journal with PgUp/PgDn.

### Tags / vars
- `#` parser: strict regex so `ping -c` / `A=B` save instead of delete/comment.
- `$JSON` from viewer; `$NS` from `:i … -n`.
- Env files **merged**: `.bashrc_term_<instance>` wins on name clash; extras from `.bashrc_term` still load (`MYVAR` in `.bashrc_term` + `NS` in `_default`). Also accepts `VAR=val` without `export`.
- `$VAR=val` writes the instance file (`.bashrc_term_default` by default).
- `-n` without value → explicit error (no silent fallback).

### CLI
- `--instance-name` parsed only in `__main__` (pytest can import `app.py`).
- Instance bashrc: `.bashrc_term_{instance}`.

---

## Tests

| File | Coverage |
|------|----------|
| `test_cmd.md` | Manual plan v1.4 (base v1.1.18; newer UX in this file) |
| `tests/test_cmd_scenarios.py` | Sections of `test_cmd.md` (Pilot keypresses) |
| `tests/test_commands.py` | echo, history, vars, paste, Ctrl+D clear input, `:c`/`:q`, merge `.bashrc_term` + `_default` |
| `tests/test_tags.py` | save with `-`/`=`, bang, delete |
| `tests/test_completion.py` | Tab path, `ls ~/`, no `cat cat`, Tab→last journal block (`:h`/`:?`), line-cursor, trailing-space Enter, Shift+Enter/Ctrl+V/Paste append, `!tag` ref completion |
| `tests/test_json_viewer.py` | expand, search, F5 from focused cat, bracket keys, jq draft / `$JSON` |

Isolated tmp cwd + test DB. `submit()` clears input, dismisses completion, then Enter.

---

## Files

| File | Purpose |
|------|---------|
| `app.py` | TUI (`CommandRunner`), v1.1.45 |
| `database_v2.py` | SQLite tagged history |
| `json_viewer.py` | JSON tree modal |
| `ingress_analyzer.py` | `:i` k8s |
| `command_parser_v2.py` | `!tag[tid]` / `!ID` assembly |
| `app.css` | Styles (JSON viewer, line-nav border, block focus) |
| `settings.yml` | DB path, timeout, `terminal_mouse` |
| `DATABASE.md` | How commands are read from SQLite |
| `test_cmd.md` | Manual test script |

---

## This session (v1.1.25 → v1.1.45)

- **Line-cursor mode** on a focused output block (`Enter`/`F2` on, `Esc`/`F2` off). Arrows move by lines; Home/End jump.
- **Enter** in that mode copies the current line (rstrip) and returns to input without select-all.
- **Shift+Enter** / **Ctrl+V** append the line to the input with a space and stay in the block. Kitty CSI-u / `modifyOtherKeys` so Shift+Enter is not the same as Enter when the terminal supports it. `Ctrl+V` in the input still pastes from the clipboard.
- Copy writes CLIPBOARD + PRIMARY + Textual/OSC 52 so Shift+Insert paste works, not only mouse paste.
- Trailing space after a command dismisses the completion list so Enter runs `echo`, not `echo with-args extra`.
- `:?` documents Navigation + Line-cursor mode (including the Ctrl+V append shortcut).
- **`:h [N]`** shows `history.txt` as **one** multiline `InfoBlock` (line-cursor can copy/append individual commands). Previously each history line was a separate block.
- **Tab** from the input focuses the last journal block in display order, so `:h` / `:?` are reached in one Tab (not the previous shell `CommandBlock`).
- **Ctrl+V** in line-cursor mode also handles terminal **Paste** events (many emulators send paste instead of the `ctrl+v` key; that is why Ctrl+J worked and Ctrl+V did not).
- **Ctrl+D** in the input clears the entire line (overrides Textual's delete-char-right).
- **`!file` / `!kube` completion**: type `!` to list tags `[file, kube, log]`; then commands as `<id> tag[tid]  full command`; Tab inserts only `!tag[tid]`. Preview expands refs while composing `#file !file[1] | !file[2]`.
- **`??` / `?tag`**: command comments (`#tag=ID=comment`) are shown as dim `# comment`. Tag refs `tag[tid]` are Rich-escaped so `[tid]` does not swallow the rest of the line.
- **`#tag=ID=comment`**: ID is tid first, then global `<id>` from `??`. Missing command → error (no fake success). UPDATE only live rows.
- **Completion list** grows with the number of hints (up to 24 / terminal height). Footer always shows whether the list is complete (`8/8 all`) or truncated (`1–16 / 40 ↓24 more`).
- **Line-cursor toggle** is **F2** (was F7).
- **Copy block** is **F3** (was F5). JSON viewer is **F5**.
- Footer hints: Esc Focus Input, F2 Line cursor, F3 Copy Block, F5 JSON Viewer, F6 Simple output.
