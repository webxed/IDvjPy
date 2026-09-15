# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with this repository.

## Project Overview

IDvjPy_term (v1.117) is a Python terminal application (TUI) built with the Textual framework. It provides a keyboard-driven interface for running shell commands with persistent, tagged command history stored in SQLite.

Philosophy: tags are variables holding command templates; the app assembles them into command lines (`!tag[tid]`, `!!`).

Bump `CommandRunner.VERSION` minor on every commit (`v1.117` → `v1.118`). `:update` compares that string with GitHub `main` (`https://github.com/webxed/IDvjPy`).

## Running the Application

```bash
python3 app.py
python3 app.py --instance-name=user1   # .bashrc_term_user1 и history_user1.txt
python3 app.py --demo                  # короткий тур (Esc — стоп)
python3 app.py --demo ip               # myip → jq .cc → F2 copy → Wiki URL → hello pipe → echo Hello, $OUT
python3 app.py --demo features         # v1.44: ?text, :mv, :stats, F4-stop, :watch, :diff, :o, :export *, :alias
python3 app.py --demo all              # всё подряд: calc/ipcalc/JSON/теги/утилиты (без сети, без кластера)
python3 app.py --demo full --demo-quit # длинный тур и выход (удобно для asciinema)
```

Tests:

```bash
python3 -m pytest tests/ -v
```

Dev dependencies for tests: `pip install -r requirements-dev.txt` (pytest, pytest-asyncio, pytest-timeout). Quick smoke that skips the slow Pilot suites: `python3 -m pytest tests/ -m "not slow"`.

In-app help: `:?`.

## Setup

```bash
./setup.sh
```

The setup script handles dependencies and configuration. On Linux, clipboard needs `xclip`/`xsel` (Wayland: `wl-clipboard`).

## Layout

- **`src/`** — TUI, CSS, seed scripts, `.bashrc_term.example`
- Launch cwd — `settings.yml`, SQLite command DB, `.bashrc_term*`, `history_<instance>.txt`. `:cd` / `cd` change the process cwd for shell commands; they do not move or recreate the tags DB.
  The root `settings.yml` is **not tracked** (`.gitignore`): it is a copy of `src/settings.example.yml`, created on first run in a new data dir. Personal settings must not leak to GitHub; edit the example for defaults.
- Data dir resolution: `--data-dir` → `$IDVJPY_DATA_DIR` → launch cwd if it holds `settings.yml` (portable) → OS default (`~/.config/idvjpy` / macOS App Support / Windows `%APPDATA%`). See `src/data_dirs.py`.
- Root **`app.py`** / **`backup_db.py`** are launchers
- **`docker/`** — демостенд: `Dockerfile` (python:3.12-alpine + bash / terminfo / nano / git / curl / jq / procps), `compose.yaml` (сервис с `tty`/`stdin_open` и томом `idvjpy-demo-data`), `entrypoint.sh` (создаёт `/data/settings.yml` из шаблона, один раз сеет linux/k8s/git/ops и запускает `app.py`), `tui-smoke.py` (запускает TUI под настоящим pty заданного размера — для локального смоука и CI), `README.md`. Контекст сборки — корень репозитория, `.dockerignore` режет `.git`/`.venv`/`tests/`/`packaging/`. Образ ~100 МБ, `docker`/`kubectl` в него намеренно не входят. CI job `docker-demo` собирает образ и прогоняет смоук (`.github/workflows/tests.yml`).
- **`packaging/`** — pip-упаковка (`idvjpy-term`). `build_wheel.sh` копирует текущий `src/` во вложенный ресурс `idvjpy_boot/src` и собирает wheel (без сети); boot-модуль при запуске (`idvjpy`, `python -m idvjpy_boot`) добавляет вложенную `src/` в `sys.path` — топ-левел импорты и ресурсы (`app.tcss`, `demos/`, примеры, `.bashrc_term.example`) читаются из пакета, а не из репозитория. Установка прямо из git (`pip install .`, `uv tool install git+…`) идёт через корневые `pyproject.toml`/`setup.py` (build_py вкладывает `src/`). Данные пользователя — всегда вне пакета (см. data dir выше).
- Empty command DB: welcome InfoBlock lists handbook seeds (`src/seed_catalog.py`). Click a `--seed` line to insert it into the input; click a `.md` name or `:md` to open the handbook. After `--seed`, type `??` or wait ~5s. `:welcome` shows that catalog again. Non-empty DB: startup lists loaded tag sections (`linux`, `k8s`, `свои`, …).
- Seeds: `python3 src/seed_linux_commands.py --seed`, `python3 src/seed_k8s_chains.py --seed` ([`K8S_CHAINS.md`](K8S_CHAINS.md)), `python3 src/seed_git.py --seed`, `python3 src/seed_ops.py --seed` (all ops except linux / k8s / git). Each `--seed` replaces only its own tags. A live DB is copied first to `backup_dir` (`backups/<stem>-pre-<label>-<timestamp>.db`); empty DB is skipped; `seed_ops` snapshots once.

## Architecture

The TUI lives mainly in `src/app.py` (root `app.py` is a launcher). Key types:

- **`CommandRunner`** (App): command routing and UI orchestration
- **`JournalScroll`** (`VerticalScroll`): journal container; keyboard scroll activates the visible block
- **`CommandBlock`** / **`InfoBlock`** / **`QueryResultsBlock`**: journal widgets (`LineNavigable` for line-cursor)
- **`CommandLineBlock`**: opt-in Line-API variant of `CommandBlock` (`render_line` + cached `Strip`s; wrapping matches `Static`). Enabled by `line_api_blocks: true` (settings) or `IDVJPY_LINE_BLOCKS=1`; created via `CommandRunner._make_command_block`
- **`InfoBlock`**: also Line API — `render_line` + strip cache via the shared `line_api_text_strips()` helper (a plain `Static` rebuilt strips for the whole widget on every focus change: ~136 ms per click on the `:?` help). The focus background is kept **out** of the cache (`_style_without_bg()` + applied per visible row), so clicking a block no longer invalidates the content; the line cursor is painted in `render_line` (`_line_rows`), so `on_blur` no longer replaces the markup with plain text. `line_api_blocks: false` / `IDVJPY_LINE_BLOCKS=0` restores the plain `Static` path
  - **Pitfall**: `Content.to_strips(widget, visual, width, height, style)` takes a **Textual** style (`Widget.visual_style`), never `visual_style.rich_style`. With a Rich `Style` it silently (no exception) returns **blank** strips, so the block renders empty while `text_content` stays correct. Any test for this must assert on the rendered output (`render_line(y).text` / `_strips`), not `text_content`
  - **Pitfall**: Textual writes `meta['offset'] = (x, y)` into every segment; `Screen.get_widget_and_offset_at` reads it to map a screen cell back to a text character (this is what mouse selection uses). Because the helper renders **one logical line per call**, Textual always wrote `y = 0` and every drag collapsed into the block's first line. `_retag_offsets()` rewrites `y` to the real logical line, `row_logical_lines()` keeps the `visual row → logical line` map, and `highlight_selection()` paints the selection in `render_line` (Textual only paints it inside `Visual.to_strips`, which Line API bypasses). `CommandLineBlock.get_selection()` extracts from the plain text, because its `Static` visual is never updated
  - **Pitfall**: any code that **splits or rewrites** segments must fix `meta['offset']` on each piece (`_with_offset(style, x, y)`) — meta is what the compositor uses for the cell → character mapping. Reusing the original segment's meta on a tail piece made the selection drift: it crept at half the cursor speed and stuck to the end of the line. Tests: `test_line_api_selection_keeps_cell_offsets` / `test_info_block_line_api_selection_keeps_cell_offsets` assert `offset == (cell, logical_line)` for every cell
- **`CommandLineBlock` / `InfoBlock` selection**: logical lines are what `Selection` addresses; `_logical_line(y)` converts a visual row. `apply_block_selection(widget, strip, logical_y)` is the shared entry point in `render_line`
- **`CommandBlock._display_payload()`**: single place that decides what goes into `update()`. `MarkdownCommandBlock` (created with `_make_command_block(..., markdown=True)`, used for `:llm`) returns a Rich `Markdown`, so the answer is formatted; the plain `text_content` / `_nav_plain_text` stay untouched, which keeps F3 / `:w` / `|` / `$OUT` / line cursor working. Disabled by `llm_render_markdown: false` or simple mode (F6); never uses Line API
- **`CommandInput`**: top input with completion (paths, DB commands, `history_*.txt`, `!tag`, `:llm ` / `:send ` args, and all app commands after `:`) and mouse-wheel → journal scroll
- **`src/colon_commands.py`**: `COLON_COMMANDS` — one-line hints for every `:` command (order = usefulness, not alphabet); `CommandRunner.get_colon_completions` feeds them into the completion list, and `linkify_colon_commands(text)` wraps `:cmd` tokens into `[@click=app.insert_colon_draft('cmd')]` links (used by `:?` — apply **after** `escape_help_markup`). `tests/test_colon_commands.py` asserts the table covers every `CommandRunner.CMD_*`
- **Completion list click**: `CompletionList._item_markup` wraps only the **command** part of a row in `[@click=app.pick_completion(<global index>)]` — `_link_span` picks the substring from `CompletionItem.click` (else `insert`; not found → the whole display, as before). Wrapping the whole row made Textual's `auto_links` underline the counter/comment/description too, so the row looked like one big link. A mouse click does what Textual's broker does — `CommandRunner.action_pick_completion` → `CommandInput.apply_completion_item(index)` inserts the item and returns `item.run`. Items flagged `run=True` (the `?tag` tag hints from `get_tag_query_completions`) are also submitted at once; everything else only inserts. Keyboard stays the primary path (Tab/Enter insert, Enter runs)
- **Tag-ref click can run too**: a plain click on a `!tag[tid]` link only inserts (unchanged), but **Ctrl+click** or a **double click** inserts and runs it — i.e. what typing the ref and pressing Enter twice does (`_run_input_reference` posts two `Input.Submitted` messages: the literal expands into the input, the expanded text is executed). Textual cannot express this: markup tag keys are `[@a-zA-Z_-][a-zA-Z0-9_-]*=` (no dots, so `@click.ctrl` does not even parse), and `App._broker_event` **discards** the key's modifiers — `@click.ctrl` would fire on a plain click too. So `LineNavigable.on_click` (called **before** the broker, same message) stashes the click chain in `CommandRunner._link_click_run` (`note_block_link_click`) and `action_insert_bang_draft` consumes it: `None` = insert only, `1` = Ctrl+click (insert + run), `>= 2` = double click (the first click of the series inserted, so the second only runs — otherwise the input got `!tag[tid] !tag[tid] `). A tid-less `!tag ` is never run (not a command), and other links (`:commands`, `.md`, `--seed`) reset the flag. Tests: `tests/test_tag_ref_click.py`

### Supporting Modules

- **`src/database_v2.py`**: SQLite tagged history
- **`src/command_parser_v2.py`**: `!tag[tid]` / `!ID` / `!!` assembly
- **`src/history_store.py`**: `history_<instance>.txt` append/read/compact + portalocker file-lock helpers
- **`src/session_mailbox.py`**: cross-session command relay (`:send` / `:send!`) — per-session `inbox_<instance>.jsonl` (JSON Lines, 0600, same portalocker pattern as `history_store`); `send_message` appends, `drain_inbox` reads-and-truncates, `pending_sessions` lists non-empty inboxes
- **`src/session_registry.py`**: active-session registry — per-session `session_<instance>.pid` (0600) in the data dir; `register` / `unregister` (with a `pid=` that no longer matches the file, someone else's record is left alone), `active_sessions` (pid files of dead processes are removed), `free_session_name` (lowest free `sN` among **live** sessions, plus `taken`). `:new` without a name uses it, so the counter follows running windows instead of leftover `history_*.txt` / `.bashrc_term_*`. **Not** the same question as `CommandRunner.list_session_names` (by files; `:send` / `:session` lists still show closed sessions)
- **`src/kctx_store.py`**: cluster journal `kctx.json` (data dir): snapshots of the kubectl var stack (`NS POD DEPLOY SVC ING APP CTR QUOTA`) per cluster, captured on `$VAR=` after a `klogin` / `tsh kube login` / `kubectl config use-context` line; UI `:kctx` lists clusters and applies saved sets
- **`src/help_texts.py`**: static `:?` / `:i` help text constants
- **`src/clipboard.py`**: CLIPBOARD / PRIMARY / OSC 52
- **`src/shell_env.py`**: `.bashrc_term` vars, `~/.bashrc` aliases, `$1` substitution
- **`src/json_viewer.py`**: JSON tree modal
- **`src/output_viewer.py`**: `:log` / F7 — full block output in a Line-API `ScrollView` (lazy `render_line`, no 300-line cap; arrows/PgUp/PgDn scroll)
- **`src/block_label.py`**: F8 label dialog for block buffers (`:name`); sets/removes a label used by `|@<label> <command>`
- **`src/md_viewer.py`**: handbook Markdown modal (`:md`, welcome `.md` clicks); `resolve_md_path` also opens explicit paths (vault files from `:rg`)
- **`src/md_search.py`**: `:rg` markdown search — ripgrep backend (`--json`) when `rg` is in PATH, built-in walk otherwise (skips `.git`/`.obsidian`/`node_modules`); smart case; `rg_available` / `install_hint`
- **`src/update_check.py`**: GitHub `VERSION` check (`:update`)
- **`src/k8s_complete.py`**: live-cluster name completion for `kubectl get …` (gated by `k8s_completion: true`)
- **`src/llm_client.py`**: `:llm` calls to LLM providers described in `llm_providers.yml` (env-only secrets, urllib, background thread); `expand_file_refs` turns `@file` into inlined text; `history_turns` keeps the last N pairs in memory (`%HISTORY%` in custom bodies)
- **`src/llm_context.py`**: app context for LLMs — prefix cheat-sheet plus a budgeted digest of the live tag library (`tag`/`tid`/`command`/`comment`, task-relevant tags first). Powers `:llm ask <task>` (always) and the `app_context: true|N` provider key (opt-in for plain `:llm`); `extract_refs` filters answers down to refs that really exist
- **`src/cheat_sh.py`**: `:cht <query>` — cheat.sh (cht.sh) cheat sheets (query → URL with `+`, ANSI stripping, proxy-aware urllib fetch in a background thread). The service returns `text/plain` only to a curl-like User-Agent; settings `cheat_sh_url` / `cheat_sh_options`
- **`src/gui_open.py`**: `:fm` / `:term` — detach a file manager or system terminal; `open_terminal_command` / `build_terminal_exec_argv` run a command inside a terminal (used by `:new` to launch another app window; Linux / macOS / Windows; `$FILEMAN` / `$TERMINAL` override)
- **`src/editor_open.py`**: `:ed` — external editor for a file, `$OUT` or `$BLOCK` (settings `editor:` → `$VISUAL`/`$EDITOR` → system list; runs in a real TTY via `_run_in_tty`; temp copies for block output)
- **`src/screensaver.py`**: idle starfield (`:screensaver`); flying live clock/date; full-width green library ticker; bottom-left command-help typewriter and bottom-right load/RAM (1s `/proc`; may overlap when the window is narrow); `screensaver_idle` seconds, `0` = off; `screensaver_stars: false` hides flying dust/tokens
- **`src/seed_catalog.py`**: empty-DB welcome catalog (click `--seed` → input)
- **`src/demo.py`**: `--demo` YAML player (`src/demos/*.yml`); `loop: true` / `loop: N` (Esc stops)
- **`src/ingress_analyzer.py`**: `:i` Kubernetes helper
- **`src/version_bump.py`** (launcher `bump_version.py`): bump `CommandRunner.VERSION` minor and sync every release file in one run (`--set`, `--dry-run`, `--check`); `check()` mirrors `tests/test_release_meta.py` plus the bold state markers of `DATABASE.md` / `backup_db.md` (`BOLD_VERSION_DOCS`; `TARGETS` also covers them — `tests/test_version_bump.py` asserts `set(TARGETS) == set(FIXTURES)`)
- **`src/app.tcss`**: Textual styling (`.tcss` — расширение Textual CSS; браузерный CSS-линтер редактора не должен его разбирать — иначе ложные `property value expected` на `$surface`/`dock`). Путь читается из `CommandRunner.CSS_PATH`; сторожит `tests/test_stylesheet.py`
  - Блок в фокусе подсвечивается смешением `background: $primary 25%` (сплошной `$primary-darken-1` слепил на больших блоках); правила `Screen.matrix-mode …` меняют рамки только у темы matrix
- **Темы**: своя `matrix` живёт в `src/app.py` (`MATRIX_THEME` — зелёный фосфор `#00ff5f` на почти чёрном, регистрируется в `on_mount` до применения темы из settings.yml). Класс `MATRIX_CLASS` (`matrix-mode`) на `Screen` держит `watch_theme` — он ловит все три пути смены темы (settings.yml, `:theme`, клавиша `d`), по классу app.tcss красит рамки. Смена темы не трогает чужие темы: их CSS остаётся прежним. Тесты — `tests/test_themes.py`
- **`settings.yml`**: buffer limits, timeout, DB file, `terminal_mouse`, `screensaver_idle`, `screensaver_stars` (cwd)
- **`.bashrc_term` / `.bashrc_term_<instance>`**: env vars from `$VAR=val` (cwd; template `src/.bashrc_term.example`)

### Command Prefix System

| Prefix | Purpose |
|--------|---------|
| (none) | Execute shell command via subprocess, add to session history |
| `> cmd` | Suspend TUI (`App.suspend()`), run with a real TTY (`htop`, `vim`, `ssh`). No timeout, stdout not captured. `>>` is left to the shell. On exit: dump that bash's env/`$PWD` into the TUI. Nested `> bash` exports are not visible. |
| `@ cmd` | Run without `command_timeout` (long non-TTY jobs; still captures stdout) |
| `#tag cmd` | Save command to database with tag (literal text; refs not expanded on save) |
| `# command` | Park the line in `history_<instance>.txt` and the journal; do not run (`#` + space, like bash) |
| `#tag=` / `#tag=ID=` | Tag / command comment (ID = tid or global `<id>`) |
| `#tag+` / `#tag+ID` | Load last / by tid into input for editing |
| `#tag-` / `#tag-tid` | Soft-delete |
| `#name--` / `#name!!` | Hide / restore a handbook's tags (`ansible`, `linux`, `k8s`, …) |
| `#tag!` / `#tag!tid` | Restore soft-deleted tag / command |
| `?` / `??` / `?tag` / `?tag[tid]` | Query tags / all / by tag / resolve preview. `?text` (2+ chars, no exact tag) = substring search over command text + comments. Click tag in `??` inserts `!tag ` at the cursor (does not replace the line, does not run). |
| `!tag[tid]` / `!N` | Insert command into input (does not run) |
| `!! …` | Assemble refs into the input line |
| `:` | App commands (`:q`, `:w file`, `:h [N]`, `:h /text`, `:c`, `:json`, `:i`, `:?`, `:cd`, `:fm`, `:term`, `:env`, `:session`, `:new`, `:send`, `:send!`, `:welcome`, `:backup`, `:screensaver`, `:r`, `:cmd`, `:log`, `:name`, `:rg`, `:/`, `:n`, `:N`, `:export`, `:import`, `:md`, `:playbook`, `:update`, `:kill`, `:watch`, `:mv`, `:stats`, `:diff`, `:o`, `:kctx`, `:alias`, `:llm`, `:cht`, `:ed`, `:theme`) |
| `\| cmd` | Pipe stdout from the focused (else last) block, add to history |
| `\|@<label> cmd` / `\|@N cmd` | Pipe from the block labelled by `:name <label>`, or from N blocks back (0 = last). The source is not re-run; history stores the full `<source> \| <cmd>` |
| `$OUT` | On demand: last line of focused/last block (not stored in `.bashrc_term`) |
| `$VAR=val` | Set env in `.bashrc_term_<instance>` and the current session. `:env` re-reads the files. |
| `$$VAR=val` | Secret env: value is masked in the input line and journal (`****`); stored in `secrets_<instance>.json` (0600), deleted on app exit (session only), masked out of `:llm` messages. Use as `$VAR`; `$$VAR` status, `$$VAR-` remove. |
| `$VAR=@key` | Value from the focused/last finished block: line whose first token is `key` (vault tables); `@last` = last line. `$$VAR=@key` stores a secret. |

`!` / `!!` only insert text. Run with a separate Enter.

Aliases load from `~/.bashrc`. If the body contains `$1` / `$2` / `$@` / `$*`, arguments are substituted (like a shell function). Otherwise the rest of the line is appended (classic alias).

### Key Behaviors

1. **Shell history**: Up/Down in the input walk `history_<instance>.txt` (plus this session). Typed text filters matches; empty input walks all lines (newest at the end). `:h /text` lists unique matching lines in the completion dropdown (newest first). Legacy `history.txt` is copied once if the instance file is missing. `:h compact` uniques the old prefix; the last `history_keep` lines stay a sequence. Startup compact only if the file is longer than `2 × history_keep`. `:session NAME` switches or creates an instance (history + `.bashrc_term_*`); the tags DB stays shared. `Ctrl+N` / the footer `New session` button open another window (`:new`); without a name it takes the lowest free `sN` **among sessions registered as running** (`src/session_registry.py`: `session_<instance>.pid`, 0600, dead entries dropped) — not among leftover `history_*` / `.bashrc_term_*` files, so two quick presses give `s2` and `s3` and closing `s2` frees the name again. The header title and the terminal window/tab title (OSC 0) show `IDvjPy_term · <session>` — plus `— N running` while background commands run (`_refresh_running_title` / `_base_title` / `_set_terminal_title`).
2. **Journal**: PgUp/PgDn / arrows (when a block is focused) scroll the journal; the **visible** block becomes active (no jump to its first line). Click a block to focus it (`terminal_mouse: true`)
3. **Reading mode (no yank)**: once the view is scrolled up (`_follow_paused`) or a journal block holds focus, `add_block` only mounts the block: no scroll to the end, no focus stealing. Unpaused by scrolling back to the end (`_note_journal_scroll`) or by submitting a line (`_resume_journal_follow` in `on_input_submitted`). `_journal_reading()` / `_should_follow_journal_end()` / `_journal_at_end()` are the predicates; `_scroll_journal_wheel()` is the input-focused wheel path.
4. **Tab** from the input focuses the last journal block (`:h` / `:?` included)
5. **Focused block as pipe source**: `|` uses the focused block's stdout. `$OUT` is that block's last non-empty line, computed only when the command contains `$OUT` / `${OUT}`
6. **Bash aliases**: loaded at startup; `$1` positional substitution supported
7. **Background execution**: shell commands run in threads so the UI stays responsive
8. **Line-cursor (F2 / Enter on a focused block)**: copy or append individual output lines. **Ctrl+C** copies the whole input draft, or the focused journal block (same as F3).
9. **Bang-ref completion**: type `!` to list tags, then commands as `<id> tag[tid]`; Tab inserts `!tag[tid]`
10. **Console view (Ctrl+O)**: `action_show_console` suspends the TUI (`App.suspend`) so the real terminal is visible — that is where `> cmd` (`htop`/`vim`/`less`) output lives, in the scrollback. `_wait_console_key` prints a hint and waits for any key on `/dev/tty` in cbreak mode (falls back to an Enter on stdin without a controlling terminal), then the app resumes. `SuspendNotSupported` becomes an explicit journal error.
11. **`:llm` thinking animation**: the request runs in a worker thread (`_llm_worker`), so the block itself shows progress — `_start_thinking(block, timeout)` registers it in `self._thinking` (one `set_interval(THINKING_TICK=0.1)` timer for the app) and `_tick_thinking` repaints a braille spinner frame via `_thinking_markup` (`⠋ thinking… 3s / 60s`). `raw_stdout` is deliberately left at `[Consulting <provider>…]` as the stable "still waiting" marker (the `--demo all` tour waits on it); the animation only rewrites the rendered widget, so `_stop_thinking` in `_on_command_finished` (answer or error) is all the cleanup needed — the timer stops with the last waiting block.

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

Dev/test-only packages (`pytest`, `pytest-asyncio`, `pytest-timeout`) live in `requirements-dev.txt`. GitHub Actions runs the whole suite on every push/PR to `main` (`.github/workflows/tests.yml`).

## Key Configuration

Edit `settings.yml`:
- `max_lines`: Output buffer limit (default: 100000)
- `history_lines`: Default lines for `:h` (default: 20)
- `history_keep`: Recent history lines kept as a sequence (default: 500). Older prefix is uniqued on `:h compact`, or at startup if the file is longer than `2 × history_keep`. `0` disables.
- `database_tags_file`: SQLite filename (default: `mytags.db`)
- `command_timeout`: seconds; `0` = no timeout (default: 10)
- `terminal_mouse`: `true` — click focuses a block, wheel scrolls the journal; `false` — OS text selection (clicks do not focus)
- `theme`: Textual theme name (`textual-dark` default). `d` toggles dark/light and writes this key; `:theme nord` picks a named theme
- `check_updates`: `true` (default) — on start, compare `VERSION` with GitHub main. `:update` always checks. Tests set this to `false`. Proxy 407: `$PROXY_USER` / `$PROXY_PASS` in `.bashrc_term` (and `HTTPS_PROXY`).
- `k8s_completion`: `false` (default) — for `kubectl get <res> <Tab>` pull live resource names from the cluster (short `kubectl get <resource> -o name` timeout; soft fallback when kubectl/cluster is unavailable)
- `file_completion`: `auto` (default) | `paths` | `off` — when file/dir hints appear. `auto`: explicit paths (`./`, `/`, `~/`) plus a bare filename only after file-taking commands (`cat`, `vim`, `grep`, …; see `FILE_ARG_COMMANDS`), so subcommand CLIs (`kubectl get po`, `docker co`, `git ch`) do not flood hints with cwd entries. `paths`: only explicit paths and `cd`/`pushd`. `off`: no file hints.
- `history_completion`: `true` (default) — while typing a plain command, also offer matching lines from `history_*.txt` (newest first, `↺` marker; includes `@`/`>` commands, which are not in `session_history`). Tab/Enter inserts the full line; `false` leaves only Up/Down and `:h /text`.
- `md_dir`: base directory for `:rg` markdown search (e.g. an Obsidian vault); empty = cwd; `~` expands. `:rg <pattern> <dir>` overrides it for one query. Results are clickable `path:line` links opening in the md viewer at that line; `:rg <N>` opens result N (1-based). `:md <path>[#L<n>]` opens an explicit path at source line n (`md_viewer.resolve_md_path`); `:rg` / `:md` / `:send[!]` are recorded in `history_*.txt` (↑ / `:h`) via `RE_HISTORY_ONLY_QUERY` (with `:llm` / `:cht`), but never suggested.
- `md_render_lines` (default 1000): `:md` renders formatted markdown only below this many lines. Above it the file opens as raw source in the Line-API `OutputViewerScreen` (lazy `render_line`, instant) — the Textual `Markdown` widget mounts a widget per block, so 550 lines ≈ 1.3 s, 2200 ≈ 6 s, 13k ≈ 40 s. `start_line` keeps `#L<n>` working in the raw view. `y` copies the source path in **both** views (`HandbookMarkdownScreen` shows the clickable name via `[@click=screen.copy_path]`; `OutputViewerScreen` takes `source_path` and reports `No file path` for plain `:log`).
- `llm_providers.yml` (cwd): LLM providers for `:llm` — see `src/llm_providers.example.yml`. Keys come from the environment only (`$VAR` refs in headers/body)
- `cheat_sh_url` (default `https://cht.sh`) / `cheat_sh_options` (default `T` = no ANSI; add `Q` for no comments): base URL and query options for `:cht`
- `screensaver_idle`: seconds of no keys/clicks/scroll/mouse-move before the DevOps starfield (default 120). `0` disables. Tests set this to `0`. `:screensaver` starts it now; `:screensaver 0` / `:screensaver 120` change idle for this session. A forwarded `:send` command also wakes it (`_wake_screensaver()` from `_deliver_forwarded`) — external events do not touch its own key handlers.
- `screensaver_stars`: `true` (default) — flying dust/tokens. `false` — black canvas; clock/date, library ticker, and load/mem stay.
