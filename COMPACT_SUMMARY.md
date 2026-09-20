# IDvjPy_term — Compact Summary

TUI на Textual для запуска shell-команд с тегированной историей в SQLite. Версия: **v1.160**.

Запуск: `python3 app.py` (лаунчер; код в `src/`). Тесты: `python3 -m pytest tests/ -v`. Демо-запись: `python3 app.py --demo`.

Пустая БД: в журнале каталог seed. Клик по `--seed` вставляет команду во ввод; клик по `.md` или `:md файл.md` открывает справочник. Цепочки k8s: [`K8S_CHAINS.md`](K8S_CHAINS.md).

Параллельный порт: `Idivjopy_rust` (ratatui). Поведение ниже — про Python, если не сказано иное.

---

## Commands

| Prefix | Action |
|--------|--------|
| (none) | Execute shell command; a digit-leading line that fully parses as arithmetic/units is calculated locally (see below) |
| `> cmd` | Suspend TUI, run with a real TTY (`htop`, `vim`, `ssh`). On exit: import that shell's env and `$PWD` |
| `@ cmd` | Run without `command_timeout` (long non-TTY jobs; stdout captured) |
| `#tag cmd` | Save (literal text; refs `!tag[tid]` not expanded on save) |
| `# command` | Park in instance history + journal, do not run (`#` + space) |
| `#tag=` / `#tag=ID=` | Tag / command comment (ID = tid or global `<id>`) |
| `#tag+` / `#tag+ID` | Edit last / by tid |
| `#tag-` / `#tag-tid` | Soft-delete (strict `#tag-` only, not `-` inside cmd) |
| `#name--` / `#name!!` | Hide / restore a handbook's tags (`ansible`, `linux`, `k8s`, …) |
| `#tag!` / `#tag!tid` | Restore soft-deleted tag / command |
| `?` / `??` / `?tag` / `?tag[tid]` | Query tags / all / by tag / resolve preview. `?text` (2+ chars, no such tag) searches command text + comments across tags |
| `!tag[tid]` / `!N` | Insert command into input (does not run) |
| `!! …` | Assemble into input. `tag[tid]` → SQL; numeric id → `last_query_results` cache |
| `:` | `:?` `:? <тема>` (`calc` `run` `i` `md` `llm` `tags` `vars` `kctx` `send` `session` `import`) `:q` `:w` `:h` `:c` `:json` `:md` `:rg` `:i` `:cd` `:fm` `:term` `:ed` `:env` `:r` `:cmd` `:log` `:o` `:diff` `:name` `:kill` `:watch` `:llm` `:cht` `:g` `:/` `:n` `:N` `:stats` `:mv` `:export` `:import` `:alias` `:kctx` `:session` `:new` `:scope` `:send` `:send!` `:backup` `:welcome` `:screensaver` `:theme` `:lang` `:relang` `:playbook` `:run` `:update` |
| `\|` | Pipe focused/last block stdout (saved in history) |
| `$OUT` | On demand: last line of focused/last block (not stored) |
| `$VAR=val` | Set local env (also `$ VAR=val`); writes `.bashrc_term_<instance>` |
| `$VAR=@key` | Value from the focused/last finished block: line whose first token is `key` (`@last` = last line); `$$VAR=@key` → secret |
| `$$VAR=val` | Secret env: masked in the input line and journal (`****`); `secrets_<instance>.json` (0600), deleted on exit; never sent to `:llm`; use as `$VAR` |

Aliases from `~/.bashrc`: bodies with `$1` / `$2` / `$@` substitute args; otherwise the rest of the line is appended.

**Calculator (no prefix):** lines starting with a digit (or '(' / '-') are tried as math first, then shell (`7z …`, `(cd …)` unaffected). `512Mi + 20% in Gi` → 0.6Gi; `20% of 512Mi`, `512Mi*30 in Gi`, `1Gi/512Mi`, `500m in cores`, `2^10`, `524288 in Mi`. IPv4 subnets are handled the same way — `192.168.1.0/24` prints address/netmask/wildcard/network/broadcast/hosts like jodies.de/ipcalc, and `300 hosts` finds the smallest fitting prefix (/23). Memory: B, KB/MB/GB/TB (×1000), KiB/MiB/GiB/TiB and k8s Ki/Mi/Gi/Ti (×1024). % is relative to the left operand. Result block header is `calc:`.

Hotkeys: `Tab` input → output (Esc back); `F3` / `Ctrl+C` copy block (Ctrl+C in the input copies the draft); `F4` / `:kill` stop a running command (SIGTERM to the process group); `F5` JSON; `F6` simple output; `F2` line-cursor mode; `Shift+Insert`/`Ctrl+V` paste in the input (does not replace existing text); in line-cursor mode `Ctrl+V` appends the current line; `Ctrl+D` clears the input line; `PgUp`/`PgDn` scroll a page and activate the visible block (no jump to block start); click a block to focus it; `Up`/`Down` walk `history_<instance>.txt` in the input (typed text filters), journal scroll when a block is focused (line-by-line in line-cursor mode).

---

## Database read path

Details: `DATABASE.md`. Module: **`src/database_v2.py`**. File: `settings.yml` → `database_tags_file` (`mytags.db`).

- Two IDs: global `id` (`!1`, `!! 1`) and per-tag `tid` (`!deploy[1]`).
- Each call opens SQLite, queries, closes. Filter `deleted = 0`.
- In-memory cache `last_query_results`: `{global_id: command}`. Filled on start, every 5s, and replaced on `?`/`??`/`?tag`.
- `!! tag[tid]` hits DB immediately. `!! 1` needs cache (start load, `??`, or 5s reload).
- Tab completion: DB `command LIKE prefix%` (`deleted = 0`) + session history; path context uses cwd files only (not mixed with full commands). Typing `!file` / `!kube` lists tagged commands (`<id> tag[tid]  cmd`) and inserts `!tag[tid]` only. Hidden handbook tags (`#name--`) stay out of these lists; `??` / `?` show them under Hidden.
- Tag scope (`:scope`) filters what these lists show (see below) — `_visible_library` is a cached slice of the same rows. `_library` stays whole: run counting (`bump_command_usage`) and the `:llm` context still see hidden tags, so `:stats` and the usage sort never drift.

---

## Key features (current)

### Calculator (no prefix)
- A line starting with a digit (or '(' / '-') that fully parses as arithmetic/unit math is evaluated **locally** (no shell) and shown as a journal block with a `calc:` header — result goes to stdout, so ↑-repeat, `$OUT` and `|` work. Everything that does not parse (`7z …`, `(cd … && …)`, `2>/dev/null …`) still runs in the shell.
- Arithmetic: `+ - * / ^ ( )` — `1024*3`, `2^10`, `(512+512)*2`, `-5+8`. Percent scales the left operand: `512Mi + 20%` (increase by 20%), `512Mi - 15%`, `512Mi * 20%` (fraction), `2 + 10%`. `of` = fraction of a value: `20% of 512Mi`, `1/3 of 1Gi`, `20% of (512Mi + 1Gi)`.
- Memory: `B`; `K/M/G/T` = `KB/MB/GB/TB` (×1000); `Ki/Mi/Gi/Ti` = `KiB/MiB/GiB/TiB` (×1024); k8s-style attached or spaced: `512Mi`, `1.5 Gi`. Conversion: `512Mi in Gi`, `512Mi in MB`; bare `512Mi` prints the largest IEC unit + bytes. `524288 in Mi` treats the bare number as bytes. `1Gi/512Mi` → 2.
- IPv4 subnets (like jodies.de/ipcalc): `192.168.1.0/24`, `10.1.2.3/255.255.255.0`, or a bare `8.8.8.8` (classful default mask) prints Address · Netmask (= prefix) · Wildcard · Network/prefix · HostMin · HostMax · Broadcast · Hosts/Net with class/RFC1918 and binary columns. /31 = point-to-point, /32 = host route. Reverse task: `300 hosts` → the smallest prefix that fits (/23, 510 usable).
- CPU: `m` = milli-core, `cores`. `500m in cores` → 0.5 cores, `0.5 in m` → 500m.
- Engine: `src/calc.py` (tokenizer + recursive descent, no eval). Tests: `tests/test_calc.py`.

### Focus / journal
- `Tab` in the input focuses the last journal block in display order (`:h` / `:?` InfoBlocks included, not only the last CommandBlock). Completion list, if open, still consumes Tab to apply a candidate.
- `Esc` returns to input (in line-cursor mode: first Esc exits the mode, second Esc goes to input).
- `Ctrl+D` in the input clears the entire line (and hides the completion list).
- Completion list is **in-flow under the input** (not overlay); height grows with the candidate count and terminal size (6–24 rows, journal kept); footer always shows `n/n all` or `1–12 / 40 ↓28 more`. `can_focus = False`. PgUp/PgDn hide the list then move block focus.
- Input `select_on_focus = False`: returning from a block does not select-all, so paste/typing does not wipe the draft.

### Line-cursor mode (F2 / Enter on a focused block)
- **Off by default.** Focus a block (`Tab` / `PgUp`), then `Enter` or `F2` to turn it on. Current line is highlighted (`[reverse]` + left accent border).
- Off: `↑/↓` scroll the journal. On: `↑/↓` move by lines; `Home`/`End` first/last line. At the edge, arrows scroll the journal again.
- `Enter`: copy the current line (trailing spaces stripped; a leading `# ` from a parked history line is removed) to CLIPBOARD + PRIMARY + Textual/OSC 52, then jump to input (cursor at end, no selection).
- `Shift+Enter` / `Ctrl+V`: append the line to the input, separated by a space (same `# ` strip); stay in the block (can append several lines). If the terminal sends Shift+Enter as plain Enter, use **Ctrl+V**. While the input is focused, `Ctrl+V` still pastes from the clipboard. The app requests kitty CSI-u / xterm `modifyOtherKeys`.
- Many terminals deliver Ctrl+V as a **Paste** event rather than a `ctrl+v` key; line-cursor mode treats that Paste as append (same as the key).
- `Esc`: turn mode off, stay on the block. `F2`: toggle.
- Documented in `:?` under **Line-cursor mode**.

### `:h` history
- `:h [N]` shows the last N lines of `history_<instance>.txt` as **one** multiline `InfoBlock` (line-cursor can copy/append individual commands). Empty file → one info message.
- `:h /text` greps that file in the completion list (case-insensitive, newest first, duplicate lines merged). Esc then Enter dumps a journal block (`shown/total`, cap 50). Empty `:h /` still tails the file like `:h`.
- `:h compact` uniques the old prefix (last occurrence wins; lines also present in the tail are dropped from the prefix). The last `history_keep` lines (default 500, `settings.yml`) stay a verbatim sequence. Startup does this only when the file is longer than `2 × history_keep`. `history_keep: 0` disables.
- `↑`/`↓` in the input walk the instance history file plus session commands. Typed text freezes as a needle; empty input walks everything. Down past the newest line restores the draft.
- A typo is dropped from **both** stores: exit `127` **together with** `command not found` in stderr (`_is_command_not_found`) removes the line from the session walk and from `history_<instance>.txt` when the block finishes (`_forget_history_line` → `history_store.remove_history_file_line`, exclusive flock), so ↑/`:h`/hints never offer a command that does not exist — the error stays in the journal and `:o`. `bash -c 'exit 127'` (no such stderr) is not a typo. `history_forget_not_found: false` keeps such lines like any other command. Tests — `tests/test_history_typo.py`.
- `--instance-name=user1` uses `history_user1.txt` (and `.bashrc_term_user1`). Missing instance file is filled once from legacy `history.txt`.

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
- File hints are built from the **last** token (`_extract_path_token`) but applied to the token **under the caret** (`CommandLineInput._token_span`) — so both showing and applying require the caret to be in that last token (`_caret_in_last_token`): fixing the command name in `bar ~/f.txt` no longer pastes the path twice. The same question decides every hint — `CommandLineInput._items_match_caret` (`_selected_match_caret`): `replace_token` items (`!tag`, `?tag`, `:commands`) are built from the caret's token and are always applicable, while full commands from the DB and history (`↺`) replace the **whole line** and need the end of the line (`_caret_at_line_end`). `_show_completions` hides the list when the guard says no, Enter/Tab then just run the typed line. Tests — `tests/test_completion.py` (6: paths while editing the command word, Enter after the caret moved, completing in the last token, DB/history mid-line apply, whole-line hints mid-line).
- **Trailing space** (`ls   `): list hides; Enter runs the typed command, not a longer candidate (`ls -la`). Tab (without trailing space) still applies the candidate.
- After apply: space → Backspace → Enter must not duplicate the command.

### Bang-ref completion (`!file`, `!kube`)
- Type `!` to list tags (`[file, kube, log]` header + selectable rows). Tab inserts `!file` and then lists that tag's commands.
- Current token `!tag` / `!tag[` lists commands as `<139> file[1]  ls -la`.
- Tab/Enter insert only `!file[1]` (replace the `!tag` token, keep `#pack ` / `|` around it).
- Live preview line `→ ls -la | cat x` expands already-typed `!tag[tid]` while composing `#file !file[1] | !file[2]` (save still stores refs literally).
- Unique tag prefix (`!fi` when only `file` exists) lists that tag's commands. Several matching tags → pick a tag first.

### Clipboard / paste
- Copy (F3, line Enter, JSON path, **Ctrl+C**) writes system CLIPBOARD, X11/Wayland PRIMARY, and Textual internal + OSC 52 (so Shift+Insert in the terminal matches mouse paste). **Ctrl+C** in the input copies the whole draft; on a journal block it copies the block (same as F3).
- `Shift+Insert` / `Ctrl+V` in the input paste from those buffers and **do not replace** existing text (insert at cursor / end if a leftover selection exists). In line-cursor mode `Ctrl+V` / Paste appends the current journal line instead.

### Output
- `MAX_DISPLAY_LINES = 300` (UI). Full text stays in `raw_stdout`; F3 copies full output.
- `F6` toggles simple output (no Rich tags).
- `command_timeout` from `settings.yml` (default 10s; tests use 5s).
- `terminal_mouse: true` (default): click focuses a journal block, wheel scrolls the journal. `false` restores OS text selection (clicks do not focus).
- `theme` in `settings.yml` (default `textual-dark`). `d` toggles textual-dark / textual-light and saves. `:theme [name]` lists or sets a builtin theme (`nord`, `dracula`, …).

### Tags / vars
- `#` parser: strict regex so `ping -c` / `A=B` save instead of delete/comment.
- `$JSON` from viewer; `$NS` from `:i … -n`.
- `$OUT` is the last non-empty line of the focused (or last) command block, computed only when the typed command contains `$OUT` / `${OUT}`. Not written to `.bashrc_term` / `local_env`. `$OUT=` is rejected.
- Env files **merged**: `.bashrc_term_<instance>` wins on name clash; extras from `.bashrc_term` still load (`MYVAR` in `.bashrc_term` + `NS` in `_default`). Also accepts `VAR=val` without `export`.
- `:env` re-reads those files (and `~/.bashrc` aliases) in a running app.
- After `> cmd`, the same bash dumps its environment: new/changed exports overlay `local_env` / `os.environ` for this session (not written to `.bashrc_term`). `$PWD` is adopted if the TTY shell `cd`'d. Nested `> bash` then `export` inside that inner shell is not visible.
- `$VAR=val` writes the instance file (`.bashrc_term_default` by default).
- `$$VAR=val` — секрет: значение не показывается при вводе и в журнале, файл `secrets_<instance>.json` (0600) удаляется при выходе (только сессия), в LLM не уходит; в командах — `$VAR`.
- `$VAR=@key` / `$$VAR=@key` — значение из вывода блока (строка с первым токеном `key`; `@last` — последняя).
- `-n` without value → explicit error (no silent fallback).

### Tag scope (per session)
- `:scope add <group|tag>…` — keep only these (`only`), `:scope rm …` — hide these (`hide`), `:scope clear` / `:scope all` — drop the filter, bare `:scope` — the current state. A name is a handbook group (`linux`, `k8s`, `git`, docker, helm, … — the canonical `seed_groups` sets) or a single tag; comma and space both separate. An unknown name is an explicit error listing the groups; mixing `only` and `hide` in one scope is an explicit error (`ScopeModeError`), not a silent reset.
- **Scope is a view filter, not data.** It only touches lists and hints: `?` (tag list), `??` (all commands), `?text` (content search), `!`/Tab completions and the screensaver ticker. Explicit refs and commands — `?tag`, `!tag[tid]`, `!N`, `:run`, `:stats`, `:export`, `:alias`, `:mv`, `:send`, `#tag+/-`, `--seed`, `:relang`, `:backup` — ignore it, so saved chains and other windows' refs never break. `??` still records every id in `last_query_results`, so `!ID` works for a hidden tag too.
- **Per session, in a file.** `scope_<session>.json` in the data directory (not SQLite and not a DB table — the library is carried by `:export` / `backup_db.py`, the scope is a property of the window and must not travel). No file — no filter; a broken file — the filter is off and the journal says so. `:session NAME` reloads the scope of that name; the window/OSC title carries the marker (`IDvjPy_term · git · only git`). `:stats` covers the whole library and adds a reminder line while a scope is active.

### CLI
- Root `app.py` is a launcher; the TUI module is `src/app.py`. `--instance-name` is parsed in the launcher / `src/app.py` `__main__` (pytest imports `src/app.py` via `pythonpath = src`).
- Instance bashrc: `.bashrc_term_{instance}` in cwd. Template: `src/.bashrc_term.example`.
- Instance history: `history_{instance}.txt` in cwd. Legacy `history.txt` is copied once if the instance file is missing.
- Empty command DB (`has_live_commands` is false): welcome InfoBlock lists handbook seeds (journal starts at the top). Click `--seed` to insert; click `.md` or `:md` to open the viewer (`terminal_mouse: true`). A live DB is snapshotted to `backups/` before `--seed` replaces its tags (`:backup` does the same by hand).

---

## Tests

| File | Coverage |
|------|----------|
| `test_cmd.md` | Manual plan v1.106 (app v1.160) |
| `tests/test_session_mailbox.py` | Ящик `:send`: запись/вычерпывание/lock/0o600, `:send`/`:send!`/`*`, offline-очередь, маскировка секретов |
| `tests/test_session_registry.py` | Реестр сессий: `session_<имя>.pid` 0600 и свой pid, мёртвый pid (устаревший файл подчищается), битые/пустые файлы, `active_sessions`, `free_session_name` (наименьшее свободное среди активных, `taken`, файлы закрытых сессий имя не занимают), `unregister` не трогает чужую запись |
| `tests/test_db_transfer.py` | Перенос (`db_transfer`): канонический JSON и терпимое чтение старого вида, отказ от переноса глобальных `id`, merge/replace/`skip_existing`/`preserve_tid`, мягко удалённые строки, адресный CSV по tid, CSV комментариев, Markdown, пути `export_path`/`import_path` |
| `tests/test_backup_cli.py` | CLI `backup_db.py`: round-trip export/import, `--tag`, `list`, `--mode replace`/`--keep-tids`, CSV-правка, `backup`/`restore` (со снимком до), отказ от чужих `id`, тонкость обёртки `backup_db.sh` |
| `tests/test_version_bump.py` | `bump_version`: арифметика версии, обновление всех маркеров (включая `DATABASE.md`/`backup_db.md`), `--check`/`--dry-run`/`--set` |
| `tests/test_cmd_scenarios.py` | Sections of `test_cmd.md` (Pilot keypresses), alias `$1` |
| `tests/test_commands.py` | echo, history, vars, paste, Ctrl+D clear input, `:c`/`:q`, merge `.bashrc_term` + `_default`, `> cmd` TTY prefix, `:env`, empty-DB seed catalog, `:md`, `:backup`, `:fm`/`:term`, click `--seed` insert, history compact, `:session` |
| `tests/test_tags.py` | save with `-`/`=`, bang, delete, `#name--` / `#name!!`, `:export` одного тега и `:export * file.json` (JSON всей библиотеки) |
| `tests/test_cwd_prompt.py` | Приглашение строки ввода: `shorten_path` (`~`, хвост длинного пути, узкое окно), путь виден и обновляется после `cd`/`:cd`, плейсхолдера нет, клик по пути фокусирует ввод |
| `tests/test_completion.py` | Tab path, `ls ~/`, no `cat cat`, Tab→last journal block (`:h`/`:?`), line-cursor, trailing-space Enter, Shift+Enter/Ctrl+V/Paste append, `!tag` ref completion, click/PgUp visible-block focus |
| `tests/test_journal_follow.py` | Режим чтения: колесо вверх/фокус на блоке не уводит вид и фокус; возобновление при докрутке до низа и по Enter; `:send!` во время чтения |
| `tests/test_line_api_block.py` | Line API: включение ключом/`IDVJPY_LINE_BLOCKS`, вывод/высота/свёртка/курсор, инфоблоки действительно рисуются (`render_line`), выделение мышью по строкам + подсветка, клетка→символ (`meta['offset']`) остаётся точной |
| `tests/test_colon_commands.py` | Подсказки `:`-команд: покрытие всех `CMD_*`, фильтр по буквам, `:/` не перебивается, Tab вставляет без запуска, Enter на точном имени выполняет, ссылка — только на имени команды |
| `tests/test_tag_ref_click.py` | Клик по `!tag[tid]` в `??`: обычный — только вставка; Ctrl+клик и двойной клик — вставить и выполнить (как «Enter, Enter», без дубля ссылки); `!tag ` без tid и чужие ссылки не выполняются |
| `tests/test_help_topics.py` | Темы `:? <тема>`: уникальность и наличие текста на каждом языке, алиасы (в т.ч. русские слова), неизвестная тема — ошибка со списком тем, `:?calc` — подсказка пробела, оглавление `main` покрывает реестр, подсказки после `:? ` |
| `tests/test_secrets.py` | Секреты (20): ввод/показ маскируются, файл 0600 и удаление при выходе, `.bashrc_term`/history не видят значения, `:llm` (`$OUT` и контекст библиотеки), замороженная маскировка (`:watch`, `:o`, шапка `:log`, снятый/переопределённый секрет), чужие файлы секретов не удаляются, `:cmd` с `clear_clipboard_after_secret` |
| `tests/test_history_import.py` | Импорт истории (33): форматы (zsh extended/континуация, bash-метки, fish `\`/`\n`/кавычки, PSReadLine), распознавание zsh по содержимому, пути по linux/darwin/win32 + XDG/APPDATA, батч-запись и её ошибка, BOM/бинарь, `sh`→`ksh`, `:h import` в TUI (импорт, идемпотентность, «не найдено», нечитаемый источник, ошибка записи, лишние аргументы, незнакомая оболочка) |
| `tests/test_stylesheet.py` | Стили — `src/app.tcss`: путь и наличие файла, Textual-синтаксис (`$surface`, `dock`), отсутствие `app.css` в коде/упаковке, попадание в wheel |
| `tests/test_tag_query_hints.py` | Подсказки `?`: список тегов с числом команд и комментарием, фильтр, `??`/пробел не перебиваются, Tab без запуска, клик по строке выполняет запрос (путь по клику только вставляется), ссылка — только на `?tag` |
| `tests/test_themes.py` | Тема `matrix` (палитра, выбор из settings.yml/`:theme`, класс `matrix-mode` и зелёные рамки только у неё, сохранение между запусками) и мягкая подсветка блока в фокусе |
| `tests/test_json_viewer.py` | expand, search, F5 from focused cat, bracket keys, jq draft / `$JSON` |
| `tests/test_output_viewer.py` | Просмотр вывода (F7 / `:log`, 24): полный вывод без обрезки, выбор блока, прокрутка (стрелки без фильтра), поиск и подсветка строки целиком, фильтр «только совпадения» с исходными номерами, стрелки ↑/↓ по совпадениям в фильтре, Enter и Ctrl+C копируют подсвеченную строку (без поиска — явное «nothing selected»), Ctrl+C в поле поиска — текст поля |
| `tests/test_demo.py` | YAML `--demo` (short/full/ip/features/all, guardrails тура `all`), `:playbook`, `loop: N` / `loop: true` |
| `tests/test_gui_open.py` | `:fm` / `:term` argv by OS, `$FILEMAN` / `$TERMINAL`, detached spawn |
| `tests/test_screensaver.py` | starfield и матричный дождь (`MatrixRain`: падение/сброс, глифы, палитра), `:screensaver` и холст по `screensaver_matrix` / `:screensaver matrix|stars`, idle timer, key swallowed, `:send` снимает заставку |
| `tests/test_docker_stand.py` | Файлы docker-стенда: seed-скрипты в entrypoint, compose-том/TTY, Dockerfile, `.dockerignore`, job CI |
| `tests/test_tag_scope.py` | Область видимости тегов (модуль): `split_names` (пробелы/запятые), `classify` (группа побеждает одноимённый тег, известные/чужие имена), `only`/`hide`, `rm` на пустом → `hide`, `rm` из `only`, снятие последнего имени → пустой scope, смешение режимов → `ScopeModeError`, `split`/`describe`, round-trip `scope_<сессия>.json` и изоляция сессий, битый файл/нет файла |
| `tests/test_scope_command.py` | `:scope` в TUI (инвариант «фильтр — только списки»): `?`/`??`/`!`-подсказки скрывают чужие теги, `?tag`/`!tag[tid]`/`:stats` работают при скрытом теге, `??` с секцией Scope, `rm` → hide, `clear`/`all` возвращают всё (файл удалён), статус без аргументов, ошибки неизвестного имени и смешения режимов, маркер в заголовке, переживает restart, две сессии независимы, битый файл → фильтр выключен и сообщение, лента заставки уважает scope |
| `tests/test_ux_extras.py` | `:r N`, счётчик running в заголовке, `:alias`, консоль под TUI по Ctrl+O (suspend → ожидание клавиши → возврат, `SuspendNotSupported`) |

Isolated tmp cwd + test DB. `submit()` clears input, dismisses completion, then Enter.

---

## Files

| File | Purpose |
|------|---------|
| `app.py` | Launcher (`python3 app.py`) |
| `pyproject.toml` / `setup.py` / `MANIFEST.in` | Корневая сборка: `pip install .` / `uv tool install git+…` (build_py вкладывает `src/` в `packaging/idvjpy_boot`) |
| `packaging/` | pip-упаковка: `pyproject.toml`, boot-модуль `idvjpy_boot` (вложенные `src/`, `docs/`, `K8S_CHAINS.md` в sys.path) и `build_wheel.sh` |
| `docker/` | Демостенд для Docker: `Dockerfile` (alpine), `compose.yaml`, `entrypoint.sh` (шаблоны + однократный посев), `tui-smoke.py` (pty-смоук TUI), `README.md` |
| `.dockerignore` | Контекст сборки стенда: без `.git`, venv, `tests/`, `packaging/`, данных и сборок |
| `src/app.py` | TUI (`CommandRunner`), v1.160 |
| `bump_version.py` / `src/version_bump.py` | Синхронизация `VERSION` по всем файлам релиза (минор/`--set`, `--dry-run`, `--check`) |
| `src/calc.py` | Встроенный калькулятор без префикса: арифметика, `%`, `of`, единицы памяти/CPU (`src/ipcalc.py` — IPv4-сети и `300 hosts`) |
| `src/screensaver.py` | Idle overlay: «матричный дождь» (`MatrixRain`) или звёздное поле + flying clock/date + full-width green ticker + bottom help (left) and load/mem (right) (`:screensaver`; `screensaver_matrix` / `screensaver_stars`) |
| `src/database_v2.py` | SQLite tagged history — только примитивы БД (чтение/запись строк, теги, комментарии, `usage_stats`); перенос — в `src/db_transfer.py` |
| `src/db_transfer.py` | Единственная реализация переноса библиотеки: JSON (`export_json`/`import_json` — каноническая схема, терпимое чтение обоих исторических видов, глобальные `id` из файла не берутся, `skip_existing`/`preserve_tid`/`mode=replace`), CSV команд (адресно по тег+tid) и комментариев тегов, Markdown-каталог, `library_overview` для `list`. Для внешнего импорта: `loads_payload`, `payload_only_tag`, `run_mode` (разбор `run:`-директив для плана) и `plan_import`/`ImportPlan` — что изменит импорт, без записи (`--dry`, подтверждение `:import <url>`). Один код для TUI (`:export`/`:import`) и CLI |
| `src/net.py` | Общий сетевой слой (без Textual): HTTP(S) через stdlib + прокси с логином (`$PROXY_USER` / `$PROXY_PASS` → URL прокси), `open_url`, чистка пароля из текста ошибки, подсказка при «407». Для `:update`, `:llm`/`:cht` и `:import <url>` |
| `src/remote_source.py` | Внешний источник для `:import <url>`: только `https://` (иначе явный `--insecure`), лимит 2 МБ, таймаут 10 с, `safe_url` без userinfo, `looks_remote` (ссылка или локальный файл), `RemoteError` с готовым текстом для журнала |
| `src/backup_db.py` | Тонкий CLI над `db_transfer` (`backup_db.py` + обёртка `backup_db.sh`): `export`/`import`, `export-csv`/`import-csv`, `export-tags-csv`/`import-tags-csv`, `list`, `backup` (снимок SQLite + JSON + CSV), `restore` (со снимком до операции). Своей SQL-обвязки и своей JSON-схемы больше нет |
| `src/seed_groups.py` | Handbook name → tags for `#name--` / `#name!!` and for `:scope` groups |
| `src/tag_scope.py` | Область видимости тегов у сессии (`:scope`): `TagScope` (`mode` `only`/`hide` + группы `seed_groups` + отдельные теги): `matches`/`split`/`add`/`drop`/`label`/`describe`, `classify`, `split_names`, `ScopeModeError`; файл `scope_<сессия>.json` в data-каталоге (нет файла — нет фильтра, битый — фильтр выключен и явное сообщение). Фильтр — только списки и подсказки; БД не трогает |
| `src/seed_catalog.py` | Empty-DB welcome catalog (click `--seed` / `.md`); texts from `catalog.*` (`locales/<lang>/seed.yml`), commands/scripts never translated |
| `src/md_viewer.py` | Modal Markdown viewer (`:md`, welcome links). Handbook lookup is language-aware: `handbook_md_path(name, lang)` prefers `docs/<lang>/NAME`, then `docs/NAME`, then `NAME` (repo root / cwd) — a language without its own copy gets the base handbook |
| `src/k8s_complete.py` | Имена ресурсов k8s из живого кластера (`kubectl get`) |
| `src/update_check.py` | Compare `VERSION` with GitHub main (`:update`) |
| `src/data_dirs.py` | Data-каталог: `--data-dir` / `$IDVJPY_DATA_DIR` / portable / OS default |
| `src/kctx_store.py` | Кластерный журнал (`kctx.json` в data-dir): снимки переменных из `kctx_vars` по кластерам, парсер `parse_kctx_vars` |
| `src/llm_client.py` | LLM-запросы по `llm_providers.yml` (`:llm`); `answer_language` провайдера, а при `auto`/отсутствии — имя языка UI (`llm.answer_language` из локали; `off`/`none`/`no`/`false`/`0` отключают правило) |
| `src/llm_context.py` | Контекст приложения для LLM: шпаргалка префиксов + выжимка тегов/команд (`:llm ask`, ключ `app_context`) |
| `src/llm_providers/<lang>.yml` | Локализованные шаблоны провайдеров LLM (en/ru/zh): язык файла задаёт `answer_language` и текст офлайн-заглушки (префикс `[offline]` общий) |
| `src/settings/<lang>.yml` | Локализованные шаблоны настроек (en/ru/zh, ключи/значения синхронны) для первого запуска в новом data-каталоге |
| `src/gui_open.py` | `:fm` / `:term` detached file manager / terminal |
| `src/editor_open.py` | Внешний редактор для `:ed` (settings.yml `editor:` → `$VISUAL`/`$EDITOR` → системный; временные копии для `$OUT`/`$BLOCK`) |
| `src/json_viewer.py` | JSON tree modal |
| `src/output_viewer.py` | Просмотр полного вывода (`:log` / F7) на Line API: ленивый `render_line` без обрезки в 300 строк, поиск `/` → Enter + `n`/`N`, подсветка строки совпадения целиком (`outputview--hit` выбирается в `render_line`), `f` — только совпадения (в этом режиме по ним ходят и стрелки ↑/↓), Enter/Ctrl+C копируют подсвеченную строку (`copy_shortcut` — Ctrl+C у приложения `priority=True` и до виджетов не доходит), `y` — путь файла-источника |
| `src/ingress_analyzer.py` | `:i` k8s |
| `src/command_parser_v2.py` | `!tag[tid]` / `!ID` assembly |
| `src/history_store.py` | `history_<instance>.txt` append/read/compact, file locks; `append_history_file_lines` — пачка под одним lock’ом без дублей (импорт) и с явной ошибкой (`AppendResult.added/error`: занятый файл не пишем молча) |
| `src/history_import.py` | Импорт истории оболочки (`:h import`): поиск файлов по ОС и `$HISTFILE` (fish/pwsh — XDG-каталог на всех ОС, nushell — системный, на win32 только Windows-пути), разбор по содержимому (zsh extended + континуация `\`+newline, bash-метки, fish `\`/`\n` однопроходно, PSReadLine/nushell), хвост 4 МБ у больших файлов, BOM/бинарь, `sh` → `ksh` |
| `src/session_mailbox.py` | Пересылка команд между сессиями (`:send`): `inbox_<instance>.jsonl` 0600, append под lock / drain |
| `src/session_registry.py` | Реестр активных сессий — `session_<instance>.pid` 0600: автоимя `:new` = наименьшее свободное `sN` среди работающих окон (устаревшие pid-файлы подчищаются) |
| `src/help_texts.py` | Реестр справки `:?`: `HELP_TEXTS` + `HELP_TOPICS` (канонические имена тем → текст: `calc`, `run`, `i`, `md`, `llm`, `tags`, `vars`, `kctx`, `send`, `session`, `import`), `help_topic()` (имена и алиасы → `i18n.text()`) — файлы `src/locales/help/<lang>/{main,runbook,calc,ingress,llm,tags,vars,md,kctx,send,session,import}.txt` (`en` — источник правды) |
| `src/relang.py` | `:relang [code]` — перевод комментариев **уже засеянной** библиотеки (подписи тегов и подсказки команд) после смены языка, без повторного `--seed`: `_collect()` собирает канонический индекс из `seed_linux_commands` / `seed_k8s_chains` / `seed_git` / `seed_ops`, строка матчится по `(тег, команда)` (linux-дополнения — по `tid - 1`), правленый руками комментарий не трогается, снимок БД в `backups/` до записи; CLI `python3 src/relang.py --lang ru`. Тесты: `tests/test_relang.py` |
| `src/i18n.py` | UI-language core: catalogue lookup (`t`/`tlist`) and long texts (`text("main")` → `locales/help/<lang>/*.txt`), language resolution (`--lang` → `$IDVJPY_LANG` → `settings.yml: language` → `en`; `auto` follows `$LANG`). Catalogues: `src/locales/<lang>.yml` plus parts in `src/locales/<lang>/*.yml` (`screensaver`, `seed`), deep-merged; `en` is the source of truth; missing keys fall back to `en`, unknown keys return themselves. Tests: `tests/test_i18n.py` (keys are strings — YAML reads bare `off`/`n`/`N` as bool; every language has all help texts and all `catalog.desc.*`) |
| `src/example_config.py` | Локализованные шаблоны личных файлов: `available_settings_languages`/`available_llm_providers_languages`, `settings_example_path(lang)`, `llm_providers_example_path(lang)` (откат на `en`), `detect_language(explicit)` — `--lang` → `$IDVJPY_LANG` → системная локаль (auto) → `en`; шаблоны — `src/settings/<lang>.yml` и `src/llm_providers/<lang>.yml` |
| `src/ansi_output.py` | ANSI/ESC в выводе команд: SGR → цвета (`to_markup`), плоский текст без кодов (`to_plain`), терминальный `\r` (`collapse_carriage_returns`); ключ `ansi_colors` |
| `src/runbook.py` | `:run` — полуавтоматический прогон цепочки: шаги `auto`/`manual`/`prompt`, директивы `run:` в комментариях тега, план из YAML (`note:` для тега без единой директивы) |
| `src/seed_*.py` | Handbook seeds (linux, k8s, git, ops, …) |
| `src/app.tcss` | Styles (JSON viewer, line-nav border, block focus); Textual CSS — расширение `.tcss`, чтобы редакторы не линтовали его браузерным CSS |
| `settings.yml` | Личные настройки — **не в git** (`.gitignore`), создаётся копией `src/settings/<lang>.yml` (язык `auto`) при первом запуске в новом data-каталоге |
| `src/settings/<lang>.yml` | Локализованные шаблоны настроек: ключи и значения синхронны, различаются только комментарии; `editor: nano`, `language: auto` |
| `docs/<lang>/README.md` | Переводы README (en/zh); корневой `README.md` — русский, но маркер версии (`**IDvjPy_term** vX.YY — …`) синхронизирует `bump_version` во всех трёх |
| `K8S_CHAINS.md` | k8s investigation overview |
| `docs/SEED_*_COMMANDS.md` | Canonical tids per handbook |
| `DATABASE.md` | How commands are read from SQLite |
| `test_cmd.md` | Manual test script |

---

## v1.160

- **То же правило — и для остальных подсказок.** В v1.159 файловые подсказки перестали менять чужое слово; оставался тот же рассинхрон у кандидатов, подменяющих строку **целиком** (полные команды из БД и `↺` из истории): правка середины строки могла затираться целой командой (`echo mid-line` → `echo mid-line-long`). Теперь место вставки и место курсора сверяет один метод `CommandLineInput._items_match_caret` (`_selected_match_caret`): файловые — последний токен, `replace_token`-кандидаты (`!tag`/`?tag`/`:`) — токен под курсором (всегда можно), целая строка — только когда курсор в её конце (`_caret_at_line_end`). `_show_completions` прячет список, Enter/Tab такой пункт не применяют (строка выполняется как есть). Классификация — по уже существующим признакам пункта (`is_path` / `replace_token`), т.е. по тому же критерию, которым живёт вставка (`_should_replace_last_token`). Тесты: `tests/test_completion.py` (+3: применение целой команды из БД и `↺` после ухода курсора в середину, показ списка целых строк при правке середины; проверено, что без гейта все три падают).

## v1.159

- **Файловые подсказки больше не меняют чужое слово.** Симптом: `bar ~/.config/idvjpy/history_default.txt` (опечатка) → правка имени команды в этой же строке → список предлагал путь, а Enter вставлял его в первое слово: `~/…txt ~/…txt`. Причина — рассинхрон: кандидаты строятся по **последнему** токену (`_extract_path_token`), а вставка идёт в токен **под курсором** (`_token_span`). Теперь оба шага требуют, чтобы курсор был в последнем токене (`CommandLineInput._caret_in_last_token`): список не показывается (`_show_completions`), а Enter/Tab его не применяют (курсор можно увести стрелками уже с открытым списком). Кандидаты из БД/истории не тронуты — у них своя семантика («полная команда заменяет строку»). Тесты: `tests/test_completion.py` (+3; проверено, что без охраны два из них падают).
- **Ключ `history_forget_not_found`.** Поведение v1.127 (опечатка `command not found` + 127 убирается из `history_*.txt` и из ленты ↑) стало настраиваемым: `true` (по умолчанию — как раньше), `false` — такие строки хранятся как любые другие (команда есть только на другой машине, в другом окружении). Ключ — в шаблоне `src/settings/<lang>.yml` рядом с `history_completion`; «опечатка» по-прежнему только 127 **вместе** с `command not found` в stderr (`bash -c 'exit 127'` остаётся). Тесты: `tests/test_history_typo.py` (+1), `tests/test_data_dirs.py` (ключ в `EXPECTED_KEYS`).

## v1.158

- **F7: Enter и Ctrl+C копируют подсвеченную строку.** В просмотрщике вывода не было способа взять одну строку: «выделенная» строка — это строка текущего совпадения (`outputview--hit`) — её ставит `/`, по ней ходят `n`/`N`. Теперь Enter и Ctrl+C кладут её в буфер (подзаголовок `Copied line N: …`), экран не закрывается (в F2 Enter копирует и уводит во ввод — в модалке это было бы неожиданно). Без поиска выделять нечего — явное `Nothing selected: / text, Enter — then Enter / Ctrl+C copies the line`, а не первая строка наугад. Ctrl+C — `priority=True` у приложения, такие привязки `App.on_event` проверяет раньше виджетов, поэтому модалка его сама перехватить не могла: `CommandRunner.action_copy_input_or_block` теперь спрашивает активный экран методом-хуком `copy_shortcut` (сразу после выделения мышью). В поле поиска Ctrl+C копирует текст поля, остальные экраны хука не имеют — поведение не тронуто.
- **F7: стрелки ходят по совпадениям в режиме фильтра.** При включённом `f` на экране одни совпадения, и построчная прокрутка бессмысленна: `↑` / `↓` ведут подсветку к соседнему совпадению (по кругу, как `n` / `N`), подзаголовок подсказывает `↑↓ / n N — matches`. Реализовано в `OutputView.on_key` (виджету с фокусом стрелки иначе забирает `ScrollableContainer`) и только на успешный шаг: без фильтра стрелки остаются обычной прокруткой, `PgUp`/`PgDn` работают всегда. Заодно `:log` в справке обещает то же самое.
- **Подсветка блока в фокусе в два раза тусклее.** `background: $primary 25%` читалось ярко — теперь `12%`: прирост яркости над фоном блока (замер в textual-dark) 18.7 → **8.8** (сплошной `$primary-darken-1` давал ~65). Тест `test_block_focus_highlight_is_soft` получил верхнюю границу `lift < 15` вместо `< 40` — сторож против возврата к слепящей заливке.

Тесты: `tests/test_output_viewer.py` (24: +4 — Enter/Ctrl+C копируют подсвеченную строку, без поиска явное сообщение, Ctrl+C в поле поиска копирует поле, стрелки по совпадениям в фильтре и обычная прокрутка без него), `tests/test_themes.py`, `tests/test_commands.py`/`test_paste_right_click.py` (Ctrl+C не сломан), `tests/test_help_topics.py`, `tests/test_i18n.py`.

## v1.157

- **`:scope` — область видимости тегов у сессии.** Два окна делят одну БД, но `session git` нужен свой фокус: `:scope add git` оставляет в списках только набор git, `:scope rm k8s` — скрывает k8s, `:scope clear` / `:scope all` — снимает фильтр, без аргумента — что сейчас. Имя — группа хендбука (`linux`, `k8s`, `git`, docker, helm, … — канонические наборы `seed_groups`) или отдельный тег; неизвестное имя — явная ошибка со списком групп, а смешивание `only` и `hide` — явная ошибка (`ScopeModeError`), а не тихий сброс. Модуль — `src/tag_scope.py`.
- **Фильтр только представления.** Scope влияет на списки и подсказки (`?`, `??`, `?text`, подсказки `!`/Tab, лента заставки). Явные адреса и команды (`?tag`, `!tag[tid]`, `!N`, `:run`, `:stats`, `:export`, `:alias`, `:mv`, `:send`, `#tag+/-`, `--seed`, `:relang`, `:backup`) работают как раньше — сохранённые цепочки и чужие ссылки не ломаются; `??` по-прежнему кладёт все id в `last_query_results`, поэтому `!ID` работает и для скрытого тега. Кэш `_library` остаётся полным (учёт запусков и контекст `:llm`), а срез `_visible_library` строится только для списков — `:stats` и сортировка по частоте не «плавают».
- **Свой файл у каждой сессии.** `scope_<сессия>.json` в каталоге данных: в SQLite не пишется (библиотеку носят через `:export` / `backup_db.py`, а область видимости — свойство окна). Нет файла — нет фильтра; битый файл — фильтр выключен и в журнале явное сообщение. `:session NAME` перечитывает scope этого имени; заголовок окна/вкладки несёт маркер `IDvjPy_term · git · only git`. В `:stats` при активном scope добавляется строка-напоминание (отчёт всё равно про всю библиотеку).
- **Попутно:** в `_handle_stats_command` переменная цикла `t` затеняла функцию локали `t()` — переименована в `stat` (без этого новое сообщение падало с `'dict' object is not callable`).

## v1.156

- **Fix: правый клик больше не тормозит.** Замер показал, что сама вставка стоит 0.3 мс, а «тормозит» клик: Textual на MouseDown сам фокусирует виджет под мышью (`Screen._forward_event` → `get_focusable_widget_at`), поэтому правый клик по журналу уводил фокус на блок, а вставка возвращала его в строку — два перефокуса на каждое нажатие. Теперь `TermScreen` отвечает `None` из `get_focusable_widget_at` и `get_widget_and_offset_at`, пока пересылается не-левое событие: фокус не трогается, и клетка→символ для кнопки, которая не выделяет, не ищется. Тест: `test_right_click_on_block_does_not_steal_focus`.
- **Переносы строк в вставке больше не ломают строку ввода.** Поле однострочное (Textual `Input`), а из буфера приезжает многострочный текст — раньше это ломало вёрстку, а Paste-событие терминала вообще теряло всё после первой строки (`Input._on_paste`). Теперь все пути (правый клик, Ctrl+V/Shift+Insert, Paste от терминала) идут через один `CommandRunner.handle_paste`, а `paste_line` превращает `\r\n`/`\r`/`\n` (с окрестными пробелами) в один пробел — многострочная команда вставляется одной строкой целиком. `CommandLineInput._on_paste` отдаёт событие приложению и обнуляет `event.text`: Textual диспетчерит `_on_*` по всему MRO, и базовая `Input._on_paste` иначе вставила бы первую строку второй раз.
- **Длинная строка видна целиком: превью под полем.** Поле прокручивает длинное значение под курсором — видно был только хвост. `#input-preview` (серый, перенос по словам, до `INPUT_PREVIEW_MAX_ROWS` строк, лишнее — `…`) показывает всю строку; короткая строка превью не показывает, секретная — никогда (в поле она и так замаскирована), живые `$$`-значения в превью маскируются (`_mask_secrets`). Обновляется в `_watch_value`, `on_resize` и после вставки; строка ввода стала контейнером `#input-row` → `#input-line` + превью.
- **Тесты:** `tests/test_cwd_prompt.py` (+7: `paste_line`/`wrap_display_line`, превью длинной строки целиком, скрытие для секретов и маскировка `$$`, Paste-событие не теряет строки, правый клик и Ctrl+V дают одно и то же) и `tests/test_paste_right_click.py` (+1 про фокус). Доки: README (ru/en/zh), `:?` main.txt (en/ru/zh), `test_cmd.md` (секция 53), `CLAUDE.md`.

## v1.155

- **Fix: правый клик больше не затирает буфер и не мешает вставить выделенное.** Симптомы были такие: выделяешь текст в выводе, сразу правый клик — в строку ничего не вставляется; правый клик в пустой строке — и в буфере (а потом и при Ctrl+V) оказывается `~ ❯` из приглашения с путём. Причина — Textual: `Screen._forward_event` заводит выделение на **любую** кнопку MouseDown (без проверки кнопки), а на отпускании приложение копировало в буфер «выделенное» — достаточно было дрогнуть мышью на клетку, чтобы в буфер ушёл случайный кусок под курсором (в строке ввода — приглашение `~ ❯`), затирая выделенное человеком.
- **Свой экран `TermScreen`** (`CommandRunner.get_default_screen`): пока пересылается не-левое событие мыши, `allow_select` возвращает False — выделение не заводится вообще; плюс на это время обнуляется `Screen._mouse_down_offset`, чтобы MouseUp правого клика не снял уже сделанное выделение. `on_text_selected` копирует только после левой кнопки (`_last_mouse_button`, 0 — тестовый `Pilot`, 1 — реальный терминал). Итог: выделенное мышью копируется при отпускании (как раньше, `tests/test_mouse_selection.py`), правый клик вставляет именно его и ничего не портит; подсветку снимает уже сама вставка — строка ввода получает фокус, а `Input._watch_selection` в Textual чистит выделение экрана (текст при этом остаётся в буфере).
- Тесты: в `tests/test_paste_right_click.py` добавлены «выделил → правый клик вставил, буфер не перезаписан» (11 всего), «пустой буфер не снимает выделение» и «дрогнувший правый клик не кладёт `~ ❯` в буфер». Доки: README (ru/en/zh), `:?` main.txt (en/ru/zh), `test_cmd.md` (секция 53), `CLAUDE.md` (pitfall про выделение).

## v1.154

- **Правый клик — вставка из буфера, где бы ни был фокус.** Мышь — ускорение (клавиатурный путь Ctrl+V / Shift+Insert не меняется): правый клик по журналу, списку подсказок или пустой области кладёт текст буфера в строку ввода, не требуя сначала попасть в неё курсором. `CommandRunner.on_mouse_down` (он же продлевает простой заставки для любой кнопки) при `button == 3` зовёт `_paste_clipboard_into_input` — тот же путь, что у Ctrl+V: вставка в позицию курсора, при выделении — в конец, `clear_clipboard_after_secret` срабатывает, пустой буфер — подсказка `clipboard.empty` (новый ключ en/ru/zh). В построчном режиме (F2 / `:log`) Ctrl+V по-прежнему дописывает текущую строку, а правый клик всегда вставляет буфер; на модалках (JSON, markdown, просмотр) вставки нет — они сами едят мышь.
- **Правый клик не выполняет ссылки.** Брокер `@click` в Textual не различает кнопки, поэтому правый клик по `--seed` / `.md` / `:команде` / `?tag` в подсказках ещё и запускал бы действие и затирал только что вставленный текст. Отсечка — override `CommandRunner._broker_event` (клик с `button != 1` действию не отдаётся); обработчики `on_click` у `LineNavigable`, `CompletionList` и приглашения с путём тоже игнорируют не-левую кнопку, чтобы фокус/курсор не прыгали.
- **Тесты:** `tests/test_paste_right_click.py` (8: вставка без фокуса в строке, в позицию курсора, ссылка правым кликом не выполняется, пункт подсказки не выбирается, блок не перехватывает фокус, пустой буфер, очистка буфера после секрета, модалка) + `tests/conftest.py::right_click` (в `pilot.click` кнопки нет). Доки: README (ru/en/zh — таблицы клавиш), `:?` (main.txt en/ru/zh), `test_cmd.md` (секция 53), `CLAUDE.md`.

## v1.153

- **В подсказках пути каталог и файл больше не выглядят одинаково.** Каталог рисуется ссылкой — с подчёркиванием, как команды и теги, — а файл остаётся обычным текстом: при наборе `cd` видно, куда можно войти, а где уже файл. Это упиралось в ограничение Textual: любой `@click`-span получает стиль ссылки темы (`link-style`, подчёркивание), и по-span его не убрать. Поэтому `CompletionItem` получил флаги `is_path` / `is_dir` (`is_link`), файловые строки рисуются без `@click`, а их клик ловит новый `CompletionList.on_click` → `index_at_y(event.y)` (рамка + строка `preview` учитываются) → `action_pick_completion`. Клик по файлу по-прежнему только вставляет, Tab/Enter — как раньше.
- **Один источник пунктов подсказок.** `CommandRunner.get_input_completion_items` отдаёт `CompletionItem` (его использует список), `get_completion_candidates` остался строковой обёрткой (его читают тесты и внешние вызовы), `_get_file_completion_candidates` теперь возвращает пункты с тем же `isdir`, который и раньше вычислял по каждому имени, — дублирующего `stat`/`listdir` нет.
- Тесты: `test_completion.py::test_path_hints_underline_dirs_not_files` (каталог — ссылка и подчёркнут, файл — нет), `test_tag_query_hints.py::test_completion_click_without_run_only_inserts` (клик по файлу вставляет) + helper `completion_underline_spans` в `conftest.py`. Доки: README (ru/en/zh), `test_cmd.md` (секция 37), `CLAUDE.md`.

## v1.152

- **Текущий каталог видно всегда: серое приглашение в строке ввода.** Плейсхолдер «Enter command» заменён путём (`~/проект ❯`) — как в терминале: видно, где ты, и пока строка пуста, и пока в неё набирают команду. Путь укорачивается (`shorten_path`: `~` вместо дома; длинный — хвостом, как `%3~` в zsh, не больше трети ширины окна), полный путь по-прежнему в шапке блока. Строка ввода стала контейнером `#input-row`: рамка у контейнера (подсветка фокуса — `:focus-within`), приглашение `#cwd-prompt` — серым (`$text-muted`), поле `#command-input` — без своей рамки. Обновляется в `on_mount`, `on_resize` (лимит длины зависит от ширины) и там, где меняется cwd: `cd` / `:cd` и `_adopt_tty_cwd` (после `> cmd` оболочка могла уехать в другой каталог). Клик по приглашению возвращает фокус в строку (мышь — ускорение). Тесты: `tests/test_cwd_prompt.py` (7).
- **Сопутствующее:** `CLAUDE.md` (устройство строки ввода), README (ru/en/zh — у `:cd`), `test_cmd.md` (секция 25).

## v1.151

- **`:export * file.json` — вся библиотека каноническим JSON.** `:export *` с расширением `.json` пишет тот же файл, что `backup_db.py export` без `--tag` (`tag_filter` пуст — при импорте он идёт как «обновить», а не как файл одного тега), `.md` и без аргумента — по-прежнему Markdown-каталог. Это закрывает дыру в публикации общей библиотеки: файл для `library_url` теперь делает сама TUI, без CLI. Usage и подсказка обновлены (en/ru/zh), тесты — `test_export_star_json_is_whole_library`, `test_export_usage_lists_both_library_formats`.
- **Fix: доки больше не зовут лаунчер `backup_db.py` «из ниоткуда».** `python3 backup_db.py export library.json` работает только из каталога репозитория, а данные (и `backups/`) живут в каталоге данных: при запуске алиасом из `~` такая строка падала на `can't open file '…/backup_db.py': [Errno 2] No such file or directory`. В `:? import`, README (ru/en/zh), `backup_db.md`, `test_cmd.md` (секции 25 и 52) теперь есть и TUI-путь (`:export * library.json`), и вызов лаунчера по пути из каталога данных с пометкой, что `settings.yml` / `backups/` берутся из текущего каталога.

## v1.150

- **Внешний импорт библиотеки по ссылке: `:import <url>`.** Библиотеку тегов можно взять с общего https-хоста: `:import https://…` скачивает канонический JSON (его делает `backup_db.py export` или `backup`), показывает **план изменений** — сколько строк добавится, что пропустится, какие теги новые, и отдельно предупреждает про `run:`-директивы (шаги `run:auto` выполнит `:run` без подтверждения) — и подставляет во ввод готовую строку `:import <url> --yes`: импорт начинается только по второму Enter (принцип «собрал — потом запустил», без модалки Y/n). Флаги: `--dry` — только план, `--yes` — без подтверждения, `--insecure` — разрешить `http://` (по умолчанию только `https://`). `:import` без аргумента берёт статичную ссылку `library_url` из `settings.yml` (новый ключ, пусто — выключено). Файл всей библиотеки импортируется как «обновить» (занятая пара `(тег, tid)` пропускается), файл одного тега — как «добавить» с новыми `tid`.
- **Общий сетевой слой `src/net.py`.** Прокси с логином (`$PROXY_USER` / `$PROXY_PASS`, `inject_proxy_userinfo`, `proxy_handler_map`), чистка пароля из текста ошибки (`redact_proxy_secrets`) и подсказка при «407» жили в `update_check.py` — теперь один модуль для `:update`, `:llm` / `:cht` и `:import <url>` (`format_fetch_error`). Сеть в тестах не трогается: транспорт `:import` проверяется на фейковом `net.open_url` (`tests/test_net.py` + `tests/test_remote_import.py`, 19).
- **Предохранители внешнего источника (`src/remote_source.py`).** Только `https://` (иначе явный `--insecure`), лимит 2 МБ с проверкой в цикле чтения, таймаут 10 с, `safe_url` не пускает userinfo из URL в журнал, `looks_remote` отличает ссылку от локального файла. Загрузка — в фоновом потоке (UI не блокируется), payload со значением живого `$$`-секрета отклоняется, локальный `--dry` работает так же, как для ссылки. План считается без записи: `db_transfer.plan_import` / `ImportPlan` + `loads_payload` / `payload_only_tag` / `run_mode` (грамматика `run:` — из `runbook`, сверяется тестом).
- **Тема справки `:? import`** (en/ru/zh) + псевдонимы `export` / `экспорт` / `импорт` / `библиотека`; в `:?` — короткая строка про `:import <file|url>` и ссылка на тему. Доки: README (ru/en/zh — команда, строки таблицы «что чем делать» и ключ `library_url`), `backup_db.md` (раздел про импорт по ссылке + таблица «Связь с TUI»), `CLAUDE.md` (модули `net` / `remote_source`, `plan_import`), `AGENTS.md` (принцип про сеть и `:import <url>`), `test_cmd.md` (секция 52 — локальный стенд и все флаги), `src/settings/<lang>.yml`.

## v1.149

- **Fix: `--lang` не работал у установленного пакета.** `packaging/idvjpy_boot:main()` не вызывал `apply_language(args.lang)` — корневой `python3 app.py --lang ru` язык применял, а `idvjpy --lang ru` молча игнорировал флаг. Сторож — `tests/test_packaging_root.py::test_entry_points_do_the_same_bootstrap` (AST-сверка шагов запуска: `parse_arguments`, `apply_instance_name`, `apply_language`, `load_demo_for_cli`, `CommandRunner`, `run`).
- **Справочники `:md` теперь едут в пакет.** `handbook_md_path` ищет markdown в `cwd` и в `REPO_ROOT`, а у установленного пакета `REPO_ROOT` — каталог `idvjpy_boot/`, где `docs/` не было: `:md SEED_*.md` и `.md`-ссылки из `:welcome` у pip/uv-установки не открывались. Теперь `build_wheel.sh` и корневой `setup.py` (`build_py`) вкладывают рядом с `src/` ещё `docs/` и `K8S_CHAINS.md`, `package-data` обоих `pyproject.toml` и `MANIFEST.in` их везут (wheel 190 → 270 файлов), а `:md` находит справочник языка (`docs/<lang>/NAME` → `docs/NAME` → `NAME`) без правки кода. Проверено распаковкой wheel: `SEED_GIT_COMMANDS.md` резолвится в `docs/en/…` и `docs/zh/…`, `K8S_CHAINS.md` — в корень пакета. Сторожа: `test_package_data_covers_handbooks`, `test_handbook_resolves_from_package_root` (симуляция раскладки пакета).
- **`setup.sh` стал устойчивым:** `set -euo pipefail`, `cd` в корень репозитория, явная проверка Python 3.12+ (с текущей версией в сообщении), повторный запуск на существующем `.venv` не пересоздаёт окружение, `pip` — через `python -m pip`, в конце — подсказки про dev-зависимости, сиды и каталог данных. Прогон без сети доходит ровно до `pip install`.

## v1.148

- **Один механизм переноса базы вместо трёх.** Анализ показал 12 точек входа для экспорта/импорта, из которых две были настоящими дублями: JSON-перенос был реализован и в TUI (`database_v2.export_tag_to_file`/`import_tag_from_file`), и в CLI (`backup_db.export_db`/`import_db` — со своей SQL-обвязкой, своим `CREATE TABLE` и своим набором полей при **том же** `schema_version: "v2"`), а `backup_db.sh` повторял команды CLI через `ls|grep|sed`. Теперь формат один — `src/db_transfer.py`: канонический JSON (`export_date`, `total_*`, `tag_comments`, `commands` с `id`/`timestamp`/`deleted`) с терпимым чтением обоих исторических видов, CSV команд (адресно по паре тег+tid) и комментариев тегов, Markdown-каталог, `library_overview` для `list`. TUI (`:export`/`:export *`/`:import`) и CLI импортируют его, `database_v2` вернулся к роли «только примитивы БД».
- **Безопасный импорт.** Глобальные `id` из файла больше **никогда** не переносятся: раньше CLI-импорт вставлял их как есть и при конфликте делал UPDATE существующей строки — чужой `id` мог затереть другую команду. Теперь по умолчанию каждая строка получает новый `tid`, `preserve_tid` управляется `--keep-tids` только для `tid`, мягко удалённые строки при импорте пропускаются, а точный слепок делается SQLite-снимком. TUI-импорт сохранил прежнее поведение (новые `tid`, однoтеговый файл — `db_transfer.payload_tag`).
- **CLI стал тонким (786 → ~380 строк) и получил `backup`/`restore`:** `backup` = снимок SQLite + JSON + CSV одной командой (то, что раньше делал `backup_db.sh`), `restore <файл>` = снимок **до** операции + импорт (тип файла — по расширению и заголовку CSV). `backup_db.sh` переписан в две строки-обёртки (никакой своей логики разбора имён), лаунчер `backup_db.py` теперь возвращает код возврата. Свой JSON-формат и своя SQL-запись в CLI удалены.
- **Тесты на CLI, которых не было вовсе** (`tests/test_backup_cli.py`, 14: round-trip, `--tag`, `list`, `--mode replace`/`--keep-tids`, CSV-правка по tid, `backup`/`restore`, отсутствие graft'а `id`, тонкость обёртки) и на модуль переноса (`tests/test_db_transfer.py`, 13). Доки: `backup_db.md` переписан (два вида бэкапа, таблица «что чем делать»), README (+таблица механизмов в ru/en/zh), `CLAUDE.md`, `AGENTS.md` (конвенция про единый модуль), `test_cmd.md` (секция 25, версия документа v1.93).

## v1.147

- **Секреты: инвариант «значение не в журнале» больше не зависит от момента показа (высокая).** Маскировка считалась при каждой отрисовке из текущего набора `$$`-секретов, поэтому после `$$NAME-`, переопределения, `:env` или `:session` любой повторный рендер (space/←→, F2, F8, поиск `:/`, `:w`) показывал настоящее значение. Теперь текст замораживается в момент записи вывода (`CommandBlock.freeze_secrets`, `masked_header/masked_stdout/masked_stderr`): `_make_command_block` и `update_content` прячут секреты сразу, `:watch` перезамораживает на каждом тике, `_output_history` (`:o`) хранит уже замаскированный вывод, шапка `:log` маскируется, `:llm` маскирует и контекст библиотеки (`app_context`), а не только сообщение. Попутно: `:watch` больше не печатает значение в теле блока (раньше маскировалась только шапка), `load_bashrc` не подменяет значение секрета из `.bashrc_term` (иначе маска «разъезжалась» и `secrets_<instance>.json` перезаписывался), при выходе чистится **только своё** хранилище (`secrets_<instance>.json*`, соседняя сессия свои значения сохраняет), а `:cmd` с `clear_clipboard_after_secret: true` не кладёт команду со значениями в буфер (в журнале — объяснение). Явные исключения по запросу человека (`F3`, `:log`/F7, `:cmd show`) остались и описаны в `AGENTS.md`/README.
- **Импорт истории (`:h import`) — форматы, пути и явные ошибки.** Разбор: снимается реальная zsh-континуация `\`+newline (было `do\ ; echo …` вместо `do ; echo …`), fish-unescape стал однопроходным (литеральный `C:\new` больше не превращается в `C:\ ; ew`), формат определяется по содержимому (нестандартный `$HISTFILE` вроде `~/.history` с zsh-extended записями), `sh` — алиас `ksh` (находит `~/.sh_history`), BOM снимается (`utf-8-sig`), бинарный файл — ошибка, а не мусорные «команды», у файлов больше 4 МБ читается только хвост. Пути: fish и PowerShell Core — XDG-каталог на всех ОС, nushell — системный (`Application Support` / `%APPDATA%`), на Windows в списке только Windows-пути (не мусорят сообщение «где искали»). Ошибки перестали выглядеть успехом: `append_history_file_lines` возвращает `AppendResult(added, error)` и не пишет пачку без блокировки (занятый файл, ошибка записи — отдельные сообщения `hist.import_write_failed`), нечитаемый источник отличается от «истории нет», лишний аргумент — `Usage: :h import [shell]`.
- **Гигиена кода.** Диспетчер `:`-команд переведён с цепочки `elif` (~150 строк) на таблицы `COLON_ARG_HANDLERS` / `COLON_NOARG_HANDLERS` плюс маленькие обёртки (`_handle_history_args`, `_handle_help_args`, `_handle_send_run_args`, …); забытая ветка больше не может молча отвечать «Unknown command» — `tests/test_colon_commands.py` требует обработчик для каждой `CMD_*`. Удалён мёртвый код: `ClickableCommand`, `_replay_focused_command`, `_scroll_results`, `_show_calc_help`/`_show_runbook_help` (после тем справки), `has_escapes`, `demo._wait_input_focus`, `MatrixRain.head_rows`, `IngressAnalyzer.install_crossplane`, `database_v2.delete_command_by_global_id`/`get_commands_by_prefix` (и упоминания в `DATABASE.md`), `backup_db.export_tag`/`import_tag`, `help_texts.topic_names_in_text`. Новые локали: `help.usage`, `hist.import_usage`/`import_write_failed` (en/ru/zh).
- Тесты: `tests/test_secrets.py` (+8: заморозка после снятия/переопределения, `:o`, шапка `:log`, `:watch`, `.bashrc_term`, чужие хранилища, `:cmd`, контекст `:llm`), `tests/test_history_import.py` (+10) и правимые кейсы путей/форматов, `tests/test_colon_commands.py` (+1: диспетчер покрывает все `CMD_*`).

## v1.146

- **Темы справки `:? <тема>`.** Общая `:?` разрослась до 358–366 строк на язык — группы команд переехали в отдельные тексты: `calc`, `run`, `i`, `md`, `llm` (+ `:cht`), `tags` (`?`/`!tag`/`!N`), `vars` (`$OUT`/`$VAR`/`$$`/алиасы), `kctx`, `send`, `session`. `src/help_texts.py` теперь реестр: `HELP_TEXTS` + `HELP_TOPICS` (каноническое имя → текст) и `help_topic(name)` с алиасами, включая русские слова (`calculator` / `калькулятор`, `runbook` / `playbook`, `k8s` / `ingress`, `ai`, `теги`, `secrets`, `mailbox`, `new` …). Разбор `:?` в `app.py` — через реестр: **неизвестная тема — явная ошибка со списком тем** (раньше молча показывалась общая справка), склеенное `:?calc` подсказывает пробел («`:? calc`, а не `:?calc`»), `:i` и `:? run` остались прежними точками входа. Любая тема рисуется одним путём `_add_help_block` (`escape_help_markup` + `linkify_colon_commands`) — раньше `:? calc` / `:i` шли без экранирования и линковки. Новое: `CommandRunner.get_help_completions` — после `:? ` Tab предлагает имена тем (в `cmd.?` они же перечислены). В `main` каждой локали — раздел «Темы справки» с оглавлением (сторожит `tests/test_help_topics.py`), в первой строке — указатель на темы. Тексты: `src/locales/help/<lang>/*.txt` (7 новых файлов × en/ru/zh); `ru/main.txt` 366→274, `en/main.txt` 358→270, `zh/main.txt` 366→273. Попутно исправлен разорванный перенос строки в `en/main.txt` («stripped, / progress»). Локали: `help.unknown_topic` / `help.topic_needs_space` (en/ru/zh), уточнён `cmd.?`. Доки: `README.md` и `docs/<lang>/README.md`, `CLAUDE.md`, эта таблица; ручной сценарий — секция 12 `test_cmd.md`. Тесты: `tests/test_help_topics.py` (10: реестр без дублей и с текстом на каждом языке, алиасы, неизвестная тема, `:?calc`, оглавление против реестра, показ темы с сохранием разметки и экранированием литеральных скобок, подсказки тем).

## v1.145

- **Догон переводов под `:h import` (v1.144).** Строка `:h import [shell]` добавлена в китайскую справку `src/locales/help/zh/main.txt` и пункт описания — в `docs/en/README.md` и `docs/zh/README.md` (по русскому оригиналу: `$HISTFILE` первым, fish/ksh/nushell/PSReadLine, `%APPDATA%` на Windows и XDG на Linux/macOS, последние 5000 строк, без дублей, ничего не исполняется, `:h import zsh` — только одна оболочка). Код не менялся.

## v1.144

- **`:h import [оболочка]` — импорт истории оболочки пользователя (кросс-ОС).** Новый модуль `src/history_import.py` (без Textual) находит файлы истории по ОС и `$HISTFILE` (`~/.bash_history`, `~/.zsh_history`, fish, ksh, nushell, PowerShell PSReadLine — `%APPDATA%` на Windows, XDG/`Application Support` на Linux/macOS), разбирает форматы (zsh extended `: ts:dur;cmd` и многострочные записи → одна строка через ` ; `, bash-метки `#<epoch>`, fish `- cmd: …` с кавычками и `\n`, plain PSReadLine/nushell) и берёт последние `DEFAULT_IMPORT_LIMIT` (5000) строк каждого. Записывает пачкой `history_store.append_history_file_lines`: **один** exclusive flock на весь импорт, пустые строки и уже имеющиеся в файле не дублируются (повторный импорт идемпотентен), после записи автоматическая компактизация уникализирует старый префикс. Ничего не исполняется, файлы только читаются (битые байты заменяются). Сообщения — локали `hist.*` (`import_done/import_none/import_unknown/import_failed`), строка в `:?` (en/ru). Тесты: `tests/test_history_import.py` (23: разбор всех форматов, пути и `$HISTFILE` по linux/darwin/win32 и XDG/APPDATA, `find_sources`/`read_sources` с лимитом, батч-запись без дублей, `:h import` в TUI — импорт/идемпотентность/неизвестная оболочка/«не найдено»).

## v1.143

- **Тот же языковой механизм для `llm_providers.example.yml` и `README.md`.** Шаблон провайдеров разложен по каталогу `src/llm_providers/<lang>.yml` (`en`/`ru`/`zh`): комментарии переведены, а язык файла задаёт `answer_language` (`English`/`Russian`/`Chinese`) и текст офлайн-заглушки (префикс `[offline]` во всех — на него опирается демо-тест). Провижининг копирует в новый data-каталог файл того же языка, выбранного в режиме auto; `llm_client.example_config_path(lang)` делегирует в новый общий модуль `src/example_config.py` (вместо `settings_example.py`: `settings_example_path`, `llm_providers_example_path`, `detect_language`). Docker-стенд выбирает оба шаблона одним языком, CI-проверка обновлена. README локализован: корневой остаётся русским, переводы — `docs/en/README.md` и `docs/zh/README.md` (по той же конвенции `docs/<lang>/`, что и справочники); относительные ссылки и `<img src>` внутри переложены на `../../`. Маркер версии в переводах — тот же (`**IDvjPy_term** vX.YY — …`), поэтому локализованные README добавлены в `bump_version.TARGETS` и под `test_release_meta` — версия не протухает. Заодно исправлены устаревшие тесты `tests/test_llm.py` (правило `answer_language` по умолчанию — язык интерфейса с v1.137; добавлен кейс `off`). Тесты: `tests/test_data_dirs.py` (+структура и языковые значения шаблонов провайдеров, паритет языков обоих каталогов), `tests/test_version_bump.py` (фикстуры локализованных README), `tests/test_release_meta.py` (+маркер версии в переводах), `tests/test_docker_stand.py`, `tests/test_llm.py`.

## v1.142

- **Локализованные шаблоны настроек + выбор языка при первом старте.** Шаблон `src/settings.example.yml` разложен по каталогу `src/settings/<lang>.yml` (`en`, `ru`, `zh`): ключи и значения синхронны, различаются только комментарии; `language:` оставлен `auto`. Новый модуль `src/settings_example.py` (`available_settings_languages`, `settings_example_path`, `detect_language`) и `_provision_fresh_data_dir` копируют в новый data-каталог **шаблон языка, выбранного в режиме auto** — `--lang` → `$IDVJPY_LANG` → системная локаль → `en`; нет файла языка — падает на `en`. Заодно поправлен приоритет в `i18n.resolve_language`: явный код (`--lang ru` / `$IDVJPY_LANG`) теперь бьёт `language: auto` в settings (раньше `auto` из settings перебивал CLI). Docker-стенд (`entrypoint.sh`) выбирает шаблон так же (env → `$LC_ALL`/`$LANG` → en), CI-проверка обновлена. Тесты: `tests/test_data_dirs.py` (параметризованный разбор всех шаблонов, равенство значений между языками, паритет с `available_languages()`, `settings_example_path`/`detect_language`, провижининг копирует en и ru по локали), `tests/test_i18n.py` (+`test_explicit_language_beats_auto`), `tests/test_docker_stand.py` (entrypoint ссылается на `src/settings/<lang>.yml`).

## v1.141

- **Китайский язык (`zh`) — полный языковой слой.** Каталоги `src/locales/zh.yml` + `src/locales/zh/{screensaver,seed}.yml` (204 ключа, паритет с `en`), справка `src/locales/help/zh/{main,runbook,calc,ingress}.txt`, комментарии сидов `src/seed_text/zh/*.yml` (25 файлов), тексты демо `src/demos/text/zh/*.yml` (5 туров), справочники `docs/zh/*.md` (26 файлов). Работает сразу: `:lang zh` / `--lang zh` / `language: zh`, `--seed` кладёт китайские подписи, `:relang zh` переводит уже посеянную БД. Поставляемые языки теперь `en`, `ru`, `zh`. Тесты обобщены: `tests/test_i18n.py` сверяет паритет ключей для **каждого** языка (параметризовано, было только ru), а справка проверяется по факту файла — откат на `en` её больше не маскирует; `tests/test_seed_i18n.py` — покрытие встроенных комментариев и «тег ровно в одном файле» для каждого языка слоя; `tests/test_seed_catalog.py` — наличие `docs/<lang>/<NAME>.md` и отсутствие кириллицы для каждого языкового каталога; новый `tests/test_demo_i18n.py` — паритет ключей демо-слоя и реальное наложение перевода (титул/подписи) без изменения шагов.

## v1.140

- **Английские справочники команд (`docs/en/`).** 26 файлов — все `SEED_*_COMMANDS.md` и обзорный `K8S_CHAINS.md` — переведены на английский. `handbook_md_path(name, lang)` уже предпочитал `docs/<lang>/` с откатом на базу, так что `:md SEED_GIT_COMMANDS.md` на языке `en` открывает английский текст, а на `ru` — базовый русский (файлы в `docs/` и корне). Структура сверена построчно (заголовки, ряды таблиц, код-блоки, `---`), машинно-кодо-подобные токены оставлены как есть; ссылки внутри перевода — сиблинги (`SEED_DISK_COMMANDS.md`, `K8S_CHAINS.md`). Заодно исправлена опечатка в `src/seed_catalog.py`: справочник sysstat назывался `SEED_SYSTAT_COMMANDS.md` вместо фактического `SEED_SYSSTAT_COMMANDS.md`, из-за чего ссылка `:md` в `:welcome` вела в никуда. Тесты: `tests/test_seed_catalog.py` (+2: у каждого справочника каталога есть `docs/en/<NAME>.md` и `handbook_md_path` резолвит именно его; в `docs/en/` нет кириллицы).

## v1.139

- **`:relang [code]` — перевод комментариев уже засеянной библиотеки.** Пробел между `--seed` и сменой языка: `--seed` пишет комментарии на языке `settings.yml: language`, но библиотека, посеянная вчера на `en`, оставалась на `en` и после `:lang ru` (повторный `--seed` стёр бы пользовательские теги). Новая команда `:relang <code>` (без аргумента — справка, как `:lang`; `:lang ru` → `:relang ru`) переписывает **только** комментарии канонических строк сидов — подписи тегов и подсказки команд, совпавшие по тегу и **тексту команды** (linux-дополнения `logs` / `file[12]` / `net[10..11]`, у которых нет канонической команды, — по позиции `tid-1`), ничего не удаляя и не добавляя. Комментарий, **правленый руками** (не пустой и не совпадающий ни с одним известным переводом), остаётся: `--seed` такого различения не делает. Перед записью снимается снимок БД в `backups/` (`mytags-pre-relang-….db`). Ядро — `src/relang.py` (`relang_db`, `seed_index` собирается из `seed_linux_commands` / `seed_k8s_chains` / `seed_git` / `seed_ops`); работа идёт в фоновом потоке (импорт сид-модулей не морозит UI), ошибка печатается блоком. Локали: секция `relang.*` + `cmd.relang` (en/ru), строка в справке `:?`. Тот же перевод из терминала: `python3 src/relang.py --lang ru [--db …]`. Тесты: `tests/test_relang.py` (11: en↔ru для команд и тегов, правленые/пользовательские строки не трогаются, снимок БД, linux-extra по tid, повторный прогон — no-op, CLI, `:relang` в TUI).

## v1.138

- **Заставка (матрица, звёздное поле) больше не греет CPU.** Симптом: «матричный дождь» съедал процессор и подтормаживал, особенно на большом терминале и после долгого показа. Причина — самая дорогая часть кадра: `render_text()` собирал `rich.Text` **по ячейке** (200×50 — это ~9.6k вызовов `Text.append` на кадр, и каждый стилизованный — ещё и `Style.parse`, который Rich не кэширует), а `_paint` перерисовывал холст на каждом тике 20 fps — притом что дождь идёт 1.8–6 строк/с, то есть за тик сдвигается меньше чем на строку. Профиль (`cProfile`, 3 с, 200×50): 425k вызовов `Text.append` и 6.0M вызовов функций всего, `_tick` — 1.36 с из 3 с, ~15 fps вместо 20 (цикл событий занят). Что сделано: (1) `cells_to_text()` клеит соседние ячейки одного стиля в один `Text.append`, а `_style_object()` кэширует разобранный `Style` (палитры — константы); (2) `_paint` троттлится до `PAINT_INTERVAL` (10 fps) и пропускает кадры, у которых не менялся `field.version`; `resize` рисует принудительно, `TICK_SECONDS` для симуляции оставлен 20 fps (лента/справка/load живут по `dt`, картинка не меняется); (3) `MatrixRain.tick`/`StarField.tick` возвращают «что-то видимое изменилось» и ведут `version` — у дождя это пересечение целой строки головой и мерцание **только видимых** строк хвоста (`_visible_row`), у звёзд — смена клетки/стиля часов. Замер после правки (то же 200×50, 3 с): сборка кадра **24.7 → 4.5 мс**, перерисовок **14.7 → 7.3 в секунду**, CPU холста **1.09 → 0.10 с** (~11×), вызовов функций 6.0M → 1.9M, цикл событий в основном простаивает (таймер и раньше снимался в `on_unmount` — утечки таймеров не было, память и число объектов за 2000 кадров не растут). Тесты: `tests/test_screensaver.py` (+6: группировка стилей и кэш разобранных стилей в `cells_to_text`, `tick` сообщает только видимые изменения, мерцание только по видимым строкам, `StarField` при `dt=0` не меняется, троттлинг и пропуск неизменённого кадра в `_paint`; поправлено сравнение `span.style` — теперь там разобранный `Style`).

## v1.137

- **Мультиязычный интерфейс: каталоги локалей + `:lang` / `--lang` / `language`.** Тексты UI переехали из литералов в каталоги `src/locales/<lang>.yml` (`en` — источник правды, `ru` — перевод), чтение — `src/i18n.py` (`t("kctx.off")`, `tlist("startup.keys")`). Язык выбирается по порядку `--lang` → `$IDVJPY_LANG` → `settings.yml: language` → `en`; значение `auto` разворачивается из `$LC_ALL`/`$LC_MESSAGES`/`$LANG`. Новая команда `:lang` (без аргумента — текущий и список; `:lang ru` — выбрать и сохранить, как `:theme`; `:lang auto`) и ключ `language` в `settings.example.yml`; в запуск добавлен флаг `--lang` (и корневой лаунчер). Локализованы: стартовый блок, сообщения `:kctx` / `:watch` / `:run` / `:llm offline`, подсказки `:`-команд (таблица имён — `COLON_COMMAND_NAMES`, текст — `cmd.<имя>`), каталог `:welcome` (`catalog.*`), строки справки заставки (`screensaver.help`), а справка `:?` / `:? run` / `:? calc` / `:i` переехала в файлы `src/locales/help/<lang>/*.txt` (доступ — `src/help_texts.py`, текст — `i18n.text()`; `ru` полностью переведён). `:?` получил строку про `:lang`. Не переводятся команды, имена тегов, ключи настроек и имена файлов; неизвестный ключ печатается как есть, отсутствующий падает на `en` (пустоты нет), битый файл локали/справки (не UTF-8, сломанный YAML) тоже откатывается на `en`, а не роняет приложение, смена языка не перерисовывает уже показанные блоки. Тесты: `tests/test_i18n.py` (24: сверка en↔ru (ключа и частей каталога), отсутствие кириллицы в `en`, ловушка YAML-ключей `off`/`n`/`N`, нормализация `ru_RU.UTF-8`, приоритет CLI→env→settings, `auto` по локали, `:lang` — список/смена/сохранение/неизвестный код, язык из settings при старте, справка и описания сидов есть в каждой локали, каталог заставки сходится с встроенным набором), `tests/test_colon_commands.py` (подсказки из локали), `tests/test_seed_catalog.py` / `tests/test_commands.py` (каталог из локалей), `tests/test_screensaver.py` (строки из каталога), `tests/test_llm.py` (офлайн-ответ из `llm.offline`).
- **Тексты демо-туров — слоем по языкам.** Базовые `src/demos/*.yml` хранят шаги (команды, `keys`, `pause`, `loop`) и базовый текст; перевод живёт в `src/demos/text/<lang>/<tour>.yml` (`title`, `captions`/`types` по номеру шага). `demo.load_scenario()` накладывает слой языка (`apply_text_overlay`), поэтому `--demo` показывает подписи выбранного языка, а команды остаются общими. Тесты: `tests/test_demo.py` (needles шагов — английские).
- **Комментарии сидов — по языкам (`src/seed_text/<lang>/`).** Встроенные комментарии в `src/seed_*.py` остаются базовым текстом, английские — в `src/seed_text/en/<handbook>.yml`, ключ — тег + позиция команды. `seed_lib.localized_tags()` / `localized_comment()` / `localized_tag_comment()`; язык — `settings.yml: language` → `$IDVJPY_LANG` (`resolve_seed_language`), поэтому `--seed` и `--comments` пишут на языке приложения (для `language: ru` — встроенный русский). Конвенция перевода — `src/seed_text/README.md`. Тесты: `tests/test_seed_i18n.py` (покрытие всех встроенных комментариев, отсутствие кириллицы в `en`, тег ровно в одном файле, откат к базовому тексту, язык из settings), `tests/test_seed_git.py` / `tests/test_seed_linux_commands.py` (ожидания — английские).
- **`:llm` по умолчанию отвечает на языке интерфейса.** `answer_language` провайдера: `auto` или отсутствие ключа → имя языка приложения (`llm.answer_language` из локали), а `off` / `none` / `no` / `false` / `0` выключают правило языка совсем (прежнее поведение).
- **Поиск справочников — по языку.** `handbook_md_path(name, lang)` сначала смотрит `docs/<lang>/NAME`, затем `docs/NAME` и корень: перевод справочника можно положить рядом, не трогая код (для языка без своей копии работает базовый). Тест — `tests/test_seed_catalog.py`.

## v1.136

- **Справка по командам догнала поведение (v1.119–v1.133).** Документация местами описывала прежнее поведение — правились только тексты, логика не менялась. Подсказка `:screensaver` обещала «starfield now», хотя с v1.119 холст по умолчанию — «матричный дождь» (`screensaver_matrix`); `:kctx` в `:?` и в ленте заставки перечислял только kubectl-стек, хотя с v1.129 список задаёт `kctx_vars` (по умолчанию kubectl **и** helm: `RELEASE CHART VALUES`), а `kctx_vars: []` выключает журнал; `:log` (в `:?`, в подсказке автодополнения и в ленте заставки) молчал про `f` — режим «только совпадения» и подсветку строки целиком (v1.132–v1.133). `:? run` получил предупреждение про тег без единой `run:`-директивы (все шаги уйдут `auto`, v1.130), а YAML-пример в справке переведён на префиксную строку `$ROLE=` (как в сиде `vapprole`: значение дописывается после `=`). В таблицу `:`-команд в `COMPACT_SUMMARY.md` добавлены пропущенные 8 команд (`:rg`, `:cht`, `:ed`, `:log`, `:name`, `:kctx`, `:send`, `:send!`), в перечень клавиш заставки — F7, в её ленту — `:run`. Тесты: `tests/test_colon_commands.py` (полнота таблицы подсказок), `tests/test_screensaver.py`, `tests/test_kctx_cmd.py`, `tests/test_runbook.py`, `tests/test_output_viewer.py`; `ruff` — без замечаний.

## v1.135

- **Секреты в `:send`: значение — в секретное хранилище цели, а не в ящик и не заглушкой.** `:send s2 curl -H "Bearer $TOKEN" …` раньше уходил в ящик с `****` вместо значения — секрет был защищён, но команда у цели заведомо не выполнялась (в ящике лежала заглушка). Теперь отправитель материализует команду, **не раскрывая свои секретные имена** (`substitute_variables(..., skip=…)`, `_substitute_variables(keep_secrets=True)`): в ящике едет `$TOKEN`, а значения упомянутых секретов (только их, не всех подряд) `_pass_secrets_to` кладёт прямо в секретное хранилище цели — `secrets_<target>.json` (0600, чистится при выходе её сессии, как и свои). Своё значение цели **не перезаписывается**: если имя у неё уже есть, команда выполнится с ним, и отправитель видит это в журнале (`secret value(s) → target secrets file: $TOKEN → beta` и `target's own secret(s) kept: $TOKEN @ beta`). Получатель при выемке ящика перечитывает свой secrets-файл (`load_secrets` в `_poll_session_inbox`) — поэтому `$NAME` в уже доставленной команде сразу что-то значит. Итог: `:send!` с секретом у цели действительно выполняется, а значение не появляется ни в `inbox_*.jsonl`, ни в её журнале/истории (в шапке блока — маска `****`, в истории — имя). Маска осталась как страховка от значений, попавших в текст иначе (`$OUT` блока, алиас, вставлено руками) — но теперь она явно говорит, что команда у цели не выполнится, и предлагает писать `$NAME`. Заодно вспомогательное: `secrets_file_for` / `read_secrets_file` / `write_secrets_file` (одна реализация атомарной записи 0600 вместо дублирования в `_save_secrets` / `load_secrets`), в справке `:send` — строка про секреты. Тесты: `tests/test_session_mailbox.py` (вместо проверки `****` — 5 своих: значение в хранилище цели и 0600, самого значения в ящике нет, свой секрет цели не перезаписан, обычная пересылка в чужие секреты не лезет, при выемке имя подхватывается из файла и в ввод/журнал идёт только имя, а `:send!` у цели выполняется по-настоящему и в историю попадёт имя), `tests/test_shell_env.py` (+1: `skip` оставляет `$NAME`/`${NAME}`, без `skip` — как раньше).

## v1.134

- **Правая рамка поля ввода больше не уезжает за край после смены темы через `Ctrl+P`.** Симптом: открыл палитру команд (`Ctrl+P`), выбрал тему — справа у поля ввода пропала рамка (и оставалась пропавшей после закрытия палитры). Причина — **совпадение имён классов**: в `textual/command.py` есть свой `CommandInput` (поле палитры) с `DEFAULT_CSS`:
  `CommandInput, CommandInput:focus { border: blank; width: 1fr; padding-left: 0; background: transparent; background-tint: 0% }`,
  а наш виджет поля ввода назывался так же (`src/app.py`: `class CommandInput(Input)`), и Textual матчит CSS **по имени класса** — селектор `CommandInput` накрывал оба виджета. Правило вступало в силу, как только палитра хоть раз открывалась (её CSS попадает в общий stylesheet), а применялось при следующем переприменении CSS — как раз при смене темы. Для `width` мы своего правила не имели: `CommandInput` (селектор-класс) побеждал `Input` (селектор-тип) в `DEFAULT_CSS`, поле получало `width: 1fr`, и вместе с `margin: 0 1` (68 + 2 > 70) его бокс выходил за правый край экрана — рамка обрезалась. Рамка при этом не исчезала в CSS («все четыре грани на месте» в `styles.border`), а именно вылезала за экран — поэтому смена темы через `:theme` или `d` ничего не ломала (палитра не открывалась), а через палитру — ломала. Лечение — корень, а не симптом: класс переименован в `CommandLineInput` (24 ссылки в `src/app.py`, `tests/conftest.py`, `tests/test_input_words.py`), совпадение снято целиком — заодно наш виджет больше не наследует `border: blank` / `background: transparent` / `background-tint: 0%` от чужого `DEFAULT_CSS`. В `CLAUDE.md` и в докстроке класса — предупреждение «не переименовывать обратно» (имя класса виджета в Textual — глобальный идентификатор для CSS). Тесты: `tests/test_themes.py` (+1: `Ctrl+P` → смена темы → `region.width` поля остаётся `экран − 2`; до правки тест падал на `width=70` вместо 68). Проверены и соседние наборы, где виджет фигурирует: `test_input_words`, `test_commands`, `test_completion`, `test_colon_commands`, `test_secrets`.

## v1.133

- **F7: режим «только совпадения» (`f`).** Второй вариант из задачи («подсветка строки **или** как в JSON-вьюере — только найденные строки»): подсветку починили в v1.132, а теперь есть и фильтр — на 13k строках с тремя совпадениями он полезнее подсветки. `f` в `OutputViewerScreen` оставляет на экране только строки с текущим образцом поиска, повторный `f` и Esc возвращают весь вывод; работает и в raw-виде `:md`. Что решено по механике: (1) работает от **текущего** образца, поэтому `f` без поиска — подсказка `Filter needs a search first: / text, Enter, then f`, а не пустой экран; (2) если совпадений нет, фильтр не включается (`set_filter` возвращает 0, вызывающий говорит `No match`), а если образец сменили на «пустой» — фильтр снимается сам: пустой экран без объяснения хуже полного списка; (3) отображение не расходится с журналом — в подзаголовке `hit · matches 2/30 · line 17 · f / Esc — all lines`, где номер строки **исходный** (`OutputView.source_line` по карте `_rows`), а `line_count` остаётся числом строк всего вывода (`visible_count` — сколько показано); (4) `n`/`N` ходят по отобранным строкам (в режиме фильтра все видимые строки — совпадения), а место совпадения пересчитывается при включении/выключении так, чтобы не теряться; (5) `Esc` идёт по цепочке: поле поиска → фильтр → экран. Тесты: `tests/test_output_viewer.py` (+4: фильтр оставляет только совпадения и исходный номер строки в подзаголовке, `n` по отбору и снятие фильтра по `f`/Esc с сохранением места, повторный `f` возвращает весь вывод, `f` без поиска ничего не фильтрует, новый образец без совпадений снимает фильтр).

## v1.132

- **F7: строка совпадения подсвечивается целиком, а не только найденный текст.** Симптом: в поиске по выводу (`:log` / F7, `/` → Enter) жирным становились только символы совпадения — фона строки не было, хотя стиль `outputview--hit` его задаёт (`background: $accent 55%`). Причина в семантике `Strip.apply_style`: `rich.segment.Segment.apply_style` сливает стили как `применяемый + стиль_сегмента`, то есть **стиль сегмента побеждает** — фон/цвет чётной-нечётной строки (`outputview--even` / `--odd`) перебивали фон хитового стиля, и от него выживал только атрибут `bold` (его в базовых стилях нет). Теперь `OutputView.render_line` выбирает имя компонентного стиля сразу (`--hit` вместо `--even` / `--odd`), а не накладывает его поверх; строка совпадения заливается акцентом на всю ширину. Тот же приём уже был в `highlight_selection` (`segment_style + style` вручную) — поэтому выделение мышью работало. Тесты: `tests/test_output_viewer.py` (+1: у строки совпадения `bgcolor` равен `--hit`, `bold` есть, ширина — полная, у соседней строки фон другой).

## v1.131

- **Порядок ↑ — хронология набора, а не «сначала файл, потом лента».** Симптом: `:screensaver`, затем обычная команда (`vault …`) — по ↑ первой всплывала `:screensaver`, а не только что набранная команда. Причина: пул истории склеивался как «все строки `history_<instance>.txt`, затем лента сессии», поэтому любая строка, которой в файле нет (`:`-команды, `?теги`, `!ссылки`, `#теги`, `$VAR=…`), оседала в самом хвосте пула — **после всех** строк файла, независимо от того, когда её набрали. Обычная же команда уходит в файл и потому оказывалась глубже. Теперь `_history_pool_pairs` собирает пул по хронологии: сначала строки файла, которых в этой сессии не набирали (старое), затем лента сессии целиком (её порядок и есть порядок набора). Заодно исправился тот же порядок у двух других потребителей того же пула: подсказки `↺` (`get_history_completions`) и `:h /текст` (`_unique_history_matches`) — «свежие сверху» теперь действительно по времени, а не «сначала всё из файла». `_history_pool` больше не дублирует правило — это тот же список без casefold. Тесты: `tests/test_session_history.py` (+1: `echo first-plain` → `:stats` → `echo last-typed`, три ↑ по порядку дают `echo last-typed`, `:stats`, `echo first-plain` — до правки первый же ↑ возвращал `:stats`).

## v1.130

- **`run vapprole` больше не выполняет шаг роли вместо человека; тег без `run:`-директив виден в плане.** Симптом: `:run vapprole` сам выполнял `$ROLE=custom-role` и падал на следующем шаге — `vault read auth/approle/role/$ROLE/role-id`. Причина — устаревший сид в рабочей БД: в старом наборе (до v1.124) не было ни одной директивы `run:`, а `RunSpec.mode` по умолчанию — `auto`, поэтому прогон брал `auto` на все шаги и молча шёл дальше (включая мутирующий `vault write -force … secret-id`). Теперь, во-первых, шаг 2 в сиде — строка-префикс `$ROLE=` (как и шаг 1 `$$VAULT_TOKEN=`): значение **дописывается после `=`**, и Enter с нетронутой строкой не отправит вымышленное имя роли (раньше стояло `$ROLE=custom-role`, и Enter выполнял именно его). Во-вторых, тег без единой `run:`-директивы получает заметку в плане: `note: в теге нет run:-директив — все шаги пойдут auto; мутирующий шаг безопаснее пометить run:manual (см. :? run)` — молчаливый «всё auto» для устаревшего сида больше невозможен (`NO_DIRECTIVES_NOTE` / `has_run_directive` в `src/runbook.py`, `steps_from_tag`), а при `--step` заметка снимается: все шаги и так ждут Enter. Диагностика в один шаг — `:run <тег> --dry`: в плане видны режимы всех шагов. Тесты: `tests/test_runbook.py` (+3: тег без директив — заметка в плане и она снимается `--step`, достаточно одной директивы (в т.ч. в комментарии тега), `has_run_directive` читает только первый токен), `tests/test_seed_ops.py` (шаг 2 `vapprole` — `$ROLE=`, не `$ROLE=custom-role`). `seed_vault.py` в справке `--seed` теперь честно перечисляет `vapprole` в списке заменяемых тегов.

## v1.129

- **Список переменных кластерного журнала — в settings.yml (`kctx_vars`).** `:kctx` запоминал по кластерам только kubectl-стек (`NS POD DEPLOY SVC ING APP CTR QUOTA`) — и этот же зашитый кортеж решал, что видно в списках и что возвращает `:kctx N`. Для helm-шаблонов (`helm upgrade --install $RELEASE $CHART -n $NS -f $VALUES`, тег `hvars`) этого мало: `$RELEASE=…` не попадал в `kctx.json` вообще, и, вернувшись в кластер, приходилось заново вспоминать релиз, чарт и values. Теперь список имён — ключ `kctx_vars` в settings.yml: список или строка через запятую/пробел (ведущие `$` / `:` отбрасываются, негодные имена и повторы — мимо), порядок имён — это же порядок в списках `:kctx` (`kctx prod #1: NS=team-a RELEASE=myapp`), а дефолт — стек bundled-шаблонов: kubectl **и** helm (`RELEASE CHART VALUES`). `[]` / `false` / `null` выключают журнал целиком: снимки не пишутся, а `:kctx` без журнала прямо говорит «Журнал выключен: kctx_vars: [] в settings.yml». Присваивание переменной вне списка (`$EDITOR=…`) в журнал по-прежнему не идёт. Технически список стал параметром: `stack_vars` / `format_vars` / `add_snapshot(var_names=…)` (пустой список — «ничего», а не дефолт), рабочий список хранит `CommandRunner.kctx_vars` (`handle_variable_assignment` → `_remember_kctx_snapshot`, парсер `parse_kctx_vars` в `src/kctx_store.py` — модуль без Textual), а подсказки `:kctx` печатают настроенный список (`_kctx_vars_hint`). NB: `VALUES` — обычно относительный путь, `:kctx N` вернёт его как есть — запускайте helm из каталога с values (или задайте абсолютный путь). Тесты: `tests/test_kctx_store.py` (+3: разбор `kctx_vars` — список/строка/`$`/мусор/`[]`/`true`/число, дефолт покрывает kubectl+helm, `stack_vars`/`format_vars`/`add_snapshot` с чужим списком), `tests/test_kctx_cmd.py` (+2: с `kctx_vars: [NS, RELEASE, CHART, VALUES]` `$RELEASE=myapp` пишет снимок, а `$POD=` — нет, и `:kctx prod 1` возвращает релиз; с `kctx_vars: []` журнала нет и `:kctx` объясняет почему), `tests/test_data_dirs.py` (ключ в шаблоне).

## v1.128

- **Файловая подсказка больше не «прилипает» и не затирает набранное (Enter).** Симптом: набираешь `cat f`, список файлов открывается — потом продолжаешь строку другим текстом (`cat f | grep ot`), список **остаётся висеть**, а Enter подставляет в него выбранного кандидата и стирает набранный текст; убрать — только Esc. Причина: `_is_path_context` смотрела на **первое слово всей строки** (`cat` ∈ `FILE_ARG_COMMANDS`), поэтому любой хвост (`grep ot`) считался файловым аргументом `cat`, а по нему в cwd находились совпадения (`project.log` на `ot`) — список не пустел и перехватывал Enter.
  Теперь контекст считается по **текущему сегменту** строки (`_current_command_segment` — после `||`/`&&`/`|`/`;`): в `cat f | grep ot` токен принадлежит `grep`, подсказки от `cat` больше не примешиваются. Заодно команды, у которых **первый аргумент — шаблон** (`grep`/`egrep`/`fgrep`/`rg`/`ag`/`awk`/`sed`/`jq`/`yq`/`xargs`), вынесены из `FILE_ARG_COMMANDS` в `PATTERN_ARG_COMMANDS`: `auto` даёт им файлы только со второго не-флагового аргумента (`grep ot` — без листинга cwd, `grep -n x project.log` — с листингом). `cd`/`pushd` по-прежнему работают в любом режиме.
  Тесты: `tests/test_file_completion.py` (+4: `_cwd_files`, контекст по текущему сегменту, шаблонные команды подсказывают только со второго аргумента, покадровый сценарий «список виден на `cat tfile.txt` → скрыт при наборе ` | grep ot` → Enter не портит ввод»).

## v1.127

- **Лента сессии (↑) и файл истории окончательно разведены.** По ↑ во время сессии теперь перелистывается **всё**, что человек вводил, а в `history_<instance>.txt` попадает только разрешённое. Раньше `session_history` наполняли только обычные команды (плюс `>`/пайпы/`# command`/калькулятор), поэтому `:stats`, `?vault`, `!deploy[1]`, `#tag cmd`, `$NS=team-a` по ↑ не возвращались — их не было ни в ленте, ни (по фильтру `log_to_history`) в файле. Теперь `on_input_submitted` помнит набранную строку одной точкой входа (`_remember_session_line`): `:`-команды, `?теги`, `!ссылки`, `#теги`, `$VAR=…`, обычные команды и `@`/`>`-строки.
  Что попадает в файл, по-прежнему решает `log_to_history` (`history_queries`, сохранения `#tag` и подстановки — мимо). Исключения ленты: секреты `$$…` (значение не должно всплывать в строке по ↑) и пайпы `|…` — их кладёт `handle_pipe_command` в развёрнутом виде (`|@метка cmd` без буфера не воспроизвести). Повторы не дублируются (как и раньше), позиция ↑ сбрасывается на конец. Выпадающий список подсказок `:`-строки из ленты не показывает: у `:`-команд своя таблица (`get_completion_candidates` пропускает `:…`), обычные строки из ленты подсказываются как раньше. Тесты: `tests/test_session_history.py` (5: все виды строк в ленте и ни одной лишней в файле, `:stats` возвращается по ↑, секреты не запоминаются, дедуп повторов, `:`-строки не в подсказках). Заодно `:h /text` не находит сам себя (`_show_history_search(exclude=…)`): лента помнит набранное, но поиск не должен показывать собственный вызов (прежние `:h /…` в результатах остаются как обычная история).

## v1.126

- **Фоновая команда больше не может «украсть» клавиатуру (и починить это не приходилось kill'ом).** Симптом: `:kctx <cluster>` запускал `tsh kube login`, тот висел на интерактиве, команда закрылась по таймауту — а приложение «перестало отвечать»: клавиши и мышь не работали, заставка не закрывалась, оставалось только `kill`. Причина: `Popen(..., stdin=None)` **наследовал терминал TUI**, поэтому команда читала клавиши/мышь напрямую (её ввод шёл ей, а не приложению) и могла перевести терминал в свой режим (raw, `VMIN=0`, без echo) и не вернуть его, будучи убитой сигналом. Теперь фоновая команда получает `stdin=subprocess.DEVNULL` (`_execute_in_thread`, `_capture_watch_tick`, а также вспомогательные запуски в `_describe_namespace`, `src/k8s_complete.py`, `src/md_search.py`, `src/ingress_analyzer.py`): интерактивные `read`/`tsh`/`kubectl`/`ssh` видят EOF (пайп `| cmd` по-прежнему передаёт данные как раньше) — интерактив остаётся за `> cmd`. Таймаут стал чистым: по `TimeoutExpired` группа добивается SIGKILL, хвост вывода собирается, каналы закрываются и процесс дожидается (`_drain_after_kill` — иначе сироты держали pipe, а зомби жил до сборки мусора), а после любого убийства (таймаут или F4 / `:kill`) приложение возвращает терминал в свой режим (`_restore_terminal_mode` — пустой `suspend()`: `stop/start_application_mode` + снятие заставки и сброс простоя). Сообщение таймаута теперь с подсказкой: `Process timed out (Ns). Killed. Long jobs: `@ cmd` (no timeout) · interactive: `> cmd` (real TTY).` Заодно `:kctx <cluster>` запускает вход **без** `command_timeout`: `tsh kube login` ходит в сеть и в 10 с легко не укладывается, висящий вход видно в блоке и останавливают F4 / `:kill`. Тесты: `tests/test_command_stdio.py` (3: `read` видит EOF вместо клавиатуры, пайп всё ещё доходит до stdin, таймаут убивает группу — процесса больше нет, в stderr есть подсказка `@ cmd` / `> cmd`), `tests/test_kctx_cmd.py` (+проверка `no_timeout=True` у строки входа).

## v1.125

- **Список «запросных» `:`-команд — в settings.yml (`history_queries`).** Какие вызовы `:`-команд остаются в `history_<instance>.txt` для ↑ / `:h`, но не подсказываются, было зашито регуляркой (`RE_HISTORY_ONLY_QUERY`: `llm|cht|rg|md|run|send!?`); каждое новое такое поведение требовало правки кода. Теперь это список имён без `:` в ключе `history_queries` — по умолчанию `llm, cht, rg, md, run, send, send!` (прежнее поведение). Принимает список (`- llm`) или строку через запятую/пробел (`history_queries: llm, run`), двоеточия в именах отбрасываются, пустые элементы игнорируются; `[]` / `false` / `null` — выключено (вызовы `:`-команд в историю не пишутся), ключа нет или мусор в значении — набор по умолчанию. Аргументы по-прежнему обязательны (`:llm` без вопроса не записывается). Оба места (запись в историю — `log_to_history`, фильтр подсказок — `get_completion_candidates`) работают через один метод `CommandRunner._is_history_only_query`, парсер значения — `parse_history_queries`. Тесты: `tests/test_history_queries.py` (7: формы ключа и выключение, дефолт, аргументы/имя `:send!`, запись без подсказок, узкий список `[rg]`, `[]` — не пишем, отсутствие ключа — прежний набор).

## v1.124

- **Прогон цепочки — runbook (`:run`).** Цепочки вроде vault-AppRole требуют ручного `!tag[N]` на каждый шаг, хотя значения переносятся из вывода автоматически (`@key`), а решение человека нужно всего в двух-трёх местах. Теперь цепочка запускается одной командой и останавливается там, где нужно решение. Источник: тег (`:run vapprole` — шаги в порядке tid) или YAML (`:run chain.yml`), в т.ч. файл `:playbook` (демо-ключи `start_pause`/`type_delay`/`command_timeout`/`reset_tags`/`wait_command` принимаются и не мешают). Режимы шага: `auto` — вставить во ввод, выполнить, дождаться завершения и идти дальше; `manual` — вставить строку и ждать Enter человека (можно править; `$$VAR=…` при этом маскируется); `prompt` — ввод пуст, ждёт набранную строку; пустой Enter пропускает шаг (токен уже есть, шаг не нужен). Ошибка auto-шага (`exit ≠ 0`) останавливает прогон с номером шага, `run:continue` в комментарии отменяет это для конкретного шага. `Esc` останавливает прогон в любой момент (`:run stop` — то же), сама команда — F4 / `:kill`. Флаги: `--step` (полуавтомат — каждый шаг ждёт Enter), `--dry` (только план, ничего не выполнять). Режимы шага тега задаются директивами в начале комментария команды: `run:auto` / `run:manual` / `run:prompt` / `run:pause=SEC` / `run:continue` / `run:stop`; остаток комментария — подсказка в плане и в `??`. Директивы в комментарии тега задают значения по умолчанию для его шагов (пауза, реакция на ошибку). Перед прогоном в журнал печатается план (шаги, режимы, подсказки, предупреждения о неизвестных директивах/ключах), в подзаголовке — `RUN <цепочка> · 3/9 · auto · Esc stops`; `:run` без аргументов — usage и список тегов с директивами, `:? run` — полная справка. Пока прогон идёт, заставка не всплывает, смена сессии и `:watch` отклоняются, `:send` откладывается, счётчик отправок (`_run_submits`) обслуживает пропуск шага, а вставленные прогоном строки не попадают в `:playbook`. `:run …` пишется в `history_*.txt` (↑ / `:h`), но не в подсказки (как `:llm`/`:cht`). Движок набора/Enter общий с `--demo` (`demo.submit_line`, `_driving()` учитывает `_run_active`). Модуль — `src/runbook.py`. Seed `vapprole` пересобран под прогон: шаг 1 — `$$VAULT_TOKEN=` (`run:manual`; токен из vault.website и остаётся маскированным), шаг 2 — имя роли (`run:manual`), шаг 5 — выпуск `secret_id` (`run:manual`: мутирующий шаг — только по подтверждению), остальное `run:auto`; tids сдвинулись на один (см. `docs/SEED_VAULT_COMMANDS.md`). Тесты: `tests/test_runbook.py` (23: директивы/наследование/YAML/план и Pilot — auto-цепочка, manual ждёт Enter, prompt ждёт набранную строку, пустой Enter пропускает шаг, остановка по ошибке и `run:continue`, Esc и `:run stop`, `--dry`, свой YAML, отказы при `:watch` и втором прогоне), `tests/test_seed_ops.py` (tids и директивы `vapprole`), `tests/test_colon_commands.py` (`:run` в таблице).

## v1.123

- **Вывод цветных команд — как в терминале (`ansi_colors`).** Симптом: алиас `ww='curl wttr.in; …` и любой другой вывод с ANSI-цветами ломался — арт wttr.in, `ls --color=always`, цветной `grep` и прогресс-бары превращались в кашу, хотя сама команда отрабатывала. Причина: приложение пишет текст блока прямо в терминал (кадр TUI целиком), а в тексте оставались сырые escape-последовательности — реальный терминал исполнял их **внутри кадра**: цвета текли на соседние клетки, `\x1b[0m` сбрасывал стиль приложения, `\r` уводил курсор в начало строки. Новый модуль `src/ansi_output.py` разбирает вывод: SGR (`\x1b[..m`) → Textual-разметка через Rich `Text.from_ansi` (цвета стандартные/256/truecolor, bold/italic/underline/dim/reverse), всё остальное (курсор, стирание, OSC/гиперссылки, bracketed paste, управляющие символы) вырезается всегда, а `\r`-перерисовка сворачивается до итоговой строки — прогресс-бары `curl`/`docker`/`pip` показывают результат, а не сотни кадров. Чтобы `\r` вообще доживал до разбора, `_execute_in_thread` и `_capture_watch_tick` читают каналы байтами (`text=True` переводил `\r` в `\n`). Ключ `ansi_colors` (по умолчанию `true`) выключает цвета: вывод плоский; `F6` (простой режим) делает то же на сессию, ведь его обещание — плоский текст для выделения мышью. Плоские данные никогда не содержат escape-кодов: новое `CommandBlock.plain_stdout` / `plain_stderr` используют F3-копия, пайп `|`, `$OUT`/`$BLOCK` (`:llm`, `:ed`), `:log`/F7, `@key` (таблицы vault), `:diff`, JSON-вьюер и поиск по журналу, а `raw_stdout` остаётся настоящим для цветного рендера. Огромный цветной вывод (> `MAX_MARKUP_CHARS`) рендерится плоским: разбор ANSI стоит ~25 ms на 300 строк и не должен задерживать кадр. `cheat_sh.strip_ansi` теперь делегирует в общий `strip_escapes` (одна реализация разбора). Тесты: `tests/test_ansi_output.py` (14: юнит на SGR/OSC/управляющие/`\r`/лимит и Pilot на цвета в кадре без сырых ESC / выключенные цвета / плоские F3 и `|` / F6 / дефолт ключа).

## v1.122

- **Заставка больше не встречает на возврате из `> cmd`.** Пока настоящий TTY был у чужого процесса (`> vim`, `> htop`, Ctrl+O, `:ed`), цикл Textual стоит на блокирующем `subprocess.run`, а таймер заставки в это время «перезревал»: сразу после возврата он срабатывал и открывал заставку — вместо журнала с результатом команды. Теперь `CommandRunner.suspend` — своя обёртка: на время паузы поднят флаг `_tty_active` (пока он стоит, `_launch_screensaver` ничего не открывает, а сработавший таймер переносится), а после возврата заставка снимается (если всё-таки успела открыться) и простой отсчитывается заново. Плюс страховка от «хвостового» срабатывания: `_launch_screensaver` сверяет реальное время последней активности (`_ss_bumped_at`, ставит `_bump_screensaver_idle`) и переносит запуск, если простоя по факту ещё нет (запас `SCREENSAVER_TIMER_SLACK`). Покрывает все паузы TUI сразу, включая `:ed` — он идёт через тот же `_run_in_tty`. Тесты: `tests/test_screensaver.py` (+2: возврат из TTY при перезревшем таймере — заставки нет, а после настоящего простоя она открывается как обычно; сработавший таймер во время паузы ничего не открывает).

## v1.121

- **Раскрытие алиасов больше не ломает `||`, `|` и `2>&1` (вход в кластер по `:kctx`).** Симптом: `:kctx <cluster>` с алиасом `klogin='tsh kube login $1'` давал `tsh kube login k8s.dev-du '||' kubectl config use-context k8s.dev-du` и ошибку `tsh: error: unexpected ||` — оператор уезжал в `tsh` аргументом. Причина: `expand_aliases` (`src/shell_env.py`) разбирала строку `shlex.split`, а остаток после подстановки `$1`/`$@` пересобирала через `shlex.quote` — а `shlex.quote("||")` даёт `'||'`. Теперь вызов алиаса разбирается своим сканером (`parse_alias_call`, `_word_end`): аргументы — это слова до первого shell-оператора вне кавычек (они безопасно уходят в `$1` / `$@` с цитированием), а хвост строки приклеивается **как набран** — операторы остаются операторами, кавычки не теряются; номер дескриптора (`2>&1`, `2>>log`) остаётся с оператором, а не становится аргументом. Заодно починилось то же самое для `$@`-алиасов: `kget pod | grep api` больше не превращается в `kubectl get pod '|' grep api`. Классические алиасы (без `$N`) работают как раньше. Тесты: `tests/test_shell_env.py` (+1: `||`, `|`, `>`, `2>&1`, `$@`, кавычки в хвосте, классический алиас), `tests/test_kctx_cmd.py` (+1: строка входа `:kctx` с `$1`-алиасом сохраняет `||`).

## v1.120

- **`:kctx <cluster>` сам применяет единственный набор.** Если у кластера в журнале ровно один снимок переменных, выбирать не из чего — теперь `:kctx <cluster>` (вход + снимки) применяет его сразу, без номера: списка из одной строки нет, а InfoBlock прямо говорит, что произошло — `kctx <cluster> #1: NS=… POD=…  (единственный набор — применился сразу)`. При двух и более наборах поведение прежнее: вход, список и применение по номеру (`:kctx N` или `:kctx <cluster> N`), ни одна переменная сама не меняется. В подсказке списка кластеров так и написано. Тесты: `tests/test_kctx_cmd.py` (+2: один снимок — применился и объяснил, что он единственный; два снимка — только список и применение по номеру).

## v1.119

- **Заставка в стиле «Матрицы» + ключ выключения (как `screensaver_stars`).** Новый холст `MatrixRain` (`src/screensaver.py`) — падающие столбцы глифов (полуширинные катаканы, цифры, знаки): голова столбца рисуется самым ярким стилем (`MATRIX_HEAD_STYLE`), хвост затухает по палитре (`MATRIX_TAIL_STYLES`), столбцы стартуют вразнобой и целиком перезапускаются из-за верхней границы — «вспышки» в кадре при сбросе нет. Темп медленный и ровный: 1.8–6.0 строк/с (`MATRIX_MIN_SPEED` / `MATRIX_MAX_SPEED`), кадр 20 fps (`TICK_SECONDS = 0.05`) — за кадр голова сдвигается меньше чем на полстроки, поэтому шаг вниз не «дёргает»; мерцание хвоста — 2 смены глифа в секунду (`MATRIX_FLICKER_PER_SECOND`), а не на каждый кадр. Все тики заставки и раньше принимали `dt`, поэтому поднятая частота кадров не ускорила звёзды, ленту, справку и load/RAM — только плавность. Ключ `screensaver_matrix` (по умолчанию `true`) выбирает холст: дождь вместо звёздного поля; `false` возвращает прежний starfield, где снова действует `screensaver_stars`. Лента команд сверху, справка и load/RAM снизу остаются в обоих случаях. На раз холст переключается из TUI: `:screensaver matrix` / `:screensaver stars` (settings.yml не трогает, поэтому можно сравнить «на глаз»); неизвестный аргумент — `Usage:` по-прежнему. Интерфейс `MatrixRain` повторяет `StarField` (`tick` / `resize` / `render_text`), поэтому `DevopsScreensaver._make_field` выбирает холст, а дальше всё рисуется одинаково; холст берётся из `app.screensaver_matrix`, если не задан явно. Тесты: `tests/test_screensaver.py` (40: +4 юнит на дождь — темп «меньше полстроки за кадр», падение и перезапуск столбцов, глифы и палитра хвоста, воспроизводимость по seed и resize; +4 на холст — дождь по умолчанию, `screensaver_matrix: false` возвращает starfield, `:screensaver stars|matrix` переключают холст без записи в настройки, `Usage:` на неизвестный аргумент).

## v1.118

- **Полный прогон падал: имя сессии утекало между тестами (14 тестов в CI).** `app.apply_instance_name` (его зовёт `:session NAME`) меняет **модульную** `INSTANCE_NAME` и классовые `FILE_HISTORY` / `FILE_BASHRC` — то есть на весь процесс. Новый тест `test_new_window.py::test_session_switch_moves_registration` делал `:session alpha` и не откатывал это (в `test_commands.py` ручной откат был), поэтому все следующие файлы видели чужой инстанс: заголовок окна `IDvjPy_term · alpha` вместо `default`, `secrets_alpha.json`, `inbox_alpha.jsonl`, `history_alpha.txt`. Отсюда падения в `test_screensaver` (2), `test_secrets` (1), `test_session_mailbox` (9), `test_tag_ref_click` (1), `test_ux_extras` (1) — при том что те же файлы по отдельности проходили. Новый autouse-фикстур `isolated_instance_name` в `tests/conftest.py` запоминает `INSTANCE_NAME` / `FILE_HISTORY` / `FILE_BASHRC` и возвращает их после каждого теста, так что сессию можно переключать в любом тесте. Заодно `tests/test_tag_ref_click.py` читает историю по `app.FILE_HISTORY`, а не по захардкоженному `history_default.txt`. Полный прогон: 829 passed.

## v1.117

- **Инструкции для агентов: команды `codegraph` исправлены.** В `AGENTS.md` был указан `codegraph search` — такой подкоманды в CLI нет, и новая сессия получала `error: unknown command 'search'` на первом же исследовании кода; флага `--no-source` тоже нет. Теперь: `codegraph query <символ>` (поиск символов; `-k/--kind`, `-l/--limit`, `-j/--json`) и `codegraph context <задача>` — у него структуру без кода отдаёт `--no-code`; `codegraph explore` — только когда действительно нужен исходник. Добавлена строка про остальное по надобности: `node`, `callers` / `callees` / `impact`, `files`, `status`, `sync` / `index`.

## v1.116

- **Быстрые подсказки `:`-команд.** При вводе `:` открывается список всех команд приложения с однострочным описанием; буквы фильтруют, `Tab`/`Enter` вставляют `:команда ` (запуск — отдельным Enter), `Esc`/`PgUp`/`PgDn` закрывают. `:/text` не перебивается (поиск по журналу); после пробела работают прежние подсказки (`:send ` — сессии, `:llm ` — провайдеры, `:md`/`:ed` — пути). Таблица — новый `src/colon_commands.py` (`COLON_COMMANDS`), источник ввода — `CommandRunner.get_colon_completions`; полноту таблицы стережёт `tests/test_colon_commands.py` (покрытие всех `CMD_*`).
- **Кликабельные команды в `:?`.** `linkify_colon_commands` оборачивает имена `:cmd` в справке в ссылки `[@click=app.insert_colon_draft('cmd')]` (вызывается после `escape_help_markup`, иначе ссылки экранируются); клик вставляет `:команда ` во ввод в позиции курсора, ничего не запуская и не затирая строку — как `!tag` в `??` и `--seed` в `:welcome`. Имена вне таблицы (`:nope`, `:name--`) не трогаются.
- **Инфоблоки — на Line API (мгновенный фокус при клике).** `InfoBlock` был обычным `Static`: при смене фокуса Textual пересобирал strip'ы **всего** виджета — для справки `:?` (284 строки) это ~136–208 ms на каждый клик, отсюда задержка подсветки и возврата во ввод. Теперь `InfoBlock` рендерится через `render_line` с кэшем (общий хелпер `line_api_text_strips`, как у `CommandLineBlock`), а фон фокуса **отделён** от кэша (`_style_without_bg` + наложение на видимую строку), поэтому клик больше не сбрасывает содержимое. Замерено: клик по `:?` 262 → 90 ms, возврат во ввод 230 → 148 ms. Бонус: фокус на инфоблоке больше не теряет разметку (раньше `on_blur` → `exit_line_nav` → `_restore_plain_display` подменял содержимое плоским текстом, и ссылки в `:?` пропадали). Выключается `line_api_blocks: false` / `IDVJPY_LINE_BLOCKS=0`. Остаток задержки — переприменение CSS самим Textual на смену фокуса (~55 ms, растёт с числом виджетов в журнале; `:c` помогает), от наших `:focus`-правил не зависит (проверено).
- **Шаг колеса мыши — 3 строки.** Журнал листался по одной строке за щелчок, из-за чего большие блоки (`:?` ≈ 290 строк) требовали сотен щелчков — при замерах это и выглядело как «торможение» (рендер блоков ~1 ms/кадр и от размера/ссылок не зависит). Теперь шаг совпадает с просмотрщиками (`:log`/F7, md): `WHEEL_SCROLL_LINES = 3` в обоих путях колеса (фокус в вводе и на блоке). Стрелки по-прежнему по строке. Тесты: `test_journal_follow.py` (+1).
- **Выделение мышью в Line-API блоках.** При переводе блоков на `render_line` выделение сломалось: Textual пишет в каждый сегмент `meta['offset'] = (x, y)`, по которому компоситор (`Screen.get_widget_and_offset_at`) сопоставляет клетку экрана с символом текста, а мы рендерили по одной логической строке за вызов — поэтому `y` всегда был `0`, и вся протяжка схлопывалась в первую строку блока. Теперь `_retag_offsets` проставляет настоящий номер строки, а `highlight_selection` (общий для `CommandLineBlock` и `InfoBlock`) рисует подсветку в `render_line` по `Selection.get_span` — раньше её вообще не было (Textual рисует выделение только в `Visual.to_strips`, а Line API его обходит; при этом `Content.to_strips(..., apply_selection=True)` красил span нулевой строки на **каждой** строке блока). У `CommandLineBlock` добавлен `get_selection`: `Static`-визуал у него не обновляется, и выделение извлекалось из содержимого на момент создания блока (`[Executing...]`). **Главное:** разрезанные подсветкой сегменты сохраняли мету исходного (у хвоста — «начало сегмента»), и компоситор начинал сопоставлять клетку не с тем символом: выделение ползло вдвое медленнее курсора и цеплялось за конец строки (`_with_offset` переписывает `meta['offset']` у каждой части). Тесты: `test_line_api_block.py` (+5: протяжка по строкам, подсветка, `:?`, клетка→символ для команды и `:?`).
- **Ctrl+O — консоль под приложением (как в Midnight Commander).** Вывод команд из `>` (`htop`, `vim`, `less`) идёт в настоящий TTY мимо журнала и остаётся только в скроллбеке терминала **под** TUI. `CommandRunner.action_show_console` вызывает `suspend()`, печатает подсказку и ждёт любую клавишу (`/dev/tty` в cbreak; нет управляющего терминала — Enter со stdin), затем возвращается в TUI и обновляет заголовок. Терминал без `suspend` — явная ошибка в журнале. Тесты: `test_ux_extras.py` (+2: порядок suspend→ожидание→resume, `SuspendNotSupported`).
- **Ответ `:llm` — форматированным markdown.** Новый `MarkdownCommandBlock` (создаётся через `_make_command_block(..., markdown=True)`): в `update()` уходит rich-`Markdown`, поэтому заголовки, списки, код и таблицы читаются как документ, а не как моноширинная простыня. Плоская копия остаётся прежней (`text_content` / `_nav_plain_text`), поэтому F3, `:w`, `|`, `$OUT`/`$BLOCK`, поиск и построчный курсор работают как раньше; в простом режиме (F6) и в построчном курсоре markdown не рисуется. Ключ `llm_render_markdown` в `settings.yml` (по умолчанию `true`, пример синхронизирован). Точка отрисовки — новый `CommandBlock._display_payload()`. Тесты: `test_llm.py` (+3: markdown, выключено ключом, простой режим).
- **Подсказки по тегам при наборе `?` + клик «спросить сразу».** `?` раньше молча ждал ввода — имена тегов приходилось помнить. Теперь новый источник `CommandRunner.get_tag_query_completions` открывает список тегов с подсказкой (число команд + комментарий тега, часто используемые — выше); буквы фильтруют, `Tab`/`Enter` вставляют `?tag` без запуска (как у `:`-команд). Строки списка стали кликабельными (`[@click=app.pick_completion(N)]` в `CompletionList._render_list` → `_item_markup`; ссылкой делается только команда — см. пункт ниже), а пункты `?` помечены `run`: клик вставляет `?vault` и сразу выполняет запрос (`CommandInput.apply_completion_item` → `action_pick_completion`). Пункты без `run` (пути, `:команды`, `!tag`) клик только вставляет — прежнее поведение. Тесты: `tests/test_tag_query_hints.py` (7: список, фильтр, `??`/пробел не перебиваются, Tab без запуска, реальный клик мышью выполняет запрос, путь — только вставка).
- **Ожидание ответа `:llm` видно (thinking-анимация).** Запрос идёт в фоновом потоке (`_llm_worker`), и заглушка `[Consulting ds…]` не отличала ожидание от зависания. Теперь в блоке крутится braille-спиннер с временем и лимитом провайдера: `⠋ thinking… 3s / 60s` (`CommandRunner._start_thinking` / `_tick_thinking` / `_thinking_markup`, общий таймер `set_interval(THINKING_TICK=0.1)` на приложение, счётчик кадров — свой). `raw_stdout` не трогается и остаётся стабильным признаком «ещё ждём» (его читает тур `--demo all`), анимация живёт только в отрисовке; снимается в `_on_command_finished` (ответ или ошибка) — таймер останавливается вместе с последним ждущим блоком. В простом режиме (F6) кадр без разметки. Тесты: `test_llm.py` (+3: анимация и разные кадры, ошибка без вечного спиннера, F6 без разметки).
- **Стили переехали в `src/app.tcss`.** Там Textual CSS (`$surface`, `dock`, `layout`, `text-style`), а расширение `.css` заставляло редакторы разбирать файл браузерным CSS-сервером — отсюда ложные `property value expected` / `Unknown property` на каждой `$переменной`. `.tcss` — родное расширение Textual: путь читается из `CommandRunner.CSS_PATH`, упаковка берёт файл через glob (`src/**/*`), так что переименование ничего не ломает. В репозитории — только имя файла; локальный `.zed/settings.json` (он в .gitignore) дополнительно глушит валидацию CSS для этого проекта. Тесты: `tests/test_stylesheet.py` (+4: путь и существование файла, признак Textual-синтаксиса, отсутствие `app.css` в коде/упаковке, попадание в wheel).
- **Ссылка в списке подсказок — только на команде.** `[@click=app.pick_completion(N)]` оборачивал строку целиком, поэтому и подсветка ссылки (`auto_links`) ложилась на всю строку: `?vault  (2)  HashiCorp Vault` выглядело как одна ссылка. Теперь `CompletionList._item_markup` заворачивает только саму команду (`_link_span`: подстрока `CompletionItem.click`, иначе `insert`; не найдена — вся строка, как раньше). Счётчик, комментарий тега и описание `:`-команды остались обычным текстом. Тесты: `test_tag_query_hints.py` и `test_colon_commands.py` (+ по одному: ссылка == `?vault` / `:json`, счётчик и описание вне неё).
- **Тема `matrix` + мягкая подсветка фокуса.** Своя тема (сейчас `MATRIX_THEME` в `src/app.py`, регистрируется в `on_mount`): зелёный фосфор `#00ff5f` на почти чёрном (`#000700`/`#04120a`/`#062012`) — в тон скринсейверу. Пока она активна, на `Screen` висит класс `matrix-mode` (синхронизирует `watch_theme`), и app.tcss красит рамки ввода/подсказок/справки в зелёный; у остальных тем они остались фиолетовыми. Заодно подсветка блока в фокусе стала мягкой: `$primary 25%` вместо сплошного `$primary-darken-1` (замер отрисованного фона в textual-dark: скачок яркости с 65 до 19 над фоном блока — на большом `:?` старое слепило), и теперь она сама подстраивается под любую тему. Тесты: `tests/test_themes.py` (5: палитра, выбор темы из settings.yml и `:theme`, класс/рамки только у matrix, сохранение между запусками, мягкость подсветки).
- **`bump_version` обновляет и справочники.** `DATABASE.md` и `backup_db.md` несли ручной маркер состояния («состояние на **vX.YY**»), который протухал между коммитами (были на v1.93 при v1.115). Теперь они в `version_bump.TARGETS` (новый список `BOLD_VERSION_DOCS`), маркер меняется на текущую версию, а `--check` ловит протухание, как у остальных файлов релиза. Тесты: `test_version_bump.py` (+1 на протухший маркер справочника, фикстуры пополнены).
- **Автоимя `:new` считает работающие окна, а не оставшиеся файлы.** Кнопка «New session» / `Ctrl+N` брала имя по файлам сессии (`history_*.txt` и `.bashrc_term_*` — тот же источник, что у `list_session_names`), а они **остаются** после закрытия окна: каждое нажатие давало следующее `s2`, `s3`, `s4`…, хотя работала по-прежнему одна сессия, и счётчик уползал вверх. Новый `src/session_registry.py`: per-session `session_<имя>.pid` (0600) в data-каталоге — `register` / `unregister`, `active_sessions` (pid-файлы мёртвых процессов подчищаются), `free_session_name` — наименьшее свободное `sN` **среди активных** (плюс имена из `taken`). `:new NAME` резервирует имя сразу pid'ом поднятого терминала (окно при старте перезапишет файл своим pid), поэтому два быстрых `Ctrl+N` дают `s2` и `s3`, а после закрытия `s2` имя снова свободно. `:session NAME` переносит регистрацию на новое имя; `unregister(..., pid=…)` не снимает чужую запись (имя успели переиспользовать). Список сессий для `:send` / `:session` по-прежнему строится по файлам (`list_session_names`: видны и закрытые сессии) — это разные вопросы. Тесты: `tests/test_session_registry.py` (24) и `tests/test_new_window.py` (+5: файлы закрытых сессий не сдвигают имя, два Ctrl+N → `s2`/`s3`, имя освобождается после выхода, `:new NAME` резервирует имя, `:session NAME` переносит регистрацию).
- **Ctrl+клик / двойной клик по `!tag[tid]` в `??` — вставить и выполнить.** Обычный клик как и был: только подставляет ссылку в позицию курсора. `Ctrl+клик` или двойной клик делают то же, что набрать ссылку и дважды нажать Enter: литерал уходит на раскрытие, раскрытая команда выполняется (новый `CommandRunner._run_input_reference` кладёт в очередь ввода два `Input.Submitted` — как «Enter, Enter»). Через разметку это не выразить: Textual 7.3.0 разбирает ключ меты как `[@a-zA-Z_-][a-zA-Z0-9_-]*=` — точку (`@click.ctrl`) написать нельзя, а `App._broker_event` модификаторы ключа **отбрасывает** (сработал бы и простой клик). Поэтому намерение ловит сам блок: `LineNavigable.on_click` вызывается **до** брокера `@click`, в том же сообщении, и кладёт номер клика в серии в `CommandRunner._link_click_run` (`note_block_link_click`), а `action_insert_bang_draft` его читает и сбрасывает: `None` — только вставка, `1` — Ctrl+клик (вставить и выполнить), `>= 2` — двойной клик (вставку сделал первый клик серии, второй только выполняет — иначе ввод получал `!tag[tid] !tag[tid] `, это была старая ошибка двойного клика). Ссылка без tid (`!tag `) не выполняется — сама по себе она не команда; чужие ссылки (`:команды` в `:?`, `.md`, `--seed`) признак сбрасывают — они вставляют или открывают. Клавиатурный путь не изменился («собрал — потом запустил»). Тесты: `tests/test_tag_ref_click.py` (5: обычный клик не запускает, Ctrl+клик и двойной клик выполняют ровно один раз и не дублируют ссылку, `!tag ` без tid только вставляется, чужие ссылки не выполняются и признак одноразовый).

## v1.115

- **`:rg` / `:md` — в истории, переход к строке.** `:rg …` и `:md …` теперь пишутся в `history_*.txt` (повтор по ↑ / поиск через `:h /`), но в подсказках не предлагаются (`RE_HISTORY_ONLY_QUERY` расширен на `rg|md`). `:md <путь>#L<n>` открывает markdown сразу на строке n (как в GitHub); результат `:rg` и клик по `путь:строка` тоже открываются на строке совпадения. В `md_viewer` — `_scroll_to_line` (по `MarkdownBlock.source_range`, с ожиданием рендера), заголовок `· line N`; в `app` — `RE_MD_LINE`. Тесты: `test_md_search.py` (+4: история, `#L`, `:rg N` на строке).
- **Shift+N в просмотрщиках вывода и в поиске по журналу.** Биндинг `shift+n` не срабатывал в реальном терминале: Shift+буква приходит как заглавная `N` (как `"N"` в `json_viewer`), поэтому «предыдущее совпадение» работало только в Pilot-тестах. Теперь добавлен `Binding("N", …)` (и сохранён `shift+n` для терминалов с modifyOtherKeys) в `output_viewer` и в `_LINE_NAV_APPEND_BINDINGS`; плейсхолдер поиска больше не показывает `«/text»` (слэш — только клавиша открытия). Тесты: `N` и `shift+n` в F7-просмотрщике и в журнале.
- **Большие markdown без тормозов.** Textual-виджет `Markdown` создаёт виджет на каждый блок: 550 строк ≈ 1.3 с, 2200 ≈ 6 с, 8800 ≈ 27 с, 13k ≈ 40 с (фактически зависание). Добавлена настройка `md_render_lines` (по умолчанию 1000): `:md` форматирует только файлы до порога; длиннее — исходник в ленивом Line-API `OutputViewerScreen` (общий экран с `:log`/F7): 14k строк ≈ 0.5 с, поиск `/` + `n`/`N`, `#L<n>` точно совпадает со строкой источника (новый параметр `start_line`). Тесты: `test_md_search.py` (+3). Настройка в `settings.example.yml`.
- **`:send` / `:send!` — в истории.** Пересылка в другую сессию теперь пишется в `history_*.txt` (повтор по ↑, поиск `:h /`), но, как `:llm`/`:cht`/`:rg`/`:md`, не предлагается в подсказках: `RE_HISTORY_ONLY_QUERY` расширен на `send!?`. Голый `:send` (справка) не пишется. Тесты: `test_session_mailbox.py` (+2).
- **Пришедшая `:send`-команда снимает скринсейвер.** Заставка реагировала только на свои клавиши/клики/скролл, поэтому пересланная из другой сессии команда оставалась за ней. Новый `_wake_screensaver()` (pop, если на экране `DevopsScreensaver`, + сброс простоя) вызывается в `_deliver_forwarded` — до вставки во ввод / выполнения. Тесты: `test_screensaver.py` (+2).
- **Копирование пути файла из `:md`.** `y` копирует полный путь открытого markdown в буфер (в обоих видах); в форматированном просмотрщике имя файла в шапке кликабельно (`[@click=screen.copy_path]`) и после копирования показывает `copied: /путь`. `OutputViewerScreen` получил `source_path`; для обычного `:log` (вывод блока, не файл) — явное `No file path to copy`. Тесты: `test_md_search.py` (+2), `test_output_viewer.py` (+1).
- **Режим чтения журнала (новый вывод не уводит вид).** Раньше `add_block` безусловно уводил журнал вниз и забирал фокус (в `_should_follow_journal_end` была оговорка «фокус в вводе → следим», но `add_block` его же и ставил), так что фоновой вывод — `:watch`, ответ `:llm`, пришедший `:send`, долгая команда — сбивал чтение. Теперь: если вид отскроллен вверх (`_follow_paused`, ставится из `_scroll_journal_wheel`/`_scroll_journal_and_focus`) или фокус на блоке журнала (`_journal_reading`), блок только монтируется — без scroll-to-end и без перевода фокуса. Слежение возвращается сам при докрутке до низа (`_journal_at_end`) и при отправке строки (`_resume_journal_follow`). Тесты: `tests/test_journal_follow.py` (5).
- **Актуализация документов.** Синхронизированы `DATABASE.md` / `backup_db.md` (маркер состояния `v1.93` → `v1.115`; с v1.116 они в `version_bump.TARGETS` и обновляются автоматически), вычищена нумерация секций `test_cmd.md` (14b/14c/14d и 30–33 по порядку следования), убраны дубли пунктов в `CLAUDE.md` (Key Behaviors) и уточнены формулировки про `y`/клик в `:md` (`README.md`, `help_texts.py`).
- **Чистка `test_cmd.md`.** Убран случайный дубль `**Версия документа**` в середине документа — маркер остался один, в подвале (`bump_version` теперь инкрементит именно его).

## v1.114

- **Поиск по markdown (`:rg <паттерн> [каталог]`) — в т.ч. Obsidian-vault.** Бэкенд — ripgrep (`--json`), если есть в PATH; иначе встроенный обход на Python (скрытые/служебные каталоги пропускаются) плюс подсказка по установке rg. Паттерн — regex, «умный регистр» (нет заглавных — без регистра); база — аргумент → `md_dir` из settings → cwd. Результаты: заголовок (`N matches / M files · backend`) и фрагменты с кликабельными `путь:строка` (открываются встроенным md-просмотрщиком), `:rg <N>` — открыть N-й (1-based), лимит 200 с пометкой обрезки. `:md` теперь принимает и путь (абсолютный или относительно `md_dir`/cwd) — через `md_viewer.resolve_md_path`. Новый модуль `src/md_search.py`; настройка `md_dir`; тесты — `tests/test_md_search.py`.

## v1.113

- **`:send` раскрывает `|@label` / `|@N` в полный вызов.** Метки буферов живут в памяти одной сессии, поэтому раньше пересланная `:send beta |@buff awk …` доходила как есть и в целевой сессии падала с `no labelled block 'buff'` (а при совпадении имени могла молча взять *её* блок). Теперь у отправителя ссылка раскрывается в `<источник> | <команда>` (буфер не передать — источник в целевой сессии выполнится заново); если метки нет у отправителя, команда не отправляется вообще — явная ошибка. Метод `_materialize_pipe_source`; тесты — `tests/test_block_labels.py`.

## v1.112

- **Подсказки из истории при наборе (`history_completion`).** В выпадающем списке теперь есть не только БД и `session_history`, но и строки `history_*.txt` по подстроке (свежие сверху, маркер `↺`, лимит 20, дедуп с командами). Важно: появляются и строки, начинающиеся с `@` и `>` — их не было в `session_history` (для `@` команда запускается уже без префикса), из-за чего казалось, что история их «не подхватывает». `Tab`/`Enter` вставляют полную строку, следующий `Enter` — запуск. `history_completion: false` оставляет только `↑`/`↓` и `:h /text`; короткий ввод (<2) и `:`/`!`/`?`/`#`/`$` — без истории. Метод `get_history_completions`; тесты — `tests/test_history_completion.py`.

## v1.111

- **`file_completion: auto | paths | off`.** Раньше файловые подсказки включались на **любое** второе слово: `kubectl get po`, `docker co`, `git ch` забивали список содержимым cwd и глушили подсказки из БД/истории. Теперь режим `auto` (по умолчанию) листит файлы только для явных путей (`./`, `/`, `~/`, есть `/`/`\`) и `cd`/`pushd`, а голое имя файла — только после команд, работающих с файлами (`FILE_ARG_COMMANDS`: cat/vim/grep/awk/cp/…). `paths` — только явные пути и `cd`/`pushd`; `off` — выключено; неизвестное значение → `auto`. Логика — `_is_path_context` в `src/app.py`; тесты — `tests/test_file_completion.py`.

## v1.110

- **F8 — диалог метки блока.** `src/block_label.py` (`BlockLabelScreen`, modal): поле предзаполнено текущей меткой (`select_all`), Enter — сохранить, пустое значение — снять метку, Esc — отмена; невалидная метка — явное сообщение. Метка работает как `:name` (`|@label <command>` без перезапуска источника). Логика меток вынесена в хелперы `_assign_block_label` / `_remove_block_label` / `_remove_block_label_by_name` / `_clear_block_labels` и используется и `:name`, и диалогом. Биндинг `F8 → name_block`; целевой блок без команды — `No finished command block to label.`

## v1.109

- **AGENTS.md: в GitHub пушим только в `main`.** На `origin` не держим рабочих/экспериментальных веток; локальные эксперименты уходят в `main` (squash/merge), временную ветку после слияния удаляем и локально, и на `origin`. Ветка `line-api-experiments` (из неё собран v1.103) удалена.

## v1.108

- **Метки буферов (`:name`) и пайп из конкретного блока (`|@label cmd` / `|@N cmd`).** Позволяет пометить блок с дорогим выводом (`cat big.json`, `kubectl get -o json`) и подбирать фильтр (`awk`/`jq`) без повторного запуска источника: `:name buff` → `|@buff awk '{...}'`. Формы: `:name <label>` (пометить сфокусированный/последний завершённый), `:name` (список), `:name <label>-` (снять), `:name -` (все). `|@N` — N блоков назад (0 = последний); чисто цифровые метки запрещены, чтобы `|@3` было однозначно индексом. Метка видна в шапке (`[buff]`), живёт в памяти сессии и чистится вместе с `:c` (иначе ссылка держала бы блок). В `history_*.txt` пайп с явным источником пишется **полным** вызовом `<источник> | <команда>` (воспроизводимо по ↑/`:h`). Нюанс: stdin — это `raw_stdout` блока (без завершающего перевода строки), как и у обычного `|`. Тесты — `tests/test_block_labels.py`.

## v1.107

- **`pyrightconfig.json`: окружение для `experiments/`.** Папка не входила в `include`, поэтому `from app import …` в bench-скриптах резолвилось в корневой лаунчер `app.py` (он реэкспортирует имена динамически) — редактор показывал `Import "app" could not be resolved`. Добавлены `experiments` в `include` и execution environment `{ "root": "experiments", "extraPaths": ["src", "."] }`. Скрипты заодно берут `src` и корень в `sys.path`, чтобы рантайм и анализатор видели один и тот же `src/app.py`; `query_one(…, Input)` — с типом.

## v1.106

- **`:cht <запрос>` — справки cheat.sh (cht.sh).** `:cht tar`, `:cht python read file` (пробелы → `+`), `:cht ~snapshot` (поиск), `:cht go/:learn` / `:list` (спецстраницы); свои опции через `?` (`Q` — без комментариев, `T` — без цветов, по умолчанию `?T`). Запрос уходит в фоновом потоке (urllib, прокси как в `:llm`/`:update`), ответ — обычный блок журнала (`$OUT`, `|`, F3, F7 с поиском). `cht.sh` отдаёт `text/plain` только «curl»-подобному User-Agent — UA задан как `curl`, ANSI-последовательности дополнительно вырезаются. Запросы пишутся в `history_*.txt` (↑, `:h`), но не в подсказки (как `:llm`). Модуль — `src/cheat_sh.py`; настройки `cheat_sh_url` / `cheat_sh_options`; тесты — `tests/test_cheat_sh.py`.

## v1.105

- **Фикс подсветки Line-API-блока.** Кэш `Strip`'ов зависел только от ширины, а фон берётся из `visual_style`: после фокуса оставались старые полосы с фоном «без фокуса», и в начале строк (на пробелах) было чёрное поле. Теперь ключ кэша — `(ширина, visual_style.rich_style)`, фон обновляется при фокусе/теме. Тест — `tests/test_line_api_block.py::test_line_api_block_repaints_on_focus`.
- **Поиск в просмотрщике вывода (F7 / `:log`).** `/` открывает поле, Enter — поиск вперёд, `n`/`N` — следующее/предыдущее совпадение (с заворотом, регистр не важен), Esc — закрыть поле. Совпадение подсвечивается. Модуль — `src/output_viewer.py`; тесты — `tests/test_output_viewer.py`.
- **Модальные экраны больше не отдают клавиши фону:** `CommandRunner.on_key` выходит при активном `_modal`-экране, и фокус не улетает на поле ввода за модалкой.

## v1.104

- **Стабилизация `test_bundled_all_plays`.** Тест опрашивал DOM и мог потерять короткоживущий блок между двумя `pilot.pause()`: тур `all` делает `:c` (чистка журнала), а на `demo_speed=25` блок успевал исчезнуть до снимка → флейк в полном прогоне. Теперь все блоки запоминаются по ссылке через `add_block`, а `raw_stdout`/`text_content` читаются в конце (актуальны даже для удалённых блоков).

## v1.103

- **Блоки журнала на Textual Line API (`CommandLineBlock`).** `render_line` + кэш `Strip`'ов на текущую ширину: разметка парсится один раз, перерисовка зависит от числа видимых строк, а не от размера вывода. Перенос строк совпадает с обычным `Static`; построчный курсор рисуется `Style(reverse)` в `render_line`, а не перезаписью текста. Единая фабрика `CommandRunner._make_command_block()` для shell / `calc` / `:llm` / `:watch`. Переключатель — `line_api_blocks` в `settings.yml` (по умолчанию `true`) или `IDVJPY_LINE_BLOCKS`. Замер (`experiments/line_api_block_bench.py`, 300 строк): движение курсора 1.46 мс → 0.006 мс. Модуль — `src/app.py` (`CommandLineBlock`, `_make_command_block`); тесты — `tests/test_line_api_block.py`.
- **Полный вывод блока в Line-API просмотрщике (`:log` / F7).** `src/output_viewer.py` — прокрутка без обрезки в 300 строк, строки вывода (как F3), уже без escape-кодов + `STDERR`. Обрезка журнала переведена на `rsplit` (без списка всех строк).
- **Фикс `textual.markup.MarkupError`.** Пользовательский текст (`cat` JSON, логи с `[`) экранируется для рендера (`escape_display_markup`), из-за ошибки разметки блок больше не залипает в `[Executing...]`. Тест — `tests/test_markup_safety.py`.

## v1.102

- **AGENTS.md: раздел «Исследование кода».** Правило для агентов: при исследовании всегда предпочитать `codegraph search` / `codegraph context` (для чистой структуры — с `--no-source`); `codegraph explore` (полный исходный код) — только когда действительно нужен код символа, а не его расположение и связи.

## v1.101

- **`pyrightconfig.json`: execution environment для корня репозитория** (`{ "root": ".", "extraPaths": ["src"] }`). Теперь `src` в путях и для файлов в корне (`app.py`, `backup_db.py`, `bump_version.py`, `setup.py`), а не только для `src`/`tests`/`docker` — редактор не жалуется на импорты из `src`. Набор сканируемых файлов (`include`) не меняется.

## v1.100

- **Fix: `Import "version_bump" could not be resolved` в редакторе.** Корневой `bump_version.py` делал обычный `import version_bump`, а для корня репозитория в `pyrightconfig.json` нет execution environment с `src` в путях. Теперь модуль загружается по пути через `importlib.util.spec_from_file_location` — как `app.py` и `backup_db.py`; лишний импорт не нужен, и имя модуля не может столкнуться с этим лаунчером. Поведение то же (`python3 bump_version.py --check` / `--dry-run` / `--set`).

## v1.99

- **Fix: `"main" is not a known attribute of module "backup_db"` (basedpyright в редакторе).** Корневой `backup_db.py` импортировал `import backup_db as _backup`, и имя модуля совпадало с самим же файлом — анализатор резолвил self-import и не видел `main`. Теперь модуль загружается по пути через `importlib.util.spec_from_file_location` (как корневой `app.py`), возвращаемый тип — `Any`. Поведение лаунчера не изменилось (`python3 backup_db.py --help`, `export`/`import`/…).

## v1.98

- **`bump_version.py` — версия в один запуск.** Раньше каждый коммит требовал вручную синхронизировать 8 файлов; теперь `python3 bump_version.py` поднимает минор `CommandRunner.VERSION` и обновляет все маркеры разом (README, COMPACT_SUMMARY + строка Manual plan, CLAUDE, AGENTS, test_cmd.md + версия документа, tests/test_cmd_scenarios.py, DEMO.md). Флаги: `--set vX.YY` (явно), `--dry-run` (diff), `--check` (синхронность, exit 1). Секция `## <версия>` в COMPACT_SUMMARY добавляется заглушкой — текст вписывает автор. Логика — `src/version_bump.py`, проверки — `tests/test_version_bump.py` (12 тестов на временном репозитории).
- Docs: README (раздел «Версия = коммит»), CLAUDE.md (модуль), AGENTS.md (пункт 11).

## v1.97

- **Имя сессии в заголовке окна терминала и в шапке приложения.** `_base_title()` = `IDvjPy_term · <сессия>`; `_refresh_running_title()` достраивает `— N running` и пишет OSC 0 в драйвер (`_set_terminal_title`; Textual сам заголовок окна не ставит), обновляется на старте, при `:session` (`_switch_session`) и после выхода из `> cmd` / `:ed` (ребёнок вроде `vim`/`htop` мог поменять заголовок). Стартовый блок показывает `session: <имя>` (`format_startup_help(session)`).
- Docs: README, `:?` (help_texts), CLAUDE.md.
- Тесты: `test_title_shows_running_count` (заголовок с сессией), `test_terminal_title_has_session_and_osc`, `test_colon_session_creates_and_switches`.

## v1.96

- **Скринсейвер не запускается при работе мышью.** Скролл колесом (`on_mouse_scroll_down/up` в `CommandRunner` и `CommandInput`) и движение мыши (`on_mouse_move`, throttle 0.5 c от `_ss_move_bump`) теперь сбрасывают таймер простоя, как клавиши и клик. Раньше чтение длинного вывода колесом считалось простым, и звездопад появлялся поверх журнала.
- Тесты: `tests/test_screensaver.py` (+2: скролл и движение мыши перезапускают таймер).

## v1.95

- **Tab-подсказки имён сессий после `:send ` / `:send! `** (`CommandRunner.get_send_completions`, вызов из `CommandInput._show_completions` после `:llm`): список из `list_session_names` (+ `*` — всем остальным; текущая помечена `(this session)`), фильтр по набранному префиксу. Список гаснет, когда начинается команда (пробел за выбранным именем); Tab/Enter подставляют имя.
- Docs: `:?` (help_texts), README (`:send` + Tab).
- Тесты: `tests/test_session_mailbox.py` (+3: пункты/префикс, гашение после команды, Tab).

## v1.94

- **`:send <сессия|*> <команда>` — пересылка команды в другую сессию** (окно `:new`): команда вставляется во ввод целевой сессии (запуск там — отдельным Enter); `:send!` — выполнить сразу; `*` — всем сессиям, кроме своей. Команда материализуется у отправителя (`$VAR`/`$OUT`, алиасы), значения секретов `$$` маскируются (`****`) и в ящик не попадают. Новая сессия — модуль `src/session_mailbox.py`, ящик `inbox_<instance>.jsonl` (0600, JSON Lines, append под portalocker-lock как `history_*.txt`); получатель опрашивает свой ящик таймером (`MAILBOX_POLL_INTERVAL = 1` с) и `drain_inbox` читает-обнуляет файл — сообщение для незапущенной сессии ждёт её старта. Пересылка дописывается к набранному тексту, не затирая его; во время демо откладывается.
- Docs: README (возможности + таблица префиксов + `:`), `:?` (help_texts), тикер скринсэйвера, CLAUDE.md (модуль + `:`), `.gitignore` (`inbox_*.jsonl`).
- Тесты: `tests/test_session_mailbox.py` (21: unit ящика + Pilot `:send`/`:send!`/`*`/self/секреты/offline-очередь).

## v1.93

- **Аудит документации под v1.92.** Синхронизированы описания, отставшие от фактического поведения:
  - `src/screensaver.py` (`COMMAND_HELP_LINES`): добавлены `:new`, `:cmd`, `:session new`, `:llm offline`, `$VAR=@key`, `$$VAR=val`.
  - `DATABASE.md`: состояние на v1.93; колонки `use_count` / `last_used` (миграция v1.39), `bump_command_usage` / `usage_stats`, поиск `?text` (`search_commands_by_content`, `_escape_like`).
  - `backup_db.md`: актуальная версия, Python 3.12+ вместо 3.7+.
  - `docker/README.md`: в таблицу добавлены `:new`, `:cmd`, `$$`-секреты, `$VAR=@key`, `:o`, `:watch`, `:kctx`.
  - `CLAUDE.md`: `:cmd` / `:new` / `:import` / `:theme` в списке команд; `gui_open.py` — запуск команды в терминале для `:new`.
  - `DEMO.md`: версия приложения (v1.79 → v1.93).

## v1.92

- **`:new [NAME|-] [DIR]` — рабочий каталог новой сессии.** Второй аргумент — `DIR` (раскрывается `~`, нет каталога — явная ошибка `not a directory`); без него — data-каталог. `-`/пустое имя — авто `sN`. В журнале `New window (session N, cwd DIR): …`.
- **Кнопка в футере: `Ctrl+N` → `New session`** (то же, что `:new` без аргументов) — `CommandRunner.action_new_window`, `Binding("ctrl+n", …)`; клик по кнопке в футере тоже работает. README: строка в таблице горячих клавиш.
- Docs: README (`:new`, горячие клавиши), `:?` (help_texts), test_cmd.md (секция 29).
- Тесты: `tests/test_new_window.py` (+4: DIR, авто-имя `-`+DIR, плохой DIR, Ctrl+N).

## v1.91

- **`:new [NAME]` — новое окно приложения в отдельном терминале** (алиас `:session new [NAME]`). Запускает ещё один экземпляр с `--instance-name=NAME --data-dir=<data-каталог>`: своя сессия (`.bashrc_term_<NAME>` / `history_<NAME>.txt`), общий data-каталог и БД тегов. Без имени — свободное `s2`/`s3`. Секреты `$$` в новое окно **не** переносятся (вычищаются из env). Реализация: `gui_open.build_terminal_exec_argv` / `open_terminal_command` (флаг запуска по терминалу: `xdg-terminal-exec`/`kitty` — без флага, `gnome-terminal`/`kgx` — `--`, X-терминалы — `-e`, `xfce4-terminal`/`terminator` — `-x`; `$TERMINAL` используется как есть), `app.CommandRunner._handle_new_window` / `_self_launch_argv` / `_next_session_name`; запуск — `$IDVJPY_LAUNCH` либо `python3 <запущенный app.py>`. Тесты: `tests/test_new_window.py`, `tests/test_gui_open.py`.

## v1.90

- **Фикс флейка `test_journal_search_jumps_to_matching_line`.** Поиск по журналу идёт и по строке-заголовку блока, а в заголовке — таймштамп; иголка `27` совпадала со временем (`17:27:17`), и поиск прыгал на заголовок — тест зависел от часов. Теперь вывод `seq -f 'hit-%02g' 1 40`, иголка `hit-27` не встречается в заголовке/пути. Тестовый фикс, код приложения не менялся.

## v1.89

- **Очистка буфера обмена после вставки секрета.** Ключ `clear_clipboard_after_secret` в `settings.yml` (по умолчанию `false`; пример синхронизирован). При включении после вставки значения в строку `$$NAME=…` (Ctrl+V / Shift+Insert, а также Paste-событие терминала) очищаются CLIPBOARD, PRIMARY и внутренний буфер; обычная вставка (`echo …`) буфер не трогает. Реализация: `CommandRunner._clear_clipboards`, `_maybe_clear_clipboard_after_secret` (вызывается из `action_paste_clipboard` и `on_paste`). Тесты: `tests/test_secrets.py` (+3: включено/по умолчанию/обычный текст).

## v1.88

- **`:cmd [N] [show]` — материализованная команда блока.** Подставляет текущие `$VAR`/секреты в команду блока (N назад, 0 = последний) и кладёт готовую строку в буфер обмена; в журнал — маскированная версия (`****`), `show` печатает полную строку (секреты становятся видны). Так после `vapprole`-логина можно получить готовый `vault write auth/approle/login role_id="…" secret_id="…"`. Реализация — `CommandRunner._handle_expand_command`, константа `CMD_EXPAND`. Тесты: `tests/test_capture.py` (`:cmd`/`show`, `too far back`).

## v1.87

- **Захват значения из вывода блока: `$VAR=@key` / `$$VAR=@key`.** Значение берётся из сфокусированного (или последнего) завершённого блока: строка, первый токен которой равен `key` (таблицы `vault read` / `vault write` — `Key  Value`); `@last` — последняя непустая строка (после `| jq -r .field`). С `$$` сохраняется как секрет (маскирование/файл/`secrets: hidden` в `:llm` — как обычно). Ошибки явные: нет завершённого блока или ключ не найден (со списком ключей). Реализация — `CommandRunner._capture_from_block` + `RE_CAPTURE_VALUE`. Тесты: `tests/test_capture.py`.
- **Vault seed: плейбук `vapprole`.** `role_id` → `secret_id` → login → временный токен, значения переносятся через `$$…=@key`. Обновлены `src/seed_vault.py` и `docs/SEED_VAULT_COMMANDS.md`; тест `tests/test_seed_ops.py::test_seed_vault_inspect_playbooks`.
- Docs: README (таблица префиксов + раздел секретов), `:?` (help_texts), CLAUDE.md, test_cmd.md (1c).

## v1.86

- **Секреты живут только сессию.** Файл `secrets_<instance>.json` теперь **удаляется при выходе** из приложения: хук `CommandRunner.on_unmount` → `_purge_secrets_file()` подчищает все `secrets_*.json*` в data-каталоге (включая `.tmp` и другие инстансы) и убирает имена из `local_env`/`os.environ`. Значения не переживают перезапуск.
- **Секреты не уходят в LLM.** В `:llm` сообщение после всех раскрытий (`$OUT` / `$BLOCK` / `@файл`) проходит через `_mask_secrets`; в шапке блока — `secrets: hidden`. Так секрет не попадёт в промпт, даже если оказался в выводе блока.
- Тесты: `tests/test_secrets.py` +`test_secrets_file_removed_on_exit`, `test_secrets_never_sent_to_llm`. Docs: README (секция секретов), `:?`, CLAUDE.md, test_cmd.md (1b).

## v1.85

- **Секреты: раздел в README с ограничениями.** В «Системе префиксов» добавлен подраздел «Секретные переменные (`$$VAR=value`)» — ввод/хранение/вывод и честные ограничения: маскируется вся строка ввода (имя — в подзаголовке); в интерактивном `> cmd` реальный терминал показывает значение, пока TUI на паузе; напечатанный командой секрет в журнале `****`, но `F3` отдаёт настоящий вывод; строка, начинающаяся с `$$`, всегда трактуется как секрет. Те же оговорки — в `:?` (help_texts) и `test_cmd.md` (секция 1b).

## v1.84

- **Секретные переменные `$$NAME=value` (маскированный ввод/вывод).** Префикс `$$` задаёт секрет: значение прячется прямо в строке ввода (`CommandInput.password` включается, как только после `=` появился первый символ; имя секрета видно в подзаголовке), хранится в отдельном `secrets_<instance>.json` с правами `0600` (не в `.bashrc_term`, не в `history_*.txt`, не в playbook-логе), а в командах подставляется как обычный `$NAME`. При выполнении значение маскируется `****` в шапке блока, в показываемых stdout/stderr (только отображение — `raw_stdout` остаётся настоящим для `|`, `$OUT`, F3) и в `:o`. Формы: `$$NAME=value` (задать), `$$NAME` (статус), `$$NAME-` (удалить). Файл в `.gitignore` (`secrets_*.json*`). Модуль — `src/app.py` (`handle_secret_assignment`, `_set_secret_var`, `_unset_secret_var`, `_save_secrets`, `load_secrets`, `_mask_secrets`); `CommandBlock._mask_for_display`. Тесты: `tests/test_secrets.py`.

## v1.83

- **README hero-гиф — тур `all`.** `screen-demo-ip.gif` заменён на `idvj-all.gif` (запись `--demo all`); запись сделана из нейтрального `cwd` `/tmp/idvj-demo`, личный путь в кадры не попадает.
- **DEMO.md: раздел «Запись гифки (asciinema → agg)».** Пошагово: изолированный data-каталог (`settings.yml` + `llm_providers.yml`), `asciinema rec … -c "env -C /tmp/idvj-demo python3 … --demo all --demo-speed 2 --demo-quit"`, затем `agg --theme nord --font-size 14 …`; ключи `--speed` / `--idle-time-limit` / `--fps-cap` и проверка утечки `grep -c "$HOME" idvj-all.cast`.

## v1.82

- **`.gitignore`: артефакты демо-тура не попадают в git.** Добавлены `library.md`, `library.sh`, `run.sh` (результаты `:export *` / `:alias *`) и `*.cast` (записи asciinema). Гифки по-прежнему добавляются осознанно (`screen-demo-ip.gif` в репо).

## v1.81

- **Встроенный офлайн-провайдер `offline` для `:llm`.** `src/llm_client.py` добавляет в любой загруженный конфиг provider `offline` с `mock: true`: `perform_request` при `mock` возвращает `answer` сразу, без HTTP и без ключей (`load_providers` делает `setdefault` — собственный `offline:` в `llm_providers.yml` имеет приоритет). Нужен для демо и проверки проводки `:llm` / `:llm ask` (контекст, формат, кликабельные refs) там, где нет сети или API-ключа. В `src/llm_providers.example.yml` добавлен пример секции `offline` и поля `mock`/`answer`; в `:?` и README — строка про `:llm offline <сообщение>`.
- **Акт E в туре `all`.** `src/demos/all.yml` теперь показывает LLM: `:llm` (список провайдеров), `:llm offline <сообщение>` и `:llm ask offline <задача>` (в шапке `app-ctx: N tags`). Тур остаётся без сети и ключей; `tests/test_demo.py::test_bundled_all_plays` копирует `llm_providers.example.yml` в data-каталог (как провижининг) и проверяет ответ заглушки. `test_bundled_all_tour_guards` знает про `:llm`-шаги.
- **Тесты LLM:** `tests/test_llm.py::test_offline_provider_is_builtin` (инъекция + mock-ответ + приоритет своего `offline:`); обновлены ожидания подсказок (`:llm o` → `offline, openai`; `:llm ` → `ds, offline, ask`).

## v1.80

- **CI: Docker-джоба гоняет и тур `all`.** После короткого смоука под pty добавлен прогон самого полного bundled-тура (`--demo all --demo-speed 2 --demo-quit`, `--timeout 300`): в контейнере проверяется, что калькулятор/`ipcalc`/JSON-дерево/теги/утилиты рисуются без traceback и автотур сам выходит. Тур сети не требует, поэтому шаг стабилен в CI.

## v1.79

- **Новый bundled-тур `all` — «всё подряд» (`src/demos/all.yml`).** Один прогон по максимуму возможностей, без сети и кластера: локальный счёт (`calc`: `1024*3`, единицы `512Mi + 20% in Gi`; `ipcalc`: `192.168.1.0/24`, `300 hosts`, `8.8.8.8`), журнал (`| grep`, JSON-дерево `Tab → F5` с `$JSON`/черновиком `| jq`, `:o /CrashLoop`), библиотека тегов (`#api`, `?tag[1]`, `??`, `!`/`!!`, `#api+1`, `#api=2=…`, `#api-1` → `#api!1`, `:mv tmp[1] logs`, `:stats`, `:export * library.md`, `:alias api run.sh`), обвязка (`$HOST`, `:env`, `:h 8`, `:c` + `:o`, `:diff`, `:r 1`, `:watch 1 date +%s` / `:watch stop`, `@ sleep 60` + F4, `:backup`, `:kctx`, `:screensaver 120`/`0`). Тур не трогает handbook-теги и не пишет в них: перед повтором жёстко сбрасываются только свои `api` / `logs` / `chain` / `tmp`. Запуск: `python3 app.py --demo all --demo-quit`.
- **Тесты тура `all`:** `tests/test_demo.py::test_bundled_all_tour_guards` (каждая возможность — шагом; нет `:q`, TTY `>`, `:fm`/`:term`/`:ed`, `wait_command` на colon-шагах, бесконечных `loop`) и `test_bundled_all_plays` (прогон: `calc`/`ipcalc` строки, `CrashLoop` из JSON, `:stats`, экспорт `library.md`/`run.sh`, `:backup`, `:kctx`). Документация: `DEMO.md` (автотур + Акт 5), `README.md`, `CLAUDE.md`.
- **CLI-подсказки `--demo`** перечисляют все bundled-имена: `short, full, ip, features, all` (argparse help и `load_demo_for_cli`).

## v1.78

- **Фикс: `./` в подсказках показывал только каталоги.** Список путей молча обрезался до 20 записей (`get_completion_candidates` → `file_cands[:20]`), а файлы сортируются после каталогов — в каталоге с 25 подкаталогами файлы в подсказки не попадали вовсе, находились только по началу имени (`./t`). Обрезка убрана: список путей идёт целиком, а у списка уже есть окно и прокрутка, в счётчике — полное число (`1–N / M ↓more`). Лимит 20 остался там, где он осмыслен: команды из БД/истории, k8s-ресурсы (`k8s_completion`). Тест: `tests/test_completion.py::test_dir_slash_shows_files_after_many_dirs` (25 каталогов + файл: `./` отдаёт >20 записей и файл из хвоста, каталоги по-прежнему со слешем).

## v1.77

- **`:ed` — короткое имя внешнего редактора** (было `:editor`; фича из v1.70, переименование до релиза, поведение не менялось). Внутренние имена остались описательными: модуль `src/editor_open.py`, ключ `editor:` в `settings.yml`, `_handle_editor_command`. Заменено везде: `:?`, подсказки/ошибки («`Usage: :ed [<file>|$OUT|$BLOCK]`»), докстринги, `docker/README.md`, тесты.
- **README: список `:`-команд и Docker.** В перечень команд приложения добавлены отсутствовавшие: `:llm` / `:llm ask` / `:llm reset`, `:ed`, `:o`, `:stats`, `:mv`, `:diff`, `:kill` / `:watch`, `:alias`, `:kctx` (раньше они были только в разделах-возможностях). Раздел «Демостенд в Docker» дополнен: что внутри образа (alpine, `bash`/`nano`/`git`/`curl`/`jq`/`procps`, без CLI `docker`/`kubectl`), что делает первый запуск (шаблон + 849 команд), запуск без compose и CI-смоук.

## v1.76

- **CI собирает демостенд и смоукит его.** Job `docker-demo` в `.github/workflows/tests.yml`: сборка `docker/Dockerfile` через BuildKit с кэшем GitHub Actions (`docker/build-push-action`), затем проверки — первый запуск создаёт `/data/settings.yml` и `/data/llm_providers.yml` из шаблонов и сеет библиотеку; в томе действительно непустая библиотека (`usage_stats`); второй запуск не пересеивает и не оставляет снимков посева; TUI рендерится и короткий тур завершается. Для последней проверки в образ добавлен `docker/tui-smoke.py`: поднимает настоящий pty (в CI терминала нет, а Textual требует tty), задаёт размер 120×40, читает отрисованное, падает на traceback/таймауте и умеет требовать подстроку (`--expect`). `pyrightconfig.json` теперь проверяет и `docker/`. Тесты: `tests/test_docker_stand.py` +1 (job существует, использует build-push-action и смоук-скрипт); полный набор — 580.

## v1.75

- **Демостенд в Docker** — потрогать TUI без установки Python. `docker/Dockerfile` на `python:3.12-alpine` (плюс `bash` — приложение запускает команды и TTY через `/bin/bash`, `ncurses-terminfo-base` — terminfo для `TERM=xterm-256color`, `nano` — редактор из шаблона, `git`/`curl`/`jq`/`procps` — чтобы seed-команды реально работали); зависимости из `requirements.txt`; образ ~100 МБ. `docker/compose.yaml` — сервис `idvjpy` с `tty`/`stdin_open` (TUI без TTY не запустится) и именованным томом `idvjpy-demo-data`, контекст сборки — корень репозитория. `docker/entrypoint.sh`: в пустом томе создаёт `/data/settings.yml` и `llm_providers.yml` из шаблонов, один раз (если в БД нет live-команд) сеет linux/k8s/git/ops (~5 с, 849 команд) и убирает снимки, сделанные самим посевом, затем `exec` `app.py` с проброшенными аргументами (`--demo short --demo-quit` и т.п.). `.dockerignore` держит контекст маленьким (`.git`, `.venv`, `tests/`, `packaging/`, данные, сборки). Документация стенда — `docker/README.md` («что попробовать», автопоказ, данные/сброс, что заведомо не работает), краткая — в README. Тест `tests/test_docker_stand.py` статически стережёт согласованность (без сборки образа). Проверено сборкой и запуском: `docker compose run --rm idvjpy --help` и `--demo short --demo-quit` — exit 0, без трейсбеков.

## v1.74

- **Порядок в `.gitignore`.** Разделы с заголовками (личные данные приложения / корневой скретч / venv / сборка / кэш), убраны мёртвые строки (шаблон `.`, дубль `packaging/dist/`). Добавлены явные исключения для файлов, которые специально живут в репозитории, но попадали под широкие шаблоны: `!/requirements.txt`, `!/requirements-dev.txt` (от `/*.txt`), `!/test_cmd.md` (от `/test*.*`). Добавлен `playbook.yml` — локальный сценарий `:playbook`, который не должен уезжать в git (в `AGENTS.md` уже был в списке «не коммитить», теперь обеспечен технически). Venv-каталоги привязаны к корню, `lib64` — без слэша (обычно симлинк на `lib`, шаблон с `/` его не ловит). Набор игнорируемых файлов до/после сверен — ничего локального не стало видимым.

## v1.73

- **`settings.yml` больше не в git.** Личные настройки уходят в `.gitignore` (`/settings.yml`) и удалены из индекса: они не могут утечь во внешний репозиторий. Источник правды — шаблон `src/settings.example.yml`, из него файл создаётся при первом запуске в новом data-каталоге (портативный режим со своим `settings.yml` не трогается). Шаблон синхронизирован с прежним рабочим файлом: все ключи и комментарии на месте (`max_lines`, `history_lines`, `history_keep`, `database_tags_file`, `backup_dir`, `command_timeout`, `terminal_mouse`, `theme`, `check_updates`, `screensaver_idle`, `screensaver_stars`, `k8s_completion`, `editor`), редактор по умолчанию — `nano` (mcedit требует отдельной установки; иначе берётся `$VISUAL`/`$EDITOR`). Docs: README (раздел «Конфигурация» ссылается на шаблон), COMPACT/CLAUDE, AGENTS. Тесты: шаблон парсится и содержит все ключи + `editor: nano`; провижининг копирует именно шаблон; `/settings.yml` в `.gitignore`.

## v1.72

- **Фикс: `:o /` давало файловые подсказки.** Аргумент `:o /text` (grep по сессионной истории выводов) начинался с `/`, и path-completion предлагал листинг корня — лишний список поверх поиска. Теперь `:h`, `:o`, `:g` объявлены командами без путей (`CommandRunner.COLON_NO_PATH_ARGS`) и файловое дополнение для них не работает (для `:h /` такое исключение было точечно). `:cd /`, `:w /…`, `:ed /…`, `:md` и прочие пути по-прежнему дополняются. Тесты: `tests/test_output_history.py` (`:o /` без файловых подсказок; `:cd /…` — всё ещё путь).

## v1.71

- **`:ed` — подстановка `$VAR`/`$OUT` в пути.** Аргумент-путь проходит через ту же подстановку, что обычные команды (`substitute_variables`): `local_env` (`$VAR=…` в TUI, `.bashrc_term`) → `os.environ`, плюс ленивый `$OUT` (последняя непустая строка сфокусированного/последнего блока). Так путь из вывода блока не надо перенабирать: `:ed $TMPDIR/pod-$OUT.json`. Нераскрытый `$NAME` — явная ошибка со списком имён (иначе редактор создал бы файл с именем «$NOPE.yaml»); `$OUT` в пути без завершённого блока — тоже явная ошибка («/tmp/.json» — не путь). Новый хелпер `shell_env.unexpanded_variables`. Docs: `:?`, README, test_cmd. Тесты: +4 app-level (`$DIR/$OUT` в пути, undefined-переменная, пустой `$OUT`, успешный `created`) и +1 юнит `shell_env`.

## v1.70

- **`:ed` — внешний редактор для файла, `$OUT` и `$BLOCK`.** Новый модуль `src/editor_open.py` (без Textual): `resolve_editor` (settings.yml `editor:` → `$VISUAL` → `$EDITOR` → системный список: sensible-editor / nano / vi / vim, Windows — notepad; значение может содержать аргументы, напр. `editor: code --wait`), `build_editor_command` (shlex-экранирование пути), `write_temp_text`/`read_text_file`. Запуск — в настоящем TTY через существующий `_run_in_tty` (TUI на паузе, как `> cmd`), после — подхват env/PWD. `:ed <файл>` правит файл на месте (`saved` / `unchanged` / `created` / `was not created`); `:ed $OUT` / `$BLOCK` (и `${…}`) берут последнюю непустую строку / весь stdout сфокусированного-или-последнего блока в временную копию: одна строка результата уходит во ввод (запуск — Enter), многострочный остаётся файлом с показанным путём (для `@файл` / `| cmd`); `:ed` без аргумента — пустой буфер. Ключ `editor:` добавлен в `src/settings.example.yml` и рабочий `settings.yml`. Ошибки явные: каталог вместо файла, нет блока, нет редактора, битые кавычки. Docs: `:?`, README, COMPACT/CLAUDE, test_cmd. Тесты: `tests/test_editor.py` — 15 (юнит: приоритет источника, отсутствие бинарника, кавычки, temp-roundtrip; app-level: файл на месте, создание/не-создание, `$OUT` → ввод, `$BLOCK` → файл, пустой буфер, unchanged, нет блока, usage/каталог, нет редактора, ключ из settings.yml).

## v1.69

- **`:llm ask <провайдер> <задача>` — выбор модели для режима ask.** Первое слово после `ask` — имя провайдера (берётся только если есть в `providers`); без него работает `default:`, как раньше. Задача — всё остальное (`:llm ask grok найди поды и покажи логи`). Ошибки явные: без задачи — `Usage: :llm ask [<provider>] <task in your words>` со списком провайдеров; без `default:` и без имени — `needs a provider`. `:r` сохраняет исходную строку вместе с явным провайдером. Подсказки: после `:llm ask ` и `:llm ask <префикс>` предлагаются провайдеры (без псевдо-`ask`), после имени — начинается задача (только `@файлы`).

## v1.68

- **Фикс: клик по ссылке `!tag[tid]` из `:llm ask` не вставлял команду.** В `@click` стояло `app.action_insert_bang_draft`, а Textual сам ищет `action_<имя>` — получался несуществующий `action_action_insert_bang_draft`, клик молчал (подсветка ссылки при этом была). Теперь ссылка строится общим хелпером `_clickable_bang_ref` (действие `app.insert_bang_draft`, как в `??`); у хелпера появился параметр `prefix` — «!» входит в кликабельный токен целиком. Регрессионный тест идёт тем же путём, что Textual: meta → `App.run_action` (Pilot-клик meta не несёт — обходит `App.on_event`).

## v1.67

- **`:llm ask <задача>` — обучение LLM возможностям приложения.** Новый режим: провайдеру по умолчанию уходит задача + «шпаргалка» (префиксы `#tag` / `?tag` / `!tag[tid]` / `!!` / `|` / `$OUT` / `$BLOCK` / `:llm`) + выжимка живой библиотеки тегов (тег, комментарий, tid, команда). Теги сортируются по совпадению слов задачи (комментарии seed-справочников на русском, поэтому и русский запрос попадает), в бюджет влезают детально, остальные — списком имён (модель не выдумывает tid). Ответ — готовые ссылки; существующие `!tag[tid]` из ответа дополнительно показываются кликабельной строкой (`action_insert_bang_draft` — вставка во ввод, без автозапуска). Тот же контекст для обычного `:llm` даёт ключ провайдера `app_context: true|N` (`N` — бюджет символов, по умолчанию 6000; нет ключа/false — выключено, поведение прежнее). Контекст идёт в system перед правилом языка (`answer_language`). Модуль `src/llm_context.py` без Textual и сети; в шапке блока — `app-ctx: N tags`. Подсказки: `ask` после `:llm ` (провайдеры первыми, Enter по-прежнему выбирает default). Docs: `:?`, README, `llm_providers.example.yml`. Тесты: +11 (юнит: парсинг ключа, приоритет тегов, бюджет/индекс, фильтр ссылок, порядок system; app-level: ask шлёт контекст, кликабельные refs только реальные, ask без default/задачи, ключ провайдера, completion `ask`).

## v1.66

- **`:llm` — контекст беседы (`history_turns`).** Провайдер может задать `history_turns: N` — приложение держит в памяти сессии последние N пар `user/assistant` **на провайдера** и добавляет их в `messages` (авто-тело: между system и текущим сообщением; шаблон — плейсхолдер `%HISTORY%`, JSON-массив). По умолчанию `0` — как раньше (без контекста). `:llm reset [<провайдер>|*]` очищает ветку. В шапке блока — `ctx: K/N turns`. Обрезка не оставляет «висячих» assistant-ов; лимит `MAX_HISTORY_TURNS=50`. Контекст — только память сессии (в файлы/БД не пишется). Логика в `llm_client` (`history_turns_for`, `trim_history`, `append_exchange`). Docs: `:?`, README, `llm_providers.example.yml`. Тесты: +6 (обрезка/добавление, тело с историей, `%HISTORY%`, app-level два хода + reset).

## v1.65

- **`:llm` — вложение файлов (`@путь`).** Сообщение может содержать `@файл` (несколько подряд): содержимое вкладывается в запрос блоком в ``` (ограждение подбирается по файлу, путь — как info-string). Только текст UTF-8; ошибки явные — нет файла, каталог, бинарник (NUL), больше лимита. Лимит `DEFAULT_MAX_ATTACHMENT_BYTES` (200 KB) переопределяется ключом `max_attachment_bytes` у провайдера. Литеральный `@` — `@@`; email (`user@host`) не трогается. В `source_command` блока и в `history_*.txt` остаётся исходная строка с `@файлом` (содержимое не оседает; `:r` перечитает файл). В шапке блока — `@files: имя (N)`. Подсказки: после `:llm … @` — имена файлов каталога (каталоги с `/`). Логика — `llm_client.expand_file_refs` (без Textual). Тесты: 5 юнит (раскрытие, несколько/экранирование, безопасный забор, ошибки, без ссылок) + app-level (содержимое ушло, источник/история чистые) + completion.

## v1.64

- **Расширение k8s-цепочек расследования** (`seed_k8s_chains.py`, `K8S_CHAINS.md`):
  - `kns` +2: `kubectl get nodes -o wide`, `kubectl auth can-i --list -n $NS` (права/контекст);
  - `kpod` +2: jsonpath `phase/reason/message` (почему Pending) и custom-columns `NAME/RESTARTS/NODE/IP`;
  - `kev` +2: современный `kubectl events` (1.23+) — `--types=Warning` и `--for pod/$POD`;
  - новые секции **`kavail`** (HPA: метрики; PDB: disruptions) и **`kstore`** (PVC/PV: застрявший том);
  - новые плейбуки **`kscale[1]`** (HPA/PDB/метрики/events) и **`kvolume[1]`** (PVC → describe → PV → events);
  - канонические tid: `docs/SEED_K8S_CHAINS_COMMANDS.md` (+ таблица симптомов: HPA, Pending-том, Forbidden, drain/evict); цикл в TUI в `K8S_CHAINS.md` дополнен шагами 6-8; подсказка в `seed_catalog.py`.
  - Тесты: `tests/test_seed_k8s_chains.py` + проверка, что все `!tag[tid]` в цепочках указывают на существующие теги/tid.

## v1.63

- **Актуализация seed-справочников.** `seed_linux_commands.py` (tag `kube`): команды pod/deploy/svc переведены на переменные стека — `$POD`, `$DEPLOY`, `$SVC` (были литералы `POD/DEPLOY/SVC` рядом с `$NS`; теперь как в `seed_k8s_chains.py` и `:kctx`), у строки логина — подсказка про `:kctx`. В `src/.bashrc_term.example` добавлены недостающие переменные kubectl-стека (`POD DEPLOY ING APP QUOTA`; `SVC`/`CTR` — в блоке docker). Доки: `docs/SEED_LINUX_COMMANDS.md` синхронизирован; в `seed_systemd.py` start/stop помечены «меняет сервис» (как restart). Проверено: остальное актуально (git switch/restore, `helm uninstall` без `--name/--purge`, `docker compose` v2 первичен, `netstat` — «старые хосты», `strace` — с `timeout`).

## v1.62

- **Выделение мышью копируется в буфер.** Textual-выделение работало и раньше, но скопировать было нечем (наш priority `Ctrl+C` перехватывал). Теперь `CommandRunner.on_text_selected` (сообщение Textual после протяжки) сразу кладёт выделенное в CLIPBOARD/PRIMARY/OSC 52 (та же утилита, что F3/Ctrl+C), с сообщением `Copied selection (N chars)`. `Ctrl+C` при наличии выделения копирует его (иначе — строка ввода/блок). Простой клик буфер не трогает; `Shift`+протяжка остаётся нативным выделением терминала. Тесты `tests/test_mouse_selection.py`.

## v1.61

- **Установка прямо из git.** Корневой `pyproject.toml` + `setup.py` с кастомным `build_py`: на этапе сборки актуальный `src/` копируется во вложенный ресурс `packaging/idvjpy_boot/src` (как `packaging/build_wheel.sh`), версия берётся из `CommandRunner.VERSION`. Теперь работают `pipx install git+https://github.com/webxed/IDvjPy`, `uv tool install git+https://github.com/webxed/IDvjPy`, `pip install .`; `MANIFEST.in` везёт `src/` в sdist. `packaging/idvjpy_boot` читает версию и из исходного `src/app.py` (в checkout нет вложенной копии). Тесты: `tests/test_packaging_root.py` (корневой и packaging pyproject не разъезжаются, `setup.py --version`, MANIFEST).

## v1.60

- **Undo во вводе (`Ctrl+Z`).** `CommandInput` ведёт стек предыдущих состояний value+курсор (`_watch_value`, лимит 100): отменяется печать, удаление символа/слова, word-delete, вставка. Стек сбрасывается после отправки команды (Enter) и по `Ctrl+D`. Примечание к word-delete: `Ctrl+Backspace` срабатывает только если терминал шлёт его отдельной клавишей (часто приходит как обычный Backspace) — универсальный вариант `Ctrl+W`. Тесты `tests/test_input_words.py` расширены (undo удаления и набора).

## v1.59

- **Удаление по словам во вводе.** В `CommandInput` добавлены алиасы `Ctrl+Backspace` (слово слева) и `Ctrl+Delete` (слово справа) — канонические `Ctrl+W` / `Ctrl+F` и word-навигация `Ctrl+←/→` уже встроены в Textual `Input`. Удобно подчищать вставленные длинные строки (поля `kubectl`): не нужно жать Backspace посимвольно. Тесты `tests/test_input_words.py`.

## v1.58

- **`:kctx` — кластерный журнал kubectl-стека (UI).** `:kctx` — список кластеров из `kctx.json`; `:kctx <cluster>` — вход (`klogin <c> || kubectl config use-context <c>` — fallback, когда tsh недоступен) и список ранее использованных наборов переменных стека (`NS POD DEPLOY SVC ING APP CTR QUOTA`); `:kctx N` применяет набор из последнего открытого списка; `:kctx <cluster> N` — вход и применение одной строкой. Применение пишет те же `.bashrc_term_<instance>` и env, что `$VAR=…` (общий `_set_env_var`; рефакторинг `handle_variable_assignment`). Подсказки: после `:kctx ` — имена кластеров из журнала. Справка `:?`. Pilot-тесты `tests/test_kctx_cmd.py`.

## v1.57

- **Кластерный журнал kubectl-стека (подготовка к `:kctx`).** `src/kctx_store.py`: файл `kctx.json` в data-каталоге со снимками `{cluster, ts, vars}` — vars только из kubectl-стека (`NS POD DEPLOY SVC ING APP CTR QUOTA`). Вход в кластер (`klogin X` / `tsh kube login X` / `kubectl config use-context X`) запоминается как текущий; присваивание переменной стека (`$NS=…`) при известном кластере дописывает/обновляет снимок (идентичный последнему — только bump времени; лимиты на кластер и всего). Запись под portalocker-локом, как history. Ошибки журнала не мешают присваиванию. Хранилище без Textual — юнит-тесты `tests/test_kctx_store.py`. UI (`:kctx`) — следующим коммитом.

## v1.56

- **fix: статическая типизация boot-модуля.** `packaging/idvjpy_boot` больше не обращается к атрибутам `app` через статический `import app` (анализатор резолвил его на корневой лаунчер и не видел `parse_arguments` / `load_demo_for_cli` / `CommandRunner`). Теперь модуль грузится через `importlib.import_module("app")` из вложенной `src/` (sys.path), модуль типизирован `Any`. Поведение не меняется.

## v1.55

- **pip-упаковка:** пакет `idvjpy-term` (`packaging/`). `packaging/build_wheel.sh` копирует текущий `src/` во вложенный ресурс boot-пакета `idvjpy_boot/src` и собирает wheel (без сети, `--no-build-isolation`); console script `idvjpy`, запуск также `python -m idvjpy_boot`. Boot-модуль добавляет вложенную `src/` в `sys.path`, поэтому топ-левел импорты (`app`, `database_v2`, …) и ресурсы (`app.tcss`, `demos/`, примеры конфигов, `.bashrc_term.example`) работают из установленного пакета. Версия wheel = `CommandRunner.VERSION` → `MAJOR.MINOR.0`. Данные пользователя остаются вне пакета (data-каталог v1.54). Сборка проверена: установка wheel в чистый каталог, headless-`run_test` (provisioning из встроенных примеров) и реальный `idvjpy --demo short --demo-quit` в pty.

## v1.54

- **Data-каталог (подготовка к pip):** выбор места хранения settings/БД/history — приоритет: `--data-dir` → `$IDVJPY_DATA_DIR` → «портативный режим» (текущий каталог, если в нём `settings.yml` — так работают repo/тесты) → системный каталог ОС (Linux `~/.config/idvjpy`, macOS `~/Library/Application Support/IDvjPy`, Windows `%APPDATA%\IDvjPy`). Модуль `src/data_dirs.py`, флаг в лаунчерах, `CommandRunner(data_dir=…)`.
- **First-run provisioning:** в новом (не портативном) data-каталоге при первом запуске автоматически создаются `settings.yml` (из `src/settings.example.yml`) и `llm_providers.yml` (из примера). `FILE_LLM_PROVIDERS` теперь тоже пинится в data-каталог.

## v1.53

- **Калькулятор без спец-команд** (`src/calc.py`, без `eval`): строка, начинающаяся с цифры (или `(` / `-`) и целиком разбираемая как арифметика/перевод единиц, считается локально, результат — блок с заголовком `calc:`. Арифметика `+ - * / ^ ( )`; проценты относительно левого операнда (`512Mi + 20%`, `512Mi - 15%`, `512Mi * 20%`, `2 + 10%`); `of` — доля от значения (`20% of 512Mi`, `1/3 of 1Gi`). Единицы памяти: `B`, SI `K/M/G/T…` = `KB/MB/GB…` (×1000), IEC `Ki/Mi/Gi/Ti…` = `KiB/MiB/GiB…` (×1024), k8s-стиль `512Mi`/`1.5 Gi`; перевод `in`/`to`; CPU `m` (миллиядро) и `cores`; безразмерные числа как байты (`524288 in Mi`); `1Gi/512Mi` → 2. Не-расчёты (`7z …`, `(cd …)`, `2>/dev/null …`) по-прежнему уходят в shell.
- **ipcalc как jodies.de/ipcalc** (`src/ipcalc.py`): IPv4-строка считается локально — `192.168.1.0/24`, маска `255.255.255.0`, голый адрес (классовая маска). Показывает Address · Netmask (= N) · Wildcard · Network/prefix · HostMin · HostMax · Broadcast · Hosts/Net с бинарной колонкой, классом/RFC1918; `/31` point-to-point (RFC 3021), `/32` host route. Обратная задача: `300 hosts` → минимальный префикс (`/23`, 510 usable). Ошибки (октет/префикс/маска) — явные, не молчаливый shell.
- **Справка**: полный справочник в TUI — `:? calc` (обновлены `src/help_texts.py`, `README.md`, `COMPACT_SUMMARY.md`, ручной план `test_cmd.md`).

## v1.52

- **Стабильный выход `:watch`:** фоновый поток-цикл больше не постит тики и финализацию в остановленный цикл событий (выход из приложения / завершение теста) — раньше это давало `RuntimeError: Event loop is closed` в фоновом потоке, из-за чего CI-тесты флейкали. Теперь поток тихо гасится. Внутренняя стабильность: поведение `:watch` для пользователя не меняется.

## v1.51

- **Язык ответа `:llm`:** поле провайдера `answer_language` (напр. `Russian`) дописывает к system жёсткое правило — «отвечай на <язык>, не переключайся (в т.ч. не отвечай по-китайски), если пользователь явно не попросил». Билингвы вроде DeepSeek иначе периодически отвечают не на языке пользователя. Работает и в авто-теле, и в шаблоне через `%SYSTEM%`. Пример конфига обновлён.

## v1.50

- **Чистая история:** команда, упавшая с `command not found` (exit 127, стд-ошибка bash), автоматически убирается из `history_*.txt` и session history — ↑/`:h` не подсовывают опечатки (`Жр`). Ошибка остаётся в журнале. `history_store::remove_history_file_line` (exclusive flock, удаление последнего вхождения).

## v1.49

- **`:llm` в истории:** запросы `:llm …` пишутся в `history_<instance>.txt` (как `# command`-комментарии) — повтор по ↑ и поиск `:h /` работают, но в Tab-подсказках они не предлагаются (это вопросы, не команды). Другие colon-команды в историю по-прежнему не попадают.

## v1.48

- **`:llm` принимает вывод блока:** в сообщении `$OUT` → последняя непустая строка сфокусированного/последнего CommandBlock, `$BLOCK` → весь stdout этого блока (записи `$VAR` и `${VAR}`). Нет завершённого блока — явная ошибка.

## v1.47

- **`:llm` без имени провайдера:** `:llm Привет как дела` уходит провайдеру по умолчанию (`default:` в llm_providers.yml); `:llm <имя> <текст>` — как раньше. Неизвестное имя без `default:` — явная ошибка со списком провайдеров.

## v1.46

- **Tab-дополнение имён провайдеров** для `:llm `: после `:llm <префикс>` список из `llm_providers.yml`, Tab/Enter вставляет имя (заменяется только токен, префикс `:llm` сохраняется, пробел добавляется). Список гаснет, когда начато сообщение.

## v1.45

- **LLM через API:** `:llm <провайдер> <сообщение>` — конфиг `llm_providers.yml` в каталоге запуска (образец `src/llm_providers.example.yml`): url/model/system/headers/body/response_path/timeout. Ключи — только из окружения (`$VAR` в headers/body). Плейсхолдеры тела: `%MSG%`/`%SYSTEM%`/`%MODEL%` (JSON-escaped) и `%MSG_RAW%`; без `body` — авто OpenAI-совместимое chat/completions. `:llm` без аргументов — список провайдеров. Ответ — в блок журнала (фоновый поток, таймаут из конфига); ошибки HTTP/сети/конфига — явные. Модуль `src/llm_client.py`, urllib без новых зависимостей.

## v1.44

- **UX:** `:r N` — команда блока N назад (`:r 0` = последний); в заголовке `— N running` при активных фоновых командах / `:watch`; `:alias <tag> [file.sh]` / `:alias * [library.sh]` — экспорт команд как bash-функций `tag_tid() { …; }`.

## v1.43

- **k8s автодополнение:** `kubectl get <res> <Tab>` подтягивает имена ресурсов из живого кластера (`kubectl get <resource> -o name`, таймаут 1.5 c). Включается `k8s_completion: true` в settings.yml (по умолчанию false — без задержек и сети). Если kubectl не настроен — мягкий fallback (пустой список, обычное дополнение не ломается). Контекст перехватывается до path-дополнения. Модуль `src/k8s_complete.py`.

## v1.42

- **Сессионная история вывода:** завершённые команды (stdout/stderr/exit) держатся в памяти (кольцо 300, только память — не БД и не история ввода). `:o [N]` — последние N выводов; `:o /text` — grep по stdout/stderr (переживает `:c`); `:o clear` — сброс.

## v1.41

- **`:diff`:** unified diff (difflib) stdout сфокусированного блока против предыдущего CommandBlock; без фокуса — два последних. Цвета: `-` красный / `+` зелёный / `@@` голубой, обрезка 300 строк, одинаковый вывод — явная подпись.

## v1.40

- **Экспорт каталога в Markdown:** `:export * [library.md]` — весь каталог live-команд по тегам: `## tag — comment` + строки `` `cmd` `` с комментариями строк; пустая БД — явная подпись. `:export <tag> [file.json]` не изменился.

## v1.39

- **Метрики использования:** колонки `use_count` / `last_used` в `commands` (миграция в `init_db` на лету). Счётчик растёт, когда исполняемый текст совпал с live-командой (в т.ч. `!tag[tid]` / `!ID` / повтор из истории; тики `:watch` не считаются). `:stats` — сводка: теги, live/soft-deleted/never-run, per-tag по запускам, топ-10 команд. В списке `!tag` часто используемые команды — выше.

## v1.38

- **`:mv tag[tid] tag2` / `:mv tag tag2`:** перенос одной команды в другой тег (новый tid в конце; комментарий команды едет с ней) и переименование тега целиком (live + мягко-удалённые, комментарий тега переносится). Явные ошибки: несуществующая команда/тег, целевой тег занят, невалидное имя. Кэш библиотеки инвалидируется.

## v1.37

- **`:watch <sec> <command>`:** периодический перезапуск одной команды в одном блоке (мониторинг без `watch -n` в shell). Тики нумеруются `watch #N · every Xs`; каждый тик — отдельный Popen (`start_new_session`), вывод обрезается как у обычного блока. Стоп: `:watch stop`, `F4`/`:kill` (ловят текущий тик), `:c`, выход из приложения. Один watch на сессию — повторный запуск с явной ошибкой.

## v1.36

- **Поиск по содержимому команд:** `?text` (2+ символа, не точный тег) — подстрочный поиск по `command` и `comment` всех live-строк (case-insensitive, `%`/`_` буквально, `ESCAPE`). Заголовок `Search 'text' in commands (N)`, строки `<id> tag[tid]` кликабельны/вставляемы, `last_query_results` заполнен — `!ID` запускает найденное. Точный `?tag` не изменился; `?<1 символ>` — явная ошибка. `src/database_v2.py::search_commands_by_content`.

## v1.35

- **Остановка фоновой команды:** `F4` / `:kill` (`:kill all`) шлют SIGTERM группе процесса (`start_new_session`), через `KILL_GRACE` сек — SIGKILL. Блок получает подпись `Process stopped by user.` и код 143 (128+SIGTERM). При выходе из приложения оставшиеся процессы останавливаются. `_execute_in_thread` переведён с `subprocess.run` на `Popen` + `communicate(timeout)` — дескриптор в `_proc_registry`.

## v1.34

- **Производительность:** автодополнение больше не открывает SQLite на каждое нажатие — live-команды кэшируются в памяти и обновляются по mtime/при мутациях. `add_command` и импорт тега — в транзакции (нет гонки за `tid` и N+1). Журнал кэширует список блоков между изменениями DOM; фоновая перезагрузка БД гейтится по mtime и чистит удалённые id; casefold истории кэшируется.

## v1.33

- **`@ cmd`:** выполнить команду без `command_timeout` (долгие не-TTY задачи; stdout захватывается). История хранит строку с `@`, повтор по ↑ ведёт себя так же.
- **CI и инструменты:** GitHub Actions гоняет pytest на push/PR в `main`; `tests/test_release_meta.py` сверяет версию в доках с `CommandRunner.VERSION`; dev-зависимости вынесены в `requirements-dev.txt`; тяжёлые Pilot-наборы помечены `slow` (быстрый прогон: `-m "not slow"`).
- **Рефакторинг:** работа с `history_*.txt` и файловые блокировки — в `src/history_store.py`, статичные тексты справки `:?` / `:i` — в `src/help_texts.py`; удалены мёртвые `src/database.py` и `src/command_parser.py`.
- **Доки:** 25 seed-справочников переехали в `docs/` (из TUI открываются как раньше), устаревшие `readme.ru.md` и `SESSION_SUMMARY.md` удалены — корень репозитория разгружен.

## v1.32

- **Screensaver:** `screensaver_stars: false` в `settings.yml` убирает летящие пыль и токены; чёрный холст — часы/дата, лента библиотеки, справка и load/mem остаются.
- **`:?`:** журнал прокручивается к началу блока справки, а не к верхушке журнала — длинная справка сразу в кадре.

## v1.31

- **Screensaver:** снизу слева печать справки команд; снизу справа `load avg` и `mem` (опрос `/proc` раз в секунду). Зелёная лента тегов — на всю ширину сверху.
- **`:cd`:** меняет cwd для shell; `mytags.db`, история и `.bashrc_term*` остаются в каталоге запуска.
- **`> cmd` / `:env`:** после TTY подхватываются `export` и `$PWD` той же оболочки; `:env` перечитывает `.bashrc_term*`.
- **`??`:** клик по тегу вставляет `!tag` в позицию курсора, не затирает строку.

## v1.30

- **`:fm` / `:term`:** проводник и системный терминал в новом окне (cwd или путь). Не ждут GUI и не забирают этот TTY. Linux / macOS / Windows; `$FILEMAN` / `$TERMINAL` перекрывают дефолт.
- **Screensaver:** среди звёзд летают живые часы и дата; слоган-кометы убраны; звёзды медленнее.

## v1.29

- **Screensaver library:** сверху starfield — ярко-зелёная бегущая строка с перемешанными командами из БД (`!tag[tid]  cmd`). Спрятанные handbook-теги (`#name--`) пропускаются. Пустая БД — только звёзды.
- **`:welcome` / разделы:** каталог seed по `:welcome` (как при пустой БД). Старт с непустой БД показывает живые теги по разделам handbook.
- **`:backup`:** снимок SQLite в `backups/` (`mytags-manual-….db`). `--seed` делает такой же снимок сам (`*-pre-<seed>-….db`).
- **`:update` proxy:** `$PROXY_USER` / `$PROXY_PASS` in `.bashrc_term` are inserted into `HTTPS_PROXY` / `HTTP_PROXY` so a 407 authenticating proxy can fetch GitHub. If those vars are unset and the proxy returns 407, `:update` prints how to set them.

## v1.28

- **Screensaver:** после `screensaver_idle` секунд простоя (по умолчанию 120, `0` = выкл) — полноэкранный starfield в духе Norton Commander, ближе к зрителю токены `k8s` / `git` / `!tag` / `!!`. Сверху зелёная лента библиотеки; снизу справка команд (печать слева направо, пауза, случайный порядок). `:screensaver` — сразу; любая клавиша или клик закрывает и не попадает во ввод. Во время `--demo` не стартует.

## v1.27

- **`:session`:** show the current instance (`:session`) or switch/create one (`:session ops`). Per-instance `history_*.txt` and `.bashrc_term_*`; tags DB stays shared. Journal stays; playbook log clears.

## v1.26

- **Playbook `loop`:** `loop: true` (until Esc) or `loop: N` at the top of a YAML, or a step `loop: 10` with `type:` / nested `steps:`. For polling a health URL without re-running setup.

## v1.25

- **History compact:** `:h compact` uniques old `history_*.txt` lines; the last `history_keep` lines stay a sequence. Startup compact only if the file is longer than `2 × history_keep`.
- **`:update`:** compare local `VERSION` with `src/app.py` on GitHub `main`. Startup notifies only when remote is newer (`check_updates: true`).
- **Versioning:** bump the minor `CommandRunner.VERSION` (`v1.N`) on every commit.

## v1.24

- **Handbook hide:** `#ansible--` / `#linux--` / `#k8s--` (and other seed names) soft-deletes every tag of that handbook. `#name!!` restores. `#tag-` still hides one tag.
- **`??` / `?` Hidden:** fully hidden tags (no live rows) are listed with `#tag!` / `#group!!`. They do not appear in `!` completion or command-prefix suggestions.
- **Empty-DB welcome:** colored seed catalog at the top of the journal. Click a `--seed` line to insert it into the input (Enter runs it). Click a `.md` name or `:md file.md` opens a formatted Markdown viewer (Esc/q closes; wheel stays in the modal). Needs `terminal_mouse: true`.
- **`:playbook`:** dump this session's Enter-submitted lines to YAML for `python3 app.py --demo file.yml`. `:playbook -` previews; `:playbook clear` resets. Keys/mouse/TTY are not recorded.

## v1.23

- **`$OUT`**: last non-empty line of the focused (or last) command block, computed only when the command contains `$OUT` / `${OUT}`. Not stored in `.bashrc_term` or `local_env`. `$OUT=` is rejected; `$OUT` alone peeks.
- **`--demo ip`**: myip → jq `.cc` → Wiki URL → tag `hello` pipe (`!! hello[1]|hello[2]`) → `echo "Hello, $OUT"`; `# comment` lines before commands. Demo tags from `#tag cmd` are wiped before playback so a second run does not duplicate tids.
- **`--demo features`** (v1.44): автотур новых команд — `?text`, `:mv`, `:stats`, `F4`/стоп, `:watch`, `:diff`, `:r N`, `:o`, `:export *`, `:alias`; см. `DEMO.md`.
- **Ansible seed:** `python3 src/seed_ansible.py --seed` — tags `ansible` `aplay` `avault` `agalaxy`, inspect playbooks `achk` / `aping`. Included in `seed_ops.py`.
- **Systemd seed:** `python3 src/seed_systemd.py --seed` — `sctl` (systemctl), `jctl` (journalctl), `dmesg`; inspect playbooks `sfail` / `sstat` / `kmsg`.
- **Sysinfo seed:** `python3 src/seed_sysinfo.py --seed` — `hinfo`, `lsof`, `strace`; playbooks `hstat` / `lport` / `pdbg`. Attach `strace -p` is time-bounded or `> cmd`.
- **Pipe seed:** `python3 src/seed_pipe.py --seed` — `sort` `uniq` `cut` `tr` `wc` `xargs` `tee` `jq` for `|` / `!!`.
- **IP seed:** `python3 src/seed_ip.py --seed` — `ip` / `ethtool`; inspect playbooks `ilink` / `iiface`.
- **Sysstat seed:** `python3 src/seed_sysstat.py --seed` — `vmstat` `iostat` `mpstat`; playbook `oload` (finite `$DELAY`×`$SAMPLES`). `htop`/`iotop`/`iftop` as `> cmd`.
- **Netdbg seed:** `python3 src/seed_netdbg.py --seed` — `tcpdump -c`, `nc -vz`, `mtr -r`, `openssl s_client`; playbooks `npath` / `tlschk`.
- **Pkg seed:** `python3 src/seed_pkg.py --seed` — `apt` `dnf` `rpm` query; `aptq` / `rpmq`. install is not in playbooks.
- **User seed:** `python3 src/seed_user.py --seed` — `ident` / `perm`; playbook `uidchk`. No `userdel`; chmod/chown not in the playbook.
- **nft / zip:** `seed_netfw` adds `nft` / `nftstat`; `seed_host` adds `zip` / `zstat` (list only in playbooks).

## v1.22

- **History file per instance:** `--instance-name=user1` uses `history_user1.txt` (same pattern as `.bashrc_term_user1`). Default is `history_default.txt`. Legacy `history.txt` is copied once if the instance file is missing.
- **`↑`/`↓`** in the input walk that file (plus this session). Typed text filters matches; empty input walks everything; Down past newest restores the draft.
- **`:h /text`** searches the instance history in the completion list (unique lines, newest first). Esc then Enter dumps a journal block. Empty `:h /` is the same as `:h`.
- History search uses an in-memory cache (reload on mtime/size). Appends take one exclusive flock so several app copies do not race on the same file.
- **`# command`** (space after `#`) parks the line in history and the journal without running it, like a bash comment. `#tag cmd` (no space) still saves a tag.
- **Demo mode:** `python3 app.py --demo` (or `--demo full`, `--demo path.yml`) types a YAML scenario into the live TUI for screen recordings. Esc stops; `--demo-quit` exits at the end; `--demo-speed` scales delays. Bundled files: `src/demos/*.yml`.

## v1.2

- Application code in `src/`; cwd holds `settings.yml`, the command DB, `.bashrc_term*`, `history_<instance>.txt`.
- Empty command DB shows a seed catalog (linux, k8s chains, git, `seed_ops.py`, individual ops).
- [`K8S_CHAINS.md`](K8S_CHAINS.md) is the investigation overview; tids are in [`SEED_K8S_CHAINS_COMMANDS.md`](docs/SEED_K8S_CHAINS_COMMANDS.md).

## This session (v1.1.25 → v1.1.52)

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
- **`??` / `?tag`**: command comments (`#tag=ID=comment`) are shown as dim `# comment`. Tag refs `tag[tid]` are Rich-escaped so `[tid]` does not swallow the rest of the line. Click a tag header / `tag[tid]` inserts `!tag ` / `!tag[tid] ` at the input cursor (does not replace the line; `terminal_mouse: true`).
- **`#tag=ID=comment`**: ID is tid first, then global `<id>` from `??`. Missing command → error (no fake success). UPDATE only live rows.
- **Completion list** grows with the number of hints (up to 24 / terminal height). Footer always shows whether the list is complete (`8/8 all`) or truncated (`1–16 / 40 ↓24 more`).
- **Line-cursor toggle** is **F2** (was F7).
- **Copy block** is **F3** (was F5). JSON viewer is **F5**.
- Footer hints: Esc Focus Input, F2 Line cursor, F3 Copy Block, F5 JSON Viewer, F6 Simple output.
- **`> cmd`**: suspend the TUI and run with a real TTY (`> htop`, `> vim file`). No timeout, stdout is not captured. `>>` is left to the shell. On exit the same bash's `export`/`unset` and `$PWD` are imported; `:env` re-reads `.bashrc_term*` without a TTY.
- Click a journal block to focus it. Arrows / PgUp / PgDn scroll the journal and activate the **visible** block without jumping to its first line. `terminal_mouse: true` is required for clicks.
- Alias bodies with `$1` / `$2` / `$@` substitute arguments (`klogin cluster` → `tsh kube login cluster`). Aliases without `$1` still append the rest of the line.
- **`cd` / `:cd`**: change the process cwd for shell commands (standalone `cd`, no `&&`). Tags DB, history, and `.bashrc_term*` stay in the launch directory. `:fm` / `:term` open the OS file manager or a system terminal in a new window (detached; `$FILEMAN` / `$TERMINAL` override). `:r` puts the focused block command into the input. `:/text` / `:g` / `:n` / `:N` search journal **lines** (line-cursor on the hit; `n`/`N` on a focused block). `/` on a block starts `:/`. `#tag!` restores soft-delete. `:export` / `:import` one tag as JSON.
