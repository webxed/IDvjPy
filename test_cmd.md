# План тестирования IDvjPy_term v1.83

Ручной прогон TUI и зеркальные автотесты (Textual Pilot).

Автотесты по этому файлу:

```bash
python3 app.py                          # ручной прогон
python3 -m pytest tests/test_cmd_scenarios.py -v
python3 -m pytest tests/ -v             # весь набор, включая JSON/completion/seeds
```

Команды ниже безопасны (`echo`/`printf`/`seq`). Боевые `systemctl`/`nginx` не обязательны.

**Важно:** `#tag` сохраняет команду **как есть**. Ссылки `!tag[tid]` / `!ID` / `!!` раскрываются при **просмотре** `?tag[tid]` и при **выполнении**, не при сохранении.

---

## Подготовка

```bash
python3 app.py
```

При пустой БД журнал открывается **сверху**: баннер, затем каталог seed (ядро / `seed_ops` / ops по отдельности). Автотесты поднимают приложение сами, в изолированной tmp-директории (своя БД, не `mytags.db`). История сессии — `history_default.txt` (не `history.txt`).

Нужен `terminal_mouse: true` (по умолчанию) для кликов по блокам, `--seed` и `.md`.

| Клавиша | Действие |
|---------|----------|
| `Enter` | Отправить команду. Если открыт список подсказок — вставить кандидата, **не** запускать |
| `Esc` | Скрыть подсказки / вернуть фокус во ввод. В Markdown-viewer — закрыть |
| `Tab` | Из ввода — на последний блок журнала; если открыт список подсказок — вставить кандидата |
| `Up`/`Down` | `history_<instance>.txt` во вводе (набранный текст фильтрует); прокрутка журнала, если фокус на блоке |
| `PageUp`/`PageDown` | Прокрутка журнала; активным становится видимый блок (без прыжка к началу) |
| клик по блоку | Фокус на блоке. В пустой БД: `--seed` → во ввод; `.md` → справочник. В `??`: тег → вставить `!tag ` в позицию курсора (строку не затирает) |
| `F2` | Построчный режим |
| `F3` | Копировать stdout сфокусированного блока |
| `Ctrl+C` | Скопировать всю строку ввода; на блоке журнала — весь stdout (как F3) |
| `F5` | JSON viewer для сфокусированного (или последнего) блока |
| `F6` | Simple output |
| `Shift+Insert` / `Ctrl+V` | Вставка во ввод (не затирает уже набранное) |
| `Ctrl+D` | Очистить строку ввода |
| `d` | Тёмная / светлая тема (когда фокус не во вводе) |

---

## Секция 1: Переменные окружения

```
$PROJECT=/tmp/idivjopy_test
$EDITOR=nvim
echo $PROJECT
echo $EDITOR
```

**Ожидание:** `Variable $PROJECT set to ...`; `echo $PROJECT` печатает `/tmp/idivjopy_test`.

Синтаксис: `$VAR=value` или `$ VAR=value`. Локальные переменные приоритетнее `os.environ`. `$OUT` — не переменная сессии, см. секцию 23.

Автотест: `test_s01_variables`.

---

## Секция 2: Сохранение команд с тегами

```
#start echo Starting app
#test echo pytest -v
#deploy echo restart nginx
#backup echo rsync -av /data /backup
#git echo git status
```

**Ожидание:** `Saved: '...' as start[1]` и т.д. Команды с `-` (`rsync -av`) сохраняются, не удаляются.

```
#cfg echo A=B
```

**Ожидание:** сохранение, не комментарий к тегу.

Автотест: `test_s02_save_tags`.

### 2.1. Ссылки при сохранении (v1.1.9+)

```
#start echo START
#deploy echo DEPLOY
#full !deploy[1] && !start[1]
?full
?full[1]
```

**Ожидание:**

- `full[1]` в БД содержит литерал `!deploy[1] && !start[1]` (не раскрыто)
- `?full[1]` показывает шаги Original → Final: `echo DEPLOY && echo START`

Автотест: `test_s02_references_saved_literal`.

### 2.2. Редактирование `#tag+`

```
#dev echo original
#dev+1
```

**Ожидание:** во вводе `#dev echo original`. Enter сохраняет новую версию как следующий tid **или** правка через `#dev+1 echo updated`.

Автотест: `test_s02_edit_plus`.

---

## Секция 3: Переменные в тегированных командах

```
$API=https://api.example.com
#api echo endpoint=$API
!api[1]
```

Enter (если открылись подсказки — сначала Esc).

**Ожидание:** вставка `echo endpoint=$API`, после Enter — `endpoint=https://api.example.com`.

Автотест: `test_s03_vars_in_tagged_commands`.

---

## Секция 4–5: Комментарии

```
#start=Startup commands
#start=1=Start in normal mode
?
?start
??
```

**Ожидание:** в `?` тег с комментарием; в `?start` / `??` комментарий у команды.

Автотест: `test_s04_comments`.

---

## Секция 6: Поиск

```
?
??
?deploy
?missing
```

**Ожидание:** список тегов; все команды с `<gid>` и `tag[tid]`; пустой тег — `(None found)`. После `#name--` в `??` / `?` блок Hidden (`#tag!` / `#group!!`); спрятанные теги не в `!`-подсказках. Клик по тегу в `??` вставляет `!tag ` в позицию курсора (не затирает уже набранное).

Автотест: `test_s06_query`. Hide: `test_hide_and_restore_handbook_group`.

---

## Секция 7: Выполнение по ID

`!` **вставляет** команду во ввод, не запускает.

```
!deploy[1]
```

Esc, Enter — выполнить.

```
!1
```

**Ожидание:** первая сохранённая команда (глобальный id) во вводе.

```
!deploy[999]
!notanumber
```

**Ожидание:** `not found` / `Invalid syntax`.

Автотест: `test_s07_bang_insert`.

---

## Секция 8: Сборка `!!`

`!! tag[tid]` читает БД сразу.  
`!! 1 2` (числовые id) берёт `last_query_results` — после старта все команды из БД уже там; новые в этой сессии появятся после `?` / `??` (или через ~5 с).

```
!! deploy[1] start[1]
!! deploy[1];start[1]
!! deploy[1]&&start[1]
```

**Ожидание:** во вводе `echo restart nginx echo Starting app` / с `;` / с `&&`.

Автотест: `test_s08_double_bang`.

---

## Секция 9: Автозагрузка при старте

Сохранить команды, **перезапустить** приложение, сразу:

```
!! 1 2
```

без предварительного `??`.

**Ожидание:** сборка из глобальных id работает.

Автотест: `test_s09_autoload_on_restart`.

---

## Секция 10: Пайпинг между блоками

```
printf 'alpha.py\nbeta.txt\ngamma.py\n'
```

PageUp на этот блок (или просто последний блок):

```
| grep py
```

**Ожидание:** в stdout есть `alpha.py` и `gamma.py`, нет `beta.txt`.

Автотест: `test_s10_pipe`.

---

## Секция 11: Навигация, история, F3 / Ctrl+C

```
echo first
echo second
```

Up / Esc / Up — `echo second`, затем `echo first`. Набранный префикс фильтрует историю (`echo` + Up).

PageUp / PageDown — прокрутка журнала, активен видимый блок (без прыжка к началу). Esc — обратно во ввод.

На блоке `echo first`: F3 или Ctrl+C.

**Ожидание:** в буфере `first` (полный raw_stdout, без заголовка). Ctrl+C во вводе копирует весь черновик, не только выделение.

Автотесты: `test_s11_nav_history_copy`, `test_history_up_filters_by_typed_text`, `test_ctrl_c_copies_whole_input_line`, `test_ctrl_c_on_block_copies_stdout`.

---

## Секция 12: Команды приложения

```
echo hist-line
:h
:h /hist
:h compact
:w test_output.txt
:?
:i
:md SEED_LINUX_COMMANDS.md
:c
```

**Ожидание:** `:h` показывает `hist-line` в одном блоке; `:h /hist` — уникальные совпадения в подсказках (свежие сверху); `:h compact` ужимает старые повторы, хвост `history_keep` не трогает; `test_output.txt` создан; `:?` — help (есть `:md`); `:i` — help ingress; `:md` — модалка Markdown (Esc / `q` закрывает, колесо не крутит журнал); `:c` — `All blocks cleared.`

`:q` — выход (в конце сессии). `:cd`, `:r`, `:theme` — секция 25.

Автотесты: `test_s12_colon_commands`, `test_colon_h_search_newest_first`, `test_colon_h_compact_uniques_old_keeps_tail`, `test_colon_md_opens_formatted_handbook`, `test_md_viewer_wheel_does_not_scroll_journal`.

---

## Секция 13: Удаление

```
#cleanup echo temp1
#cleanup echo temp2
#cleanup-1
?cleanup
#cleanup-
?cleanup
```

**Ожидание:** soft-delete: `cleanup[1]` пропал; после `#cleanup-` тег пустой / `(None found)`. `#cleanup!` возвращает тег.

Автотест: `test_s13_delete`. Restore: `test_restore_soft_deleted_command`.

### 13.1. Спрятать справочник (`#name--` / `#name!!`)

После `python3 src/seed_helm.py --seed` (или клик по `--seed` из каталога):

```
#helm--
??
#helm!!
??
```

**Ожидание:** `#helm--` прячет все теги handbook (`helm`, `hls`, `hvars`, …), не один тег. В `??` блок Hidden с `#helm!!`. В `!`-подсказках helm нет. `#helm!!` возвращает. `#helm-` по-прежнему один тег. Неизвестное имя — ошибка, не hide.

Автотесты: `test_hide_and_restore_handbook_group`, `test_handbook_hide_unknown_and_single_tag_untouched`.

---

## Секция 14: Алиасы

Алиасы грузятся из `~/.bashrc` при старте. Для проверки без правки home:

в тесте алиас задаётся в `app.aliases`. Вручную можно добавить `alias mytest="echo Hello from alias"` в `~/.bashrc` и перезапустить.

```
mytest
```

**Ожидание:** `Hello from alias`.

Автотест: `test_s14_aliases`.

Алиас с `$1` подставляет аргумент, а не дописывает его после литерала `$1`:

```
# alias klogin="echo tsh kube login $1"
klogin my-cluster
```

**Ожидание:** stdout `tsh kube login my-cluster`, в выводе нет `$1`.

Автотест: `test_s14_alias_positional_dollar1`.

---

## Секция 14b: Настоящий TTY (`> cmd`)

```
>
> ssh $HOST
```

**Ожидание:** пустой `>` — Usage. `> cmd` снимает TUI и запускает команду с настоящим TTY (stdout не пишется в журнал). После выхода — InfoBlock `TTY: … / Exit code: N`; если тот же bash сделал `export`/`cd` — строки `env:` / `cwd:`. `>>` остаётся редиректом оболочки. Вложенный `> bash` + export внутри него не виден; тогда писать `.bashrc_term*` и `:env`.

Автотесты: `test_tty_prefix_empty_shows_usage`, `test_tty_prefix_runs_substituted_command` (мок `_run_in_tty`), `test_wrap_tty_command_dumps_exports`.

---

## Секция 14d: Перечитать env (`:env`)

```
:env extra
:env
```

**Ожидание:** лишний аргумент — `Usage: :env`. Без аргументов перечитывает `.bashrc_term*` и алиасы `~/.bashrc`; в журнале `Reloaded .bashrc_term_…: N vars`. После `> cmd` файлы и `export` той же оболочки подхватываются сами.

Автотест: `test_colon_env_reloads_bashrc`.

---

## Секция 14c: Клик и клавиатурный скролл журнала

Два блока (`echo click-first`, `echo click-second`). Клик по первому, затем по второму — фокус без прыжка к началу блока.

`seq` с длинным выводом: из ввода PageUp входит в просмотр последнего блока, повторный PageUp не прыгает к строке 1. Стрелки / PageUp на сфокусированном блоке активируют **видимый** блок.

Нужен `terminal_mouse: true` (по умолчанию).

Автотесты: `test_click_selects_block_without_leaving_input_only`, `test_pageup_does_not_jump_to_block_start`, `test_keyboard_scroll_activates_visible_block`.

---

## Секция 15: Ошибки, таймаут, обрезка вывода

```
/bin/false
ls /no-such-idivjopy-dir
sleep 15
@sleep 15
seq 1 400
```

**Ожидание:**

- несуществующая команда: stderr + exit code ≠ 0
- `sleep 15`: таймаут (`command_timeout` в `settings.yml`, по умолчанию 10 с), полный вывод не теряется
- `@sleep 15`: префикс `@` выполняет без таймаута (ждём завершения; в истории строка остаётся с `@`)
- `seq 1 400`: в UI последние ~300 строк + `truncated for UI stability`; F3 копирует полный вывод

Автотест: `test_s15_errors_timeout_truncate`.

---

## Секция 16: Интеграционный цикл

```
$PROJECT=myapp
#dev echo run-$PROJECT
#dev echo pytest
#dev=Development workflow
#dev=1=Run app
!dev[1]
!! dev[1];dev[2]
```

**Ожидание:** переменная в сохранённой команде; `!` вставляет; `!!` собирает цепочку с `;`.

Автотест: `test_s16_dev_cycle`.

---

## Секция 17: Edge cases

```
#
!abc[xyz]
!9999
#special=chars @#$
#special echo ok
#special=1=Test @#$%
```

**Ожидание:** Invalid syntax / not found; комментарии с спецсимволами сохраняются.

Автотест: `test_s17_edge_cases`.

---

## Секция 18: Несколько команд / `??`

```
#perf echo test 1
#perf echo test 2
... (8+ команд)
??
```

**Ожидание:** все видны, UI не падает.

Автотест: `test_s18_many_commands`.

---

## Секция 19: JSON Viewer

```
echo '{"spec":{"path":"/health","name":"demo"}}'
F3
```

или `:json file.json`.

- дерево раскрыто
- `/` затем `health` — фильтр
- Down, Enter — jq path в блоке, `$JSON` задан, viewer закрыт
- `echo $JSON` подставляет путь
- Right на узле не крашит
- Esc / `q` закрывает без `ScreenStackError`

Автотест: `tests/test_json_viewer.py`.

---

## Секция 20: Подсказки по файлам и вставка

```
ls ./
cat ./al<Tab>
```

**Ожидание:** список файлов (включая скрытые), каталоги с `/`; Tab заменяет только путь, не всю команду; после каталога список следующего уровня; `... and N more` + Down прокручивает.

`Shift+Insert` вставляет буфер в input (не букву `i`).

Автотест: `tests/test_completion.py`, `test_shift_insert_pastes_into_input`.

---

## Секция 21: Ingress help (`:i`)

```
:?
:i
:i list -n
```

**Ожидание:** help; `:i list -n` без значения — ошибка `Missing namespace after -n` (не молчаливый fallback).

Полный `:i list -n kube-system` — только если есть кластер.

Автотест: `test_s21_ingress_help`.

---

## Секция 22: Пустая БД, клик `--seed`, Markdown

Первый старт без живых команд (чистый cwd / пустой `mytags.db`; `:c` только чистит журнал, каталог от этого не появляется):

1. Журнал на **верхней** строке каталога, не прокручен вниз.
2. Есть ядро (`seed_linux_commands.py`, `seed_k8s_chains.py`, `seed_git.py`), `python3 src/seed_ops.py --seed`, ops по отдельности, имена `.md`.
3. Клик по зелёной `--seed` (например `python3 src/seed_ops.py --seed`) вставляет команду во ввод, **не** запускает. Enter — выполнить; затем `??` (или ~5 с).
4. Клик по `SEED_LINUX_COMMANDS.md` открывает formatted viewer. Esc / `q` закрывает. Колесо крутит только модалку.
5. Без мыши: `:md SEED_LINUX_COMMANDS.md`. Несуществующий файл — предупреждение, не краш. `../etc/passwd` не открывается.
6. Если в БД уже есть живые команды — каталог seed **не** показывается.

Автотесты: `test_welcome_journal_starts_at_top`, `test_starts_without_existing_database`, `test_insert_seed_command_puts_draft_in_input`, `test_colon_md_opens_formatted_handbook`, `test_md_viewer_wheel_does_not_scroll_journal`, `test_seed_hint_skipped_when_database_has_commands`, `test_handbook_md_path_resolves_repo_docs`.

---

## Секция 23: `$OUT`

```
echo Hello
echo Hello, $OUT
$OUT
$OUT=nope
```

**Ожидание:** второй echo печатает `Hello, Hello` (последняя непустая строка сфокусированного / последнего блока). Считается только если в команде есть `$OUT` / `${OUT}`. Не пишется в `.bashrc_term`. `$OUT` без аргументов — peek. `$OUT=` — отказ.

Автотест: `test_out_placeholder_is_lazy_last_line`.

---

## Секция 24: `# comment` и файлы истории

```
# curl https://example.com
#logs echo still-a-tag
```

**Ожидание:** `# ` + пробел — строка в журнале и в `history_default.txt`, **без** запуска и без тега. `#logs echo …` — обычный save. Up поднимает parked-строку.

`python3 app.py --instance-name=user1` пишет `history_user1.txt` и `.bashrc_term_user1`. Старый `history.txt` копируется один раз, если instance-файла ещё нет. В уже запущенном TUI то же делает `:session user1`.

Автотесты: `test_hash_space_parks_in_history_without_running`, `test_default_instance_writes_history_default`, `test_instance_name_uses_separate_history_file`, `test_migrates_legacy_history_txt`.

---

## Секция 25: `:cd`, `:r`, `:theme`, `:export`

```
echo replay-me
:r
cd /tmp
:cd
:cd /no-such-idivjopy-dir
:theme
:theme textual-dark
```

**Ожидание:** `:r` кладёт команду сфокусированного (или последнего) блока во ввод. `cd` / `:cd` меняет cwd для shell-команд; нет каталога — ошибка, не молчание. База тегов / история / `.bashrc_term*` остаются в каталоге запуска (пустой `mytags.db` в новой папке не появляется). `:theme` показывает / ставит тему в `settings.yml`. `d` на журнале переключает dark/light.

```
#demo echo one
:export demo
```

**Ожидание:** JSON с тегом; `:import` создаёт новые tid (не затирает).

Автотесты: `test_replay_puts_command_in_input`, `test_cd_changes_app_cwd`, `test_colon_cd_and_missing_dir`, `test_colon_theme_sets_and_lists`, `test_toggle_dark_saves_theme`, `test_export_and_import_tag`.

---

## Секция 26: Плейбук из обычной сессии (`:playbook`)

```
echo hello-play
#demo echo tagged
:playbook -
:playbook tour.yml
:playbook clear
```

**Ожидание:** `:playbook -` показывает YAML в журнале (`echo hello-play` с `wait_command`, `#demo echo tagged` без). Файл `tour.yml` пишется в cwd. Replay: `python3 app.py --demo tour.yml`. Tab / F5 / клик / `> htop` в YAML не попадают. Пустой лог — подсказка, не файл. `:playbook` само в шаги не пишется.

Автотесты: `test_session_to_playbook_heuristics`, `test_playbook_writes_session_yaml`.

---

## Секция 27: Проверка обновлений (`:update`)

```
:update
```

**Ожидание:** сверка с GitHub `main` (`src/app.py` → `VERSION`). Если на GitHub новее — `Update available` и `git pull`. Если совпадает — `Up to date`. Старт с `check_updates: true` пишет в журнал только при наличии обновления. Без сети `:update` показывает ошибку, не падает. Прокси 407 без `$PROXY_USER` — подсказка задать `$PROXY_USER` / `$PROXY_PASS`.

Автотест: `test_colon_update_reports_newer_remote`, `tests/test_update_check.py`.

---

## Секция 28: Плейбук `loop` (мониторинг)

В YAML после `:playbook` (или в своём файле):

```yaml
loop: 3
steps:
  - type: echo loop-mark
    wait_command: true
    pause: 0
```

Или шаг:

```yaml
- loop: true
  type: curl -sS http://127.0.0.1:8080/health
  wait_command: true
  pause: 5
```

**Ожидание:** `loop: N` повторяет шаги N раз и заканчивается. `loop: true` / `0` / `forever` крутит до **Esc** (сессия остаётся). `--demo-quit` не выходит из бесконечного цикла. Подпись в subtitle: `DEMO · … 2/∞ · Esc stops`.

Автотесты: `test_normalize_loop_shorthand_and_nested_steps`, `test_demo_loop_repeats_command`, `test_demo_top_level_loop_stops_on_escape`.

---

## Секция 29: Сессии на лету (`:session`)

```
:session
$ALPHA=from-default
:session ops
:session
:session default
:session ../oops
```

**Ожидание:** `:session` показывает текущий инстанс и список. `:session ops` создаёт `.bashrc_term_ops` / пишет в `history_ops.txt`; `$ALPHA` из default не течёт в ops. Журнал не очищается, БД тегов общая. Плейбук-лог сбрасывается. Неверное имя — `Usage:`. Демо (`--demo`) — нельзя переключить, пока тур идёт.

Автотест: `test_colon_session_creates_and_switches`.

---

## Секция 31: Каталог seed (`:welcome`)

```
:welcome
```

**Ожидание:** `:welcome` показывает каталог seed (`Empty command database`, `--seed`, `.md`) даже если БД уже не пустая. На старте с живыми тегами — блок **Разделы** (`linux` / `k8s` / `свои`, …), без каталога empty-DB.

Автотест: `test_colon_welcome_shows_seed_catalog`, `test_startup_shows_sections_when_db_has_tags`.

---

## Секция 32: Снимок БД (`:backup`)

```
:backup
#keep echo still-here
:backup
```

**Ожидание:** на пустой БД — `Empty database, nothing to backup`, каталога `backups/` нет. После `#keep` — `Backup: …/test_history-manual-….db`, файл открывается SQLite и содержит `keep`. Лишние аргументы — `Usage: :backup`.

Автотест: `test_colon_backup_empty_db`, `test_colon_backup_writes_sqlite_copy`.

---

## Секция 33: Проводник и терминал (`:fm`, `:term`)

```
:fm extra arg
:fm
:fm inner
$FILEMAN=nautilus
:fm
:term extra arg
:term
```

**Ожидание:** лишние аргументы — `Usage: :fm [path]` / `Usage: :term [path]`. Без пути открывает проводник / системный терминал в cwd приложения (новое окно, TUI не ждёт). Путь — тот каталог. Нет бинарника — `not found` и `set $FILEMAN=` / `set $TERMINAL=`. `$FILEMAN` / `$TERMINAL` перекрывают дефолт ОС (Linux `xdg-open`, macOS `open`, Windows `explorer` / `wt`). В YAML-плейбук `:fm` / `:term` не пишутся.

Автотест: `tests/test_gui_open.py`, `test_colon_fm_spawns_detached`, `test_colon_fm_path_usage_and_override`, `test_colon_fm_missing_binary`, `test_colon_term_override_and_missing`, `test_colon_term_no_default_binary`, `test_session_to_playbook_heuristics`.

---

## Секция 30: Screensaver (`:screensaver`)

```
:screensaver
x
:screensaver 0
```

**Ожидание:** `:screensaver` открывает полноэкранный starfield. Среди звёзд летают живые часы (`HH:MM:SS`) и дата (`YYYY-MM-DD`). Сверху на всю ширину — зелёная лента `!tag[tid]  cmd` если в БД есть команды. Снизу слева справка команд (печать слева направо, отступ от края); снизу справа `load` 1/5/15 и `mem` (опрос раз в секунду из `/proc`), с таким же отступом от правого угла; в узком окне load может перекрыть справку. `x` закрывает его и **не** попадает во ввод. После `screensaver_idle` секунд без клавиш/клика то же самое само (в тестах `screensaver_idle: 0` — выкл). `:screensaver 0` выключает на сессию. Во время `--demo` idle-скринсейвер не стартует. `screensaver_stars: false` в `settings.yml` убирает летающую пыль/токены; часы, лента и load остаются.

Автотест: `tests/test_screensaver.py`.

### Остановка фоновой команды (F4 / :kill)

**Предусловия:** приложение запущено с `command_timeout` > 0.

1. `@ sleep 60` — долгая команда без timeout; блок показывает `[Executing...]`.
2. `F4` (фокус во вводе → стоп последней запущенной) — блок быстро завершается.
   **Ожидание:** в блоке STDERR: `Process stopped by user.`, `Exit code: 143` (128+SIGTERM).
3. `@ sleep 60`, затем сфокусировать этот блок (Tab) и нажать `F4` — стоп именно его.
4. `@ sleep 60` ×2, затем `:kill all` — оба блока останавливаются.
5. `:kill` без запущенных — **Ожидание:** `No running commands to stop.`
6. Запустить `@ sleep 30` и выйти `:q` — приложение закрывается и останавливает процесс.

Автотест: `tests/test_stop_command.py`.

### Поиск по содержимому команд (`?text`)

**Предусловия:** в БД есть команды с общим фрагментом, напр. `kubectl get pods -o wide` (тег kube).

1. `#kube kubectl get pods -o wide`, `#kube kubectl get svc -o wide`.
2. `?wide` — **Ожидание:** заголовок `Search 'wide' in commands (2)`, обе строки `<id> kube[tid]  …`.
3. `?pods` — одна строка. `?zzz` — `no matches` (не ошибка). `?z` — `Tag 'z' not found`.
4. `!<id>` после поиска — команда вставляется во ввод, Enter выполняет.
5. `?kube` — по-прежнему список тега (не поиск).

Автотест: `tests/test_search_content.py`.

### Периодический перезапуск (`:watch <sec> <command>`)

1. `:watch 1 echo tick` — блок `watch: echo tick · every 1s`.
2. Через ~3 сек в блоке `watch #3` (номер тика растёт, текст заменяется, не копится).
3. `:watch stop` — подпись `— watch stopped after N tick(s) —`, блок не `[Executing...]`.
4. `:watch 1 echo x` и сразу `:watch 1 echo y` — **Ожидание:** `A watch is already running…`.
5. `:c` во время watch — останавливает цикл; повторный `:watch` снова работает.
6. `:watch 3 sleep 60`, затем `F4` (или `:kill`) — тик останавливается, блок получает подпись.
7. `:watch` (без аргументов), `:watch abc echo x`, `:watch 0 echo x` — явные Usage.

Автотест: `tests/test_watch.py`.

### Перенос и переименование тегов (`:mv`)

1. `#kube kubectl get pods`, `#mine echo stay`.
2. `:mv kube[1] mine` — **Ожидание:** `Moved <1> kube[1] → mine[2]`.
3. `?mine` — обе команды; `?kube` — теперь поиск `Search 'kube'` (тега нет), не список.
4. `:mv kube k8s` (переименование) — `Renamed tag 'kube' → 'k8s' (N command(s)).`; комментарий тега переехал.
5. Ошибки: `:mv`, `:mv kube[1] 9bad`, `:mv nope[1] mine`, `:mv kube kube`, `:mv ghost target` — явные сообщения.
6. `:mv kube[1] mine`, затем `:mv k8s mine` — целевой тег занят → `already exists`.

Автотест: `tests/test_tag_move.py`.

### Статистика использования (`:stats`)

1. `#kube echo hot`, `#kube echo cold`.
2. `echo hot` (Enter) ×2.
3. `:stats` — **Ожидание:** теги 1, live 2, never run 1; `Per tag`: `kube … 2 run(s)`; `Top commands`: `echo hot … (2×)`.
4. `!kube` (completion) — первой строка `echo hot` (чаще использовалась), затем `echo cold`.
5. `:stats` на пустой БД — `(empty database …)`.
6. Старая БД: запуск приложения не падает (миграция `use_count`/`last_used` на лету).

Автотест: `tests/test_usage_stats.py`.

### Экспорт библиотеки в Markdown (`:export *`)

1. `#kube kubectl get pods`, `#mine echo done`, комментарий тега/команды.
2. `:export * out.md` — **Ожидание:** `Exported 2 command(s) to out.md (Markdown catalog)`.
3. Файл: `# Command library`, `## kube — …`, строки `` `kubectl get pods` ``, комментарии строк `— …`.
4. `:export` без аргументов — Usage. Старый `:export mine out.json` — как раньше (JSON).

Автотест: `tests/test_md_export.py`.

### Сравнение выводов (`:diff`)

1. `printf 'a\nb\nc'`, затем `printf 'a\nB\nc'` — два блока.
2. `:diff` — **Ожидание:** `Diff:` + `@@`, строка `- b` (красная) и `+ B` (зелёная).
3. Дважды одна и та же команда + `:diff` — `outputs are identical`.
4. Одна команда + `:diff` — `need at least two command blocks`.
5. Сфокусировать (Tab) второй блок из трёх + `:diff` — сравнение именно его с предыдущим.

Автотест: `tests/test_diff.py`.

### Сессионная история вывода (`:o`)

1. `echo alpha`, `echo beta`, `echo gamma`.
2. `:o` — последние выводы (заголовки `$ echo …` и строки). `:o 1` — только gamma.
3. `echo secret-token-42`, затем `:c`, затем `:o /secret-token` — **Ожидание:** совпадение найдено даже после очистки журнала.
4. `:o /zzz` — `no matches in output history`. `:o clear` → `Cleared…`, затем `:o` → `No command output stored`.
5. `echo err >&2; exit 3`, `:o 1` — `exit 3` и строка stderr.

Автотест: `tests/test_output_history.py`.

### Автодополнение ресурсов k8s (`k8s_completion`)

1. В `settings.yml` поставить `k8s_completion: true`, кластер доступен (`kubectl`).
2. Набрать `kubectl get pod <Tab>` — **Ожидание:** список имён подов из кластера.
3. `kubectl get svc -n prod web<Tab>` — имена сервисов в namespace `prod` с префиксом `web`.
4. Выключить kubectl/кластер — `kubectl get pod <Tab>` не падает (пустой список, обычное дополнение не смешивается с файлами).
5. Без флага (`k8s_completion: false`) — `kubectl get pod` не дёргает kubectl вовсе.

Автотест: `tests/test_k8s_completion.py` (kubectl замокан).

### UX-мелочи (`:r N`, running, `:alias`)

1. `echo a`, `echo b`, `echo c`; `:r 1` — во вводе `echo b`; `:r 0` — `echo c`; `:r 5` — `too far back`.
2. `@ sleep 30` — заголовок `IDvjPy_term — 1 running`; `:kill` — счётчик исчезает.
3. `#mine echo hello`, `:alias mine out.sh` — файл содержит `mine_1() {` и `echo hello`; `:alias * lib.sh` — все теги.
4. `:alias` — Usage; `:alias ghost` — `no live commands for 'ghost'`.

Автотест: `tests/test_ux_extras.py`.

### LLM через API (`:llm`)

1. Скопировать `src/llm_providers.example.yml` в каталог запуска как `llm_providers.yml`.
2. Задать ключ окружением: `$DEEPSEEK_API_KEY=...` (или export до запуска).
3. `:llm` — **Ожидание:** список провайдеров (`ds (default)`, `openai`, `grok`, `ollama`, …).
4. `:llm Привет, как дела?` — **Ожидание:** запрос провайдеру по умолчанию (`default: ds`).
5. `:llm ds Привет, как дела?` — то же, но явно указан провайдер.
6. Без ключа: `:llm ds hi` — `Missing env variable(s): DEEPSEEK_API_KEY`.
7. Ошибки: `:llm ds` (Usage), `:llm nope hi` без `default:` (`unknown provider` + подсказка), удалённый конфиг — `Config not found` + подсказка про example.
8. Провайдер с ручным `body` (например, `ollama` без ключа) — шаблон с `%MSG%` / `%MODEL%`.
9. `:llm d` → Tab — **Ожидание:** список из конфига, подстановка только имени (`:llm ds `); начатое сообщение список гасит.
10. Прокси 407 (`Tunnel connection failed: 407`): задать `$PROXY_USER=…` / `$PROXY_PASS=…` — `:llm` подхватит их, как `:update`; без них — явная подсказка в сообщении об ошибке.
11. Вывод блока: выполнить `printf 'l1\nl2\n'`, затем `:llm ds $OUT` — уйдёт строка `l2`; `:llm ds $BLOCK` — весь вывод `l1`…`l2`. Без завершённого блока — явная ошибка.
12. Вложение файла: создать `note.txt`, затем `:llm ds объясни @note.txt` — в шапке блока `@files: note.txt (N)`, в запрос уйдёт содержимое (```-блок). Несколько: `@a.py @b.log`. Ошибки явные: нет файла (`Cannot read`), каталог (`directory`), бинарник (`binary`), больше лимита (`too large`; лимит — `max_attachment_bytes`). Литеральный `@` — `@@`; `user@host` не трогается.
13. В `history_*.txt` и в `:r` — исходная строка с `@файлом`, без содержимого файла. Подсказки: набрать `:llm ds … @no` — список файлов каталога (каталоги с `/`).
14. Контекст беседы: в конфиге `ds` задать `history_turns: 2` — задать два вопроса подряд (`:llm первый`, `:llm второй`): в шапке второго блока `ctx: 1/2 turns`, в запрос уходит первая пара. Третий вопрос — уже 2 пары; четвёртый вытесняет первую. `:llm reset` — сброс ветки default (InfoBlock `LLM context reset: ds (N turns)`); `:llm reset ds`, `:llm reset *` — по имени/все. Без `history_turns` — поведения нет (как раньше).
15. Язык ответа: в конфиге у `ds` задан `answer_language: Russian` — ответы DeepSeek на русском, без ухода в китайский (несколько вопросов подряд, короткие).

Автотест: `tests/test_llm.py` (urllib замокан, сеть не дёргается).

### Опечатки не пишутся в историю

1. Ввести `Жр` (Enter) — блок с `command not found`, `Exit code: 127`.
2. `:h` / открыть `history_default.txt` — строки `Жр` нет; в ↑ её тоже нет.
3. `bash -c 'exit 127'` (127 без not-found) — **Ожидание:** строка в истории остаётся.
4. Обычные команды (`echo ok`) пишутся как раньше.

Автотест: `tests/test_history_typo.py`.

---

## Калькулятор / ipcalc (v1.53)

Локальные вычисления **без спец-команд**: строка, начинающаяся с цифры (или `(` / `-`) и целиком разбираемая как арифметика/единицы/IPv4, выполняется локально, результат — блок с заголовком `calc:`. Остальное (`7z …`, `(cd …)`, `-la`, `2>/dev/null …`) уходит в shell как раньше.

1. **Арифметика:** `1024*3` → `= 3072`; `(512+512)*2` → `= 2048`; `2^10` → `= 1024`; `-5 + 8` → `= 3`.
2. **Проценты:** `512Mi + 20% in Gi` → `= 0.6Gi` (увеличить память на 20%); `512Mi - 15%` → 435.2Mi; `512Mi * 20% in Mi` → `= 102.4Mi` (доля); `2 + 10%` → `= 2.2`.
3. **Доли (`of`):** `20% of 512Mi in Mi` → `= 102.4Mi`; `1/3 of 1Gi in Mi` → `= 341.333333Mi`; `20% of (512Mi + 1Gi) in Mi` → `= 307.2Mi`.
4. **Перевод единиц:** `512Mi in B` → `= 536870912B`; `1Mi in B` → `= 1048576B`, `1M in B` → `= 1000000B`; `1Gi in MB` → `= 1073.741824MB`; голый `512Mi` — авто-эквиваленты `= 512Mi (= 536870912B)`.
5. **CPU:** `500m in cores` → `= 0.5 cores`; `0.5 in m` → `= 500m`; `500m + 20% in m` → `= 600m`.
6. **k8s-ресурсы:** `512Mi + 1Gi + 256Mi in Mi` → `= 1792Mi`; `512Mi*30 in Gi` → `= 15Gi`; `1Gi/512Mi` → `= 2`; `524288 in Mi` → `= 0.5Mi`.
7. **ipcalc:** `192.168.1.0/24` — Network `192.168.1.0/24`, Broadcast `192.168.1.255`, `Hosts/Net: 254`, `Class C · RFC1918 private`, бинарная колонка; `10.1.2.3/255.255.255.0` — `Netmask: 255.255.255.0 = 24`; `10.0.0.1/32` — host route; `172.16.0.1` (без маски) — класс B → /16.
8. **Префикс под N хостов:** `300 hosts` → `300 hosts → /23` (510 usable); `2 hosts` → `/31` (RFC 3021 point-to-point); `1 host` → `/32`; `7 hosts` → `/28`; `4,000 hosts` → `/20`.
9. **Ошибки — явные, не молчаливый shell:** `512Mi + 2` → `calc: incompatible units…`; `10.1.2.3/33` → `calc: prefix out of range…`; `0 hosts` → `calc: hosts count must be >= 1`.
10. **Не-расчёты остаются shell:** `7z` → `command not found` (127); `(echo ok)` — подстановка выполняется; `2>/dev/null echo ok` → stdout `ok`.
11. **Справка:** `:? calc` — справочник калькулятора и ipcalc (упоминание в `:?`).

Автотесты: `tests/test_calc.py`, `tests/test_ipcalc.py`.

### Data-каталог (`--data-dir` / `$IDVJPY_DATA_DIR`)

1. `python3 app.py --data-dir /tmp/idvj-dir` — settings/БД/history создаются в `/tmp/idvj-dir`.
2. Без флага, из каталога с `settings.yml` — данные остаются в нём (portable).
3. Без флага из пустого каталога (и без env) — системный каталог ОС (см. `src/data_dirs.py`).
4. `IDVJPY_DATA_DIR=/tmp/idvj-env python3 app.py` — каталог из переменной.

Автотест: `tests/test_data_dirs.py`.

### pip-установка из wheel (v1.55)

1. Из репозитория: `packaging/build_wheel.sh` → `packaging/dist/idvjpy_term-*.whl`.
2. В чистом venv (`pip install --no-deps <wheel>` без зависимостей не запустится — нужны deps; обычный `pip install <wheel>` ставит их из PyPI).
3. `idvjpy --data-dir /tmp/idvj-pip` — первый запуск создаёт settings/БД/history + шаблоны `settings.yml`, `llm_providers.yml`, `.bashrc_term_default` в `/tmp/idvj-pip`; `:q` — выход.
4. `idvjpy --demo short --demo-quit` — автотур из установленного пакета, корректный выход.
5. `python3 -m idvjpy_boot --demo short --demo-quit` — тот же запуск через `python -m`.
6. Ресурсы (CSS/demos/примеры) берутся из пакета: демо и темы работают без каталога репозитория рядом.
7. Из корня репозитория: `uv tool install .` → `idvjpy --help`; зависимости ставятся автоматически (textual и др.). `uv tool uninstall idvjpy-term`.
8. Из GitHub без локальной сборки: `pipx install git+https://github.com/webxed/IDvjPy` / `uv tool install git+https://github.com/webxed/IDvjPy` — корневой `setup.py` вкладывает `src/` на этапе сборки.

Автотест: `tests/test_packaging_root.py` (корневой и packaging pyproject не разъезжаются, `setup.py --version`, MANIFEST).

Проверено вручную: wheel `idvjpy_term-1.56.0` поставлен в чистый каталог; headless-`run_test` с `data_dir` (provisioning из встроенных примеров) и реальный pty-прогон `--demo short --demo-quit` (exit 0).

### Кластерный журнал `:kctx` (v1.58)

Переменные kubectl-стека (`NS POD DEPLOY SVC ING APP CTR QUOTA`) запоминаются по кластерам в `kctx.json` (data-каталог).

1. Войти в кластер обычной строкой — `klogin prod` (alias → `tsh kube login`) или `kubectl config use-context prod` (когда tsh недоступен).
2. Задать `$NS=team-a`, `$POD=api-7f` → в журнале появились снимки кластера `prod` (см. `kctx.json` рядом с `settings.yml`).
3. `:kctx` — список кластеров: имя, число снимков, время последнего; у текущего — «← текущий».
4. `:kctx prod` — блок входа (`klogin prod || kubectl config use-context prod`) и список ранее использованных наборов переменных (`1. NS=… POD=… (дата)`).
5. `:kctx 1` — применить свежайший набор: переменные в `.bashrc_term_<instance>`, InfoBlock `kctx prod #1: NS=…`. Проверить: `cat .bashrc_term_default`, `echo $NS` в новой команде.
6. `:kctx staging 2` — вход в staging и применение его набора №2 одной строкой.
7. `:kctx 99` без открытого списка — подсказка «нет открытого списка»; после `:kctx <cluster>` с одним снимком — «набора 99 нет».
8. Ввод `:kctx ` + первые буквы кластера — подсказки имён из журнала (Tab/Enter).
9. Не-стековые переменные (`$EDITOR=…`) в журнал кластеров не пишутся.

Автотесты: `tests/test_kctx_cmd.py`, `tests/test_kctx_store.py`.

### Удаление по словам во вводе (v1.59)

1. Вставить/набрать длинную строку (например, поля вывода `kubectl get ... -o wide`).
2. `Ctrl+W` — удалить слово слева от курсора (работает во всех терминалах). `Ctrl+Backspace` — то же, где терминал шлёт его отдельной клавишей (если нет — он ведёт себя как обычный Backspace).
3. `Ctrl+F` / `Ctrl+Delete` — удалить слово справа от курсора.
4. `Ctrl+←` / `Ctrl+→` — курсор по словам (не посимвольно).
5. `Ctrl+Z` — отменить последнее изменение (печать/удаление/вставку); повторные — шаг за шагом. После Enter/`Ctrl+D` история правок сбрасывается.
6. Удержание Backspace — как раньше, посимвольно (авто-repeat терминала).

Автотест: `tests/test_input_words.py`.

### Выделение мышью → буфер (v1.62)

1. Выполнить команду с выводом (`echo hello`), при `terminal_mouse: true` протянуть мышью по журналу — текст выделяется, при отпускании сразу в буфере; в подзаголовке `Copied selection (N chars)`.
2. Вставить в другое окно/поле (Ctrl+V) — вставляется именно выделенное.
3. `Ctrl+C` при активном выделении — копирует выделение (иначе — строка ввода/блок).
4. Простой клик без протяжки — выделение снимается, буфер не меняется.
5. `Shift`+протяжка — нативное выделение терминала (альтернатива).
6. Проверить оба режима `terminal_mouse`: true — выделяет приложение (с автокопированием); false — выделяет терминал сам, колесо в приложение не идёт (PgUp/PgDn).

Автотест: `tests/test_mouse_selection.py` (эмуляция протяжки через MouseDown/Move/Up).

### LLM знает библиотеку тегов — `:llm ask` (v1.67)

1. Заполнить библиотеку: выполнить `#kpod kubectl get pods -n $NS`, `#klog kubectl logs $POD -n $NS --tail=200`.
2. В `llm_providers.yml` задать `default: ds`. Набрать `:llm ask найди все поды XXX и покажи их логи` → в шапке блока `app-ctx: N tags`; в запрос уходит задача + шпаргалка префиксов + выжимка тегов (проверить на локальном `echo-demo`/ollama, подменив URL на свой). Выбор модели: `:llm ask <провайдер> <задача>` — слово сразу после `ask`, совпавшее с именем из `providers`, берётся как провайдер; иначе — `default:`.
3. Ответ содержит `!kpod[1]` / `!! kpod[1] && klog[1]`. Под блоком — строка кликабельных ссылок; при `terminal_mouse: true` клик вставляет `!kpod[1] ` во ввод (без запуска), Enter — запуск.
4. Выдуманные ссылки (`!ghost[9]`) в строку ссылок не попадают.
5. `:llm ask` (без задачи) → `Usage: :llm ask [<provider>] <task in your words>`; без `default:` и без имени провайдера → `needs a provider`.
6. Обычный `:llm ds вопрос` без ключа `app_context` в шапке `app-ctx` не показывает (поведение прежнее); с `app_context: true` — показывает и шлёт тот же контекст.
7. `:llm ` (Tab) предлагает провайдеров и `ask`; `:llm as` → `ask`; `:llm ask ` → провайдеры; `:llm ask <Tab>` без default выбирает провайдера для ask; `:r` на блоке `:llm ask` возвращает `:llm ask [<провайдер>] <задача>`.
8. Встроенный офлайн-провайдер `offline` (`mock: true`) есть в любом конфиге и отвечает без сети/ключа: `:llm offline Привет`, `:llm ask offline найди поды` (в шапке `app-ctx: N tags`). Используется в акте E тура `--demo all`.

Автотест: `tests/test_llm.py` (юнит `llm_context` + app-level `:llm ask` / `app_context`).

### Внешний редактор — `:ed` (v1.70)

1. В `settings.yml` задать `editor: nano` (или `vim`). Набрать `:ed notes.txt` → TUI на паузе, открывается nano; сохранить и выйти → `Editor: saved <путь>`. Файла нет — nano создаёт его (`Editor: created`), выход без записи — `was not created`.
2. Ничего не менять → `Editor: <путь> unchanged`.
3. Выполнить `docker ps` (или любое), затем `:ed $OUT` → в редакторе последняя непустая строка вывода; правка в одну строку `:wq` → строка оказалась во вводе (рядом `Editor: $OUT → input`), Enter — запуск. Несколько строк — файл остаётся по напечатанному пути (`kept at …`).
4. `:ed $BLOCK` → весь stdout блока (несколько строк → файл остаётся, путь виден; при сведении к одной строке — уходит во ввод).
5. `:ed` без аргумента — пустой буфер: набрать команду, сохранить → она во вводе.
6. Ошибки: `:ed <каталог>` → `is a directory`; `:ed $BLOCK` без завершённого блока → `need a finished command block`; `editor: есть-нет` → `'…' not found (editor: in settings.yml…)`; `:ed` без `editor:` и без `$EDITOR`/`$VISUAL` → откат на системный редактор.
7. `:ed a b` → `Usage: :ed [<file>|$OUT|$BLOCK]`.
8. GUI-редактор (`editor: code --wait`) — флаг ожидания обязателен, иначе приложение продолжит работу сразу.
9. Подстановка в пути: `$NS=prod`, затем `:ed /tmp/$NS-notes.txt` → открывается `/tmp/prod-notes.txt`; `$TMPDIR/pod-$OUT.json` — ленивый `$OUT` берёт последнюю строку блока (без блока — `$OUT is empty`); `:ed /tmp/$NOPE.yaml` → `undefined variable(s): $NOPE` (файл «$NOPE.yaml» не создаётся).

Автотест: `tests/test_editor.py` (запуск редактора подменяется — TTY не нужен).

---

## Критерии успеха

- Команды сохраняются с корректным `tid`; `-`/`=`/`+` внутри текста не ломают парсер
- Комментарии тегов и команд видны в `?` / `??` / `?tag`
- Ссылки **не** раскрываются при `#save`, раскрываются в `?tag[tid]` и при выполнении
- `!tag[tid]` и `!ID` вставляют во ввод
- `!! tag[tid]` работает сразу; `!! 1 2` — из кэша (старт или `??`)
- `| cmd` берёт stdout сфокусированного/последнего блока
- `$VAR` подставляется; `$JSON` после Enter в viewer; `$OUT` — последняя строка блока по запросу; `:env` перечитывает `.bashrc_term*`
- `:q` `:w` `:h` `:c` `:?` `:md` `:cd` `:fm` `:term` `:env` `:session` `:welcome` `:backup` `:screensaver` `:r` `:theme` `:playbook` `:update` работают
- `:llm ask <задача>` шлёт контекст приложения и предлагает только существующие `!tag[tid]` (ключ `app_context` — то же для обычного `:llm`)
- `:ed <файл>|$OUT|$BLOCK` открывает редактор из `settings.yml`; однострочная правка `$OUT` попадает во ввод, многострочная — остаётся файлом
- `:o /text` и `:h /text` — поиск, а не листинг `/`: файловых подсказок нет (`:cd /…` и другие пути дополняются как раньше)
- YAML `--demo` / `:playbook`: `loop: true` / `loop: N` крутит шаги, Esc останавливает
- Soft-delete `#tag-` / `#tag-tid`; handbook hide `#name--` / `#name!!`; `# command` паркуется без запуска
- Пустая БД: каталог сверху; клик `--seed` → ввод; `.md` / `:md` — Markdown-viewer (колесо не крутит журнал)
- Большой вывод не вешает UI (обрезка + полный `raw_stdout`)
- JSON viewer и path-completion без крашей

---

## Проверка БД после ручного прогона

```bash
sqlite3 mytags.db "SELECT tag, tid, command, comment FROM commands WHERE deleted = 0 ORDER BY tag, tid;"
sqlite3 mytags.db "SELECT tag, comment FROM tags ORDER BY tag;"
cat .bashrc_term_default
cat history_default.txt
```

---

**Версия документа**: v1.30  
**Версия приложения**: v1.83
**Автотесты**: `tests/test_cmd_scenarios.py`, `tests/test_commands.py`, `tests/test_completion.py`, `tests/test_tags.py`, `tests/test_seed_catalog.py`, `tests/test_json_viewer.py`, `tests/test_demo.py`, `tests/test_screensaver.py`, `tests/test_calc.py`, `tests/test_ipcalc.py`  
**Дата**: 2026-09-11
