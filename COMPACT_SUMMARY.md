# IDvjPy_term — Compact Summary

TUI на Textual для запуска shell-команд с тегированной историей в SQLite. Версия: **v1.86**.

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
| `:` | `:q` `:w` `:h` `:c` `:json` `:i` `:?` `:cd` `:fm` `:term` `:env` `:session` `:welcome` `:backup` `:screensaver` `:r` `:/` `:g` `:n` `:N` `:export` `:import` `:theme` `:md` `:playbook` `:update` `:kill` `:watch` `:mv` `:stats` `:diff` `:o` `:alias` `:llm` |
| `\|` | Pipe focused/last block stdout (saved in history) |
| `$OUT` | On demand: last line of focused/last block (not stored) |
| `$VAR=val` | Set local env (also `$ VAR=val`); writes `.bashrc_term_<instance>` |
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
- `-n` without value → explicit error (no silent fallback).

### CLI
- Root `app.py` is a launcher; the TUI module is `src/app.py`. `--instance-name` is parsed in the launcher / `src/app.py` `__main__` (pytest imports `src/app.py` via `pythonpath = src`).
- Instance bashrc: `.bashrc_term_{instance}` in cwd. Template: `src/.bashrc_term.example`.
- Instance history: `history_{instance}.txt` in cwd. Legacy `history.txt` is copied once if the instance file is missing.
- Empty command DB (`has_live_commands` is false): welcome InfoBlock lists handbook seeds (journal starts at the top). Click `--seed` to insert; click `.md` or `:md` to open the viewer (`terminal_mouse: true`). A live DB is snapshotted to `backups/` before `--seed` replaces its tags (`:backup` does the same by hand).

---

## Tests

| File | Coverage |
|------|----------|
| `test_cmd.md` | Manual plan v1.33 (app v1.86) |
| `tests/test_cmd_scenarios.py` | Sections of `test_cmd.md` (Pilot keypresses), alias `$1` |
| `tests/test_commands.py` | echo, history, vars, paste, Ctrl+D clear input, `:c`/`:q`, merge `.bashrc_term` + `_default`, `> cmd` TTY prefix, `:env`, empty-DB seed catalog, `:md`, `:backup`, `:fm`/`:term`, click `--seed` insert, history compact, `:session` |
| `tests/test_tags.py` | save with `-`/`=`, bang, delete, `#name--` / `#name!!` |
| `tests/test_completion.py` | Tab path, `ls ~/`, no `cat cat`, Tab→last journal block (`:h`/`:?`), line-cursor, trailing-space Enter, Shift+Enter/Ctrl+V/Paste append, `!tag` ref completion, click/PgUp visible-block focus |
| `tests/test_json_viewer.py` | expand, search, F5 from focused cat, bracket keys, jq draft / `$JSON` |
| `tests/test_demo.py` | YAML `--demo` (short/full/ip/features/all, guardrails тура `all`), `:playbook`, `loop: N` / `loop: true` |
| `tests/test_gui_open.py` | `:fm` / `:term` argv by OS, `$FILEMAN` / `$TERMINAL`, detached spawn |
| `tests/test_screensaver.py` | starfield, `:screensaver`, idle timer, key swallowed |
| `tests/test_docker_stand.py` | Файлы docker-стенда: seed-скрипты в entrypoint, compose-том/TTY, Dockerfile, `.dockerignore`, job CI |

Isolated tmp cwd + test DB. `submit()` clears input, dismisses completion, then Enter.

---

## Files

| File | Purpose |
|------|---------|
| `app.py` | Launcher (`python3 app.py`) |
| `pyproject.toml` / `setup.py` / `MANIFEST.in` | Корневая сборка: `pip install .` / `uv tool install git+…` (build_py вкладывает `src/` в `packaging/idvjpy_boot`) |
| `packaging/` | pip-упаковка: `pyproject.toml`, boot-модуль `idvjpy_boot` (вложенная `src/` в sys.path) и `build_wheel.sh` |
| `docker/` | Демостенд для Docker: `Dockerfile` (alpine), `compose.yaml`, `entrypoint.sh` (шаблоны + однократный посев), `tui-smoke.py` (pty-смоук TUI), `README.md` |
| `.dockerignore` | Контекст сборки стенда: без `.git`, venv, `tests/`, `packaging/`, данных и сборок |
| `src/app.py` | TUI (`CommandRunner`), v1.86 |
| `src/calc.py` | Встроенный калькулятор без префикса: арифметика, `%`, `of`, единицы памяти/CPU (`src/ipcalc.py` — IPv4-сети и `300 hosts`) |
| `src/screensaver.py` | Idle starfield + flying clock/date + full-width green ticker + bottom help (left) and load/mem (right) (`:screensaver`) |
| `src/database_v2.py` | SQLite tagged history |
| `src/seed_groups.py` | Handbook name → tags for `#name--` / `#name!!` |
| `src/seed_catalog.py` | Empty-DB welcome catalog (click `--seed` / `.md`) |
| `src/md_viewer.py` | Modal Markdown viewer (`:md`, welcome links) |
| `src/k8s_complete.py` | Имена ресурсов k8s из живого кластера (`kubectl get`) |
| `src/update_check.py` | Compare `VERSION` with GitHub main (`:update`) |
| `src/data_dirs.py` | Data-каталог: `--data-dir` / `$IDVJPY_DATA_DIR` / portable / OS default |
| `src/kctx_store.py` | Кластерный журнал kubectl-стека (`kctx.json` в data-dir, снимки NS/POD/… по кластерам) |
| `src/llm_client.py` | LLM-запросы по `llm_providers.yml` (`:llm`) |
| `src/llm_context.py` | Контекст приложения для LLM: шпаргалка префиксов + выжимка тегов/команд (`:llm ask`, ключ `app_context`) |
| `src/llm_providers.example.yml` | Образец конфига провайдеров LLM |
| `src/settings.example.yml` | Шаблон настроек для первого запуска в новом data-каталоге |
| `src/gui_open.py` | `:fm` / `:term` detached file manager / terminal |
| `src/editor_open.py` | Внешний редактор для `:ed` (settings.yml `editor:` → `$VISUAL`/`$EDITOR` → системный; временные копии для `$OUT`/`$BLOCK`) |
| `src/json_viewer.py` | JSON tree modal |
| `src/ingress_analyzer.py` | `:i` k8s |
| `src/command_parser_v2.py` | `!tag[tid]` / `!ID` assembly |
| `src/history_store.py` | `history_<instance>.txt` append/read/compact, file locks |
| `src/help_texts.py` | Static `:?` / `:i` help texts |
| `src/seed_*.py` | Handbook seeds (linux, k8s, git, ops, …) |
| `src/app.css` | Styles (JSON viewer, line-nav border, block focus) |
| `settings.yml` | Личные настройки — **не в git** (`.gitignore`), создаётся копией `src/settings.example.yml` при первом запуске в новом data-каталоге |
| `src/settings.example.yml` | Шаблон настроек: все ключи с комментариями, `editor: nano` по умолчанию |
| `K8S_CHAINS.md` | k8s investigation overview |
| `docs/SEED_*_COMMANDS.md` | Canonical tids per handbook |
| `DATABASE.md` | How commands are read from SQLite |
| `test_cmd.md` | Manual test script |

---

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

- **pip-упаковка:** пакет `idvjpy-term` (`packaging/`). `packaging/build_wheel.sh` копирует текущий `src/` во вложенный ресурс boot-пакета `idvjpy_boot/src` и собирает wheel (без сети, `--no-build-isolation`); console script `idvjpy`, запуск также `python -m idvjpy_boot`. Boot-модуль добавляет вложенную `src/` в `sys.path`, поэтому топ-левел импорты (`app`, `database_v2`, …) и ресурсы (`app.css`, `demos/`, примеры конфигов, `.bashrc_term.example`) работают из установленного пакета. Версия wheel = `CommandRunner.VERSION` → `MAJOR.MINOR.0`. Данные пользователя остаются вне пакета (data-каталог v1.54). Сборка проверена: установка wheel в чистый каталог, headless-`run_test` (provisioning из встроенных примеров) и реальный `idvjpy --demo short --demo-quit` в pty.

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
