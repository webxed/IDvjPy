# IDvjPy_term — Compact Summary

TUI на Textual для запуска shell-команд с тегированной историей в SQLite. Версия: **v1.51**.

Запуск: `python3 app.py` (лаунчер; код в `src/`). Тесты: `python3 -m pytest tests/ -v`. Демо-запись: `python3 app.py --demo`.

Пустая БД: в журнале каталог seed. Клик по `--seed` вставляет команду во ввод; клик по `.md` или `:md файл.md` открывает справочник. Цепочки k8s: [`K8S_CHAINS.md`](K8S_CHAINS.md).

Параллельный порт: `Idivjopy_rust` (ratatui). Поведение ниже — про Python, если не сказано иное.

---

## Commands

| Prefix | Action |
|--------|--------|
| (none) | Execute shell command |
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

Aliases from `~/.bashrc`: bodies with `$1` / `$2` / `$@` substitute args; otherwise the rest of the line is appended.

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
| `test_cmd.md` | Manual plan v1.6 (app v1.51) |
| `tests/test_cmd_scenarios.py` | Sections of `test_cmd.md` (Pilot keypresses), alias `$1` |
| `tests/test_commands.py` | echo, history, vars, paste, Ctrl+D clear input, `:c`/`:q`, merge `.bashrc_term` + `_default`, `> cmd` TTY prefix, `:env`, empty-DB seed catalog, `:md`, `:backup`, `:fm`/`:term`, click `--seed` insert, history compact, `:session` |
| `tests/test_tags.py` | save with `-`/`=`, bang, delete, `#name--` / `#name!!` |
| `tests/test_completion.py` | Tab path, `ls ~/`, no `cat cat`, Tab→last journal block (`:h`/`:?`), line-cursor, trailing-space Enter, Shift+Enter/Ctrl+V/Paste append, `!tag` ref completion, click/PgUp visible-block focus |
| `tests/test_json_viewer.py` | expand, search, F5 from focused cat, bracket keys, jq draft / `$JSON` |
| `tests/test_demo.py` | YAML `--demo`, `:playbook`, `loop: N` / `loop: true` |
| `tests/test_gui_open.py` | `:fm` / `:term` argv by OS, `$FILEMAN` / `$TERMINAL`, detached spawn |
| `tests/test_screensaver.py` | starfield, `:screensaver`, idle timer, key swallowed |
| `tests/test_seed_*.py` | linux / k8s chains / git / ops handbooks; pre-seed SQLite backup; empty-DB catalog text |

Isolated tmp cwd + test DB. `submit()` clears input, dismisses completion, then Enter.

---

## Files

| File | Purpose |
|------|---------|
| `app.py` | Launcher (`python3 app.py`) |
| `src/app.py` | TUI (`CommandRunner`), v1.51 |
| `src/screensaver.py` | Idle starfield + flying clock/date + full-width green ticker + bottom help (left) and load/mem (right) (`:screensaver`) |
| `src/database_v2.py` | SQLite tagged history |
| `src/seed_groups.py` | Handbook name → tags for `#name--` / `#name!!` |
| `src/seed_catalog.py` | Empty-DB welcome catalog (click `--seed` / `.md`) |
| `src/md_viewer.py` | Modal Markdown viewer (`:md`, welcome links) |
| `src/k8s_complete.py` | Имена ресурсов k8s из живого кластера (`kubectl get`) |
| `src/update_check.py` | Compare `VERSION` with GitHub main (`:update`) |
| `src/llm_client.py` | LLM-запросы по `llm_providers.yml` (`:llm`) |
| `src/llm_providers.example.yml` | Образец конфига провайдеров LLM |
| `src/gui_open.py` | `:fm` / `:term` detached file manager / terminal |
| `src/json_viewer.py` | JSON tree modal |
| `src/ingress_analyzer.py` | `:i` k8s |
| `src/command_parser_v2.py` | `!tag[tid]` / `!ID` assembly |
| `src/history_store.py` | `history_<instance>.txt` append/read/compact, file locks |
| `src/help_texts.py` | Static `:?` / `:i` help texts |
| `src/seed_*.py` | Handbook seeds (linux, k8s, git, ops, …) |
| `src/app.css` | Styles (JSON viewer, line-nav border, block focus) |
| `settings.yml` | DB path, timeout, `terminal_mouse`, `theme`, `check_updates`, `history_keep`, `screensaver_idle`, `screensaver_stars` (cwd) |
| `K8S_CHAINS.md` | k8s investigation overview |
| `docs/SEED_*_COMMANDS.md` | Canonical tids per handbook |
| `DATABASE.md` | How commands are read from SQLite |
| `test_cmd.md` | Manual test script |

---

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
