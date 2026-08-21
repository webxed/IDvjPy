# План тестирования IDvjPy_term v1.24

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
| клик по блоку | Фокус на блоке. В пустой БД: `--seed` → во ввод; `.md` → справочник |
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

**Ожидание:** список тегов; все команды с `<gid>` и `tag[tid]`; пустой тег — `(None found)`. После `#name--` в `??` / `?` блок Hidden (`#tag!` / `#group!!`); спрятанные теги не в `!`-подсказках.

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
:w test_output.txt
:?
:i
:md SEED_LINUX_COMMANDS.md
:c
```

**Ожидание:** `:h` показывает `hist-line` в одном блоке; `:h /hist` — уникальные совпадения в подсказках (свежие сверху); `test_output.txt` создан; `:?` — help (есть `:md`); `:i` — help ingress; `:md` — модалка Markdown (Esc / `q` закрывает, колесо не крутит журнал); `:c` — `All blocks cleared.`

`:q` — выход (в конце сессии). `:cd`, `:r`, `:theme` — секция 25.

Автотесты: `test_s12_colon_commands`, `test_colon_h_search_newest_first`, `test_colon_md_opens_formatted_handbook`, `test_md_viewer_wheel_does_not_scroll_journal`.

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

**Ожидание:** пустой `>` — Usage. `> cmd` снимает TUI и запускает команду с настоящим TTY (stdout не пишется в журнал). После выхода — InfoBlock `TTY: … / Exit code: N`. `>>` остаётся редиректом оболочки.

Автотесты: `test_tty_prefix_empty_shows_usage`, `test_tty_prefix_runs_substituted_command` (мок `_run_in_tty`).

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
seq 1 400
```

**Ожидание:**

- несуществующая команда: stderr + exit code ≠ 0
- `sleep 15`: таймаут (`command_timeout` в `settings.yml`, по умолчанию 10 с), полный вывод не теряется
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

`python3 app.py --instance-name=user1` пишет `history_user1.txt` и `.bashrc_term_user1`. Старый `history.txt` копируется один раз, если instance-файла ещё нет.

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

**Ожидание:** `:r` кладёт команду сфокусированного (или последнего) блока во ввод. `cd` / `:cd` меняет cwd приложения; нет каталога — ошибка, не молчание. `:theme` показывает / ставит тему в `settings.yml`. `d` на журнале переключает dark/light.

```
#demo echo one
:export demo
```

**Ожидание:** JSON с тегом; `:import` создаёт новые tid (не затирает).

Автотесты: `test_replay_puts_command_in_input`, `test_cd_changes_app_cwd`, `test_colon_cd_and_missing_dir`, `test_colon_theme_sets_and_lists`, `test_toggle_dark_saves_theme`, `test_export_and_import_tag`.

---

## Критерии успеха

- Команды сохраняются с корректным `tid`; `-`/`=`/`+` внутри текста не ломают парсер
- Комментарии тегов и команд видны в `?` / `??` / `?tag`
- Ссылки **не** раскрываются при `#save`, раскрываются в `?tag[tid]` и при выполнении
- `!tag[tid]` и `!ID` вставляют во ввод
- `!! tag[tid]` работает сразу; `!! 1 2` — из кэша (старт или `??`)
- `| cmd` берёт stdout сфокусированного/последнего блока
- `$VAR` подставляется; `$JSON` после Enter в viewer; `$OUT` — последняя строка блока по запросу
- `:q` `:w` `:h` `:c` `:?` `:md` `:cd` `:r` `:theme` работают
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

**Версия документа**: v1.6  
**Версия приложения**: v1.24  
**Автотесты**: `tests/test_cmd_scenarios.py`, `tests/test_commands.py`, `tests/test_completion.py`, `tests/test_tags.py`, `tests/test_seed_catalog.py`, `tests/test_json_viewer.py`  
**Дата**: 2026-08-21
