# План тестирования IDvjPy_term v1.152

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
| `Ctrl+клик` / двойной клик по `!tag[tid]` | Вставить ссылку и сразу выполнить (как два Enter); без tid/прочие ссылки — только вставка |
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

### 1b. Секретные переменные `$$VAR=value`

```
$$TOKEN=supersecret
$$TOKEN
echo prefix-$TOKEN suffix
$$TOKEN-
$$TOKEN
```

**Ожидание:**
- При наборе/вставке значения поле ввода маскируется (точки), в подзаголовке `Secret $TOKEN: value hidden`.
- После Enter: `Secret $TOKEN set (value hidden, secrets_default.json)` — значение в журнале не видно; `echo prefix-$TOKEN` даёт блок с `prefix-****` (raw_stdout при этом настоящий — `F3`/`|`/`$OUT` работают).
- **Хранение (только сессия).** Запись идёт в `secrets_default.json` (права `0600`), нет в `.bashrc_term_default` и `history_default.txt`.
- **Выход.** `:q` (или `--demo-quit`, Ctrl+C) — файл `secrets_default.json` удаляется, значения не переживают перезапуск.
- `$$TOKEN` → `is set (value hidden)`; `$$TOKEN-` → `removed`; после — `is not set`.
- **LLM.** `:llm ds explain $OUT`, где в выводе был секрет → в отправленном сообщении `****`, в шапке блока `secrets: hidden`; литеральное значение в сохранённом теге тоже маскируется в контексте `:llm ask`.
- **Заморозка маскировки.** `echo $TOKEN` → space/←→ (свернуть-развернуть), F2, F8, `:/` поиск — значение по-прежнему `****`; после `$$TOKEN-` (или `:session`/`$$TOKEN=другое`) повторный рендер **того же блока** секрет не раскрывает; `:o` тоже показывает `****`.
- **Шапки.** `:log` (F7) — подзаголовок `secrets visible`, заголовок с командой маскирован; `:watch 5 echo $TOKEN` — в шапке и теле блока `****`.
- **`.bashrc_term`.** Положить `TOKEN=from-bashrc` в `.bashrc_term_default` и дать `:env` → значение секрета не подменяется.
- **Чужие сессии.** Создать рядом `secrets_s2.json` и выйти — файл на месте (чистится только своё хранилище).
- **Буфер.** С `clear_clipboard_after_secret: true` вставка значения в `$$TOKEN=` (Ctrl+V / Shift+Insert) очищает CLIPBOARD/PRIMARY; обычная вставка (`echo `) буфер не трогает; `:cmd` с командой, где есть значение, в буфер не копируется (в журнале `Not copied`).

**Ограничения (проверить, что ведут себя именно так):** маскируется вся строка ввода — имя видно только в подзаголовке; в `> cmd` реальный терминал показывает значение, пока TUI на паузе (журнальная строка `TTY: …` уже маскирована); строка, начинающаяся с `$$`, всегда трактуется как секрет; **явные исключения по запросу человека** — `F3`, `:log`/F7 и `:cmd show` отдают настоящие данные.

Автотест: `tests/test_secrets.py`.

### 1c. Захват значения из вывода блока (`@key`)

```
printf 'Key        Value\n---        -----\nrole_id    2474a21f-uuid\n'
$MYROLE=@role_id
$$MYSEC=@role_id
$X=@nope
printf 'a\nb\nlast-val\n'
$V=@last
```

**Ожидание:** `$MYROLE=@role_id` → `Variable $MYROLE set (from block @role_id)`, значение `2474a21f-uuid`; `$$MYSEC=@role_id` — то же, но секрет (значение не в журнале); `@nope` → `not found in block output (keys: …)`; `@last` — `last-val`. Без завершённого блока — `no finished command block to capture from`. Подробный сценарий — `docs/SEED_VAULT_COMMANDS.md` (тег `vapprole`).

Автотест: `tests/test_capture.py`.

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

### Клик по ссылке с запуском

```
#clickme echo from-click
?clickme
→ клик по строке `clickme[1] `       (обычный)      — только вставка
→ Ctrl+клик по строке `clickme[1] `                 — вставка + выполнение
→ двойной клик по `clickme[1] `                    — то же (без дубля ссылки)
→ Ctrl+клик по строке `clickme `  (без tid)        — только вставка
```

**Ожидание:** обычный клик — `!clickme[1] ` во вводе, команда не запускается. Ctrl+клик и двойной клик — то же, что набрать ссылку и дважды нажать Enter: ссылка раскрывается в `echo from-click` и выполняется (в журнале блок с выводом `from-click`, ввод пуст). На двойной клик ссылка вставляется **один раз** (раньше ввод получал `!clickme[1] !clickme[1] ` и выполнилось бы `echo from-click echo from-click` — регрессия). Ссылка без tid и прочие ссылки (`:`-команды в `:?`, `.md`, `--seed`) по Ctrl+клику не выполняются. Нужен `terminal_mouse: true`.

Автотест: `tests/test_tag_ref_click.py`.

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

### 11.1. Импорт истории оболочки (`:h import`)

```text
# подготовка: в HOME лежит история bash/zsh (можно искусственно)
printf '#1700000000\necho from-bash\ngit status\n' > ~/.bash_history
:h import bash        # Shell history → …/history_default.txt: 2 line(s) from bash 2, 2 new.
:h import             # все найденные оболочки (bash, zsh, fish, ksh, nu, pwsh)
:h import bash        # повторно — «0 new» (уже имеющиеся строки не дублируются)
:h import sh          # `sh` = `ksh` (тот же ~/.sh_history)
:h import bash extra  # Usage: :h import [shell] — известные: … (лишний аргумент)
:h import nope        # Unknown shell: nope. Known: zsh, bash, …
Up                    # импортированные команды видны по ↑ и в :h /текст
```

**Ожидание:** ищутся файлы истории по ОС и `$HISTFILE` (`~/.bash_history`, `~/.zsh_history`, fish, ksh, nushell, PowerShell PSReadLine — `%APPDATA%` на Windows, XDG-каталог на Linux/macOS). Берутся последние 5000 строк каждого файла (у больших — только хвост); zsh extended (`: ts:dur;cmd`) и bash-метки `#<epoch>` разбираются, многострочные записи (в т.ч. реальная zsh-континуация `\`+newline) сворачиваются в одну строку, формат определяется и по содержимому (нестандартный `$HISTFILE`). Ничего не выполняется, файлы только читаются; если истории нет — сообщение со списком искомых путей. Отказы видны явно: `chmod 000 ~/.bash_history` → `Not read: …`, read-only `history_default.txt` → `Could not write …`, а не «0 new». Проверка: `python3 -m pytest tests/test_history_import.py -q`.

---

## Секция 12: Команды приложения

```
echo hist-line
:h
:h /hist
:h compact
:w test_output.txt
:?
:? llm
:? tags
:? nope
:?calc
:i
:md SEED_LINUX_COMMANDS.md
:c
```

**Ожидание:** `:h` показывает `hist-line` в одном блоке; `:h /hist` — уникальные совпадения в подсказках (свежие сверху); `:h compact` ужимает старые повторы, хвост `history_keep` не трогает; `test_output.txt` создан; `:?` — общая справка (есть `:md` и раздел «Темы справки» с 10 темами); `:? llm` — справка про провайдеров и `@file` (не общая!); `:? tags` — про `?`/`!tag`; `:? nope` — явная ошибка со списком тем (`Нет такой темы справки: 'nope'. Темы: :? calc, …`), а не молчаливая общая справка; `:?calc` — подсказка про пробел («`:? calc`, а не `:?calc`»); после `:? ` Tab показывает 10 тем; `:i` — help ingress; `:md` — модалка Markdown (Esc / `q` закрывает, колесо не крутит журнал); `:c` — `All blocks cleared.`

`:q` — выход (в конце сессии). `:cd`, `:r`, `:theme` — секция 25.

Автотесты: `test_s12_colon_commands`, `test_colon_h_search_newest_first`, `test_colon_h_compact_uniques_old_keeps_tail`, `test_colon_md_opens_formatted_handbook`, `test_md_viewer_wheel_does_not_scroll_journal`, `tests/test_help_topics.py` (11: алиасы, неизвестная тема, `:?calc`, оглавление против реестра, подсказки тем).

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

## Секция 14c: Перечитать env (`:env`)

```
:env extra
:env
```

**Ожидание:** лишний аргумент — `Usage: :env`. Без аргументов перечитывает `.bashrc_term*` и алиасы `~/.bashrc`; в журнале `Reloaded .bashrc_term_…: N vars`. После `> cmd` файлы и `export` той же оболочки подхватываются сами.

Автотест: `test_colon_env_reloads_bashrc`.

---

## Секция 14d: Клик и клавиатурный скролл журнала

Два блока (`echo click-first`, `echo click-second`). Клик по первому, затем по второму — фокус без прыжка к началу блока.

`seq` с длинным выводом: из ввода PageUp входит в просмотр последнего блока, повторный PageUp не прыгает к строке 1. Стрелки / PageUp на сфокусированном блоке активируют **видимый** блок.

Колесо мыши прокручивает журнал по **3 строки** за щелчок (как в `:log`/F7 и md-вьювере) — большой блок вроде `:?` (~290 строк) листается без сотен щелчков. Стрелки остаются по одной строке — точный шаг.

Клик по большому инфоблоку (`:?`, `:welcome`, `??`) подсвечивает его **сразу**, возврат кликом во ввод — тоже без задержки: strip'ы строятся по видимым строкам, фон фокуса накладывается поверх (подробности — в `CLAUDE.md`, ключ `line_api_blocks`). Разметка блока при этом сохраняется (ссылки, bold).

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

**Ожидание:** `:r` кладёт команду сфокусированного (или последнего) блока во ввод. `:cmd [N] [show]` — материализует команду блока с текущими `$VAR`/секретами и кладёт в буфер обмена; в журнале — маскированная версия, `show` печатает полную (секреты видны). `:cmd 5` при одном блоке — `too far back`. `cd` / `:cd` меняет cwd для shell-команд; нет каталога — ошибка, не молчание. База тегов / история / `.bashrc_term*` остаются в каталоге запуска (пустой `mytags.db` в новой папке не появляется). Серое приглашение слева в строке ввода (`~/путь ❯`) показывает текущий каталог и меняется после каждого `cd`/`:cd` (`~` вместо дома, длинный путь — хвостом; клик по пути возвращает фокус в строку). Заголовок блока по-прежнему несёт полный путь. `:theme` показывает / ставит тему в `settings.yml`. `d` на журнале переключает dark/light.

```
#demo echo one
:export demo
:import demo.json
:export
```

**Ожидание:** `:export demo` → `demo.json` (каноническая схема: `export_date`, `total_commands`, `tag_comments`, `commands` с `id`/`timestamp`/`deleted`); `:export demo.json` без тега → `demo.json`; `:export * library.json` → вся библиотека каноническим JSON (`tag_filter` пуст — именно такой файл нужен для `library_url`), `:export * library.md` — Markdown-каталог; `:import demo.json` создаёт **новые** `tid` (не затирает); `:export` без аргументов — Usage со обоими формами `*`. Глобальные `id` из файла импортом не берутся (чужой `id` не может затереть другую строку). То же и в CLI — одна реализация, `src/db_transfer.py` — но лаунчер живёт в каталоге репозитория: из каталога данных зовите его по пути (`python3 /путь/к/IDvjPy/backup_db.py export f.json` / `import f.json [--mode replace] [--keep-tids]`), а `settings.yml` и `backups/` он берёт из текущего каталога; адресная правка по `tid` — `export-csv` / `import-csv`; снимок и возврат — `backup` / `restore <file>` (со снимком до операции); обёртка `./backup_db.sh backup|restore <file>`.

Автотесты: `test_replay_puts_command_in_input`, `test_cd_changes_app_cwd`, `test_colon_cd_and_missing_dir`, `test_colon_theme_sets_and_lists`, `test_toggle_dark_saves_theme`, `test_export_and_import_tag`, `test_export_star_json_is_whole_library`, `test_export_usage_lists_both_library_formats`, `tests/test_db_transfer.py`, `tests/test_backup_cli.py`, `tests/test_cwd_prompt.py` (приглашение с путём).

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

### Новое окно приложения (`:new`)

```
:new
:new stage
:new stage /srv/app
:new - /tmp
:session new stage2
:new ../oops
```

**Ожидание:** `:new` открывает **новое окно терминала** с ещё одним экземпляром приложения: своя сессия (`.bashrc_term_<NAME>` / `history_<NAME>.txt`), общий data-каталог и БД тегов; в журнале `New window (session NAME, cwd DIR): Opened: … pid N`. Второй аргумент — рабочий каталог новой сессии (`:new stage /srv/app`, `~` раскрывается; нет каталога → `not a directory`); без него — data-каталог. Без имени / `-` — свободное `s2`/`s3` **среди работающих окон** (реестр `session_<имя>.pid` в data-каталоге, `src/session_registry.py`): файлы закрытых сессий (`history_s2.txt`, `.bashrc_term_s2`) имя не занимают, поэтому `Ctrl+N` не уползает на `s4`, `s5` в одной сессии. Два нажатия подряд при живом окне — разные имена (`s2`, затем `s3`; имя резервируется сразу при запуске терминала); закрыли `s2` — имя снова свободно. `:session new …` — то же. `Ctrl+N` (кнопка `New session` в футере) — `:new` без аргументов. Неверное имя — `Usage: :new`. Секреты (`$$…`) в новое окно не переносятся. Терминал: `$TERMINAL` (напр. `kitty` / `alacritty -e`), иначе из системных; запуск — `$IDVJPY_LAUNCH` (`uv run idvjpy`) или `python3 <запущенный app.py>`. Без доступного терминала — явная ошибка `set $TERMINAL=`.

Автотесты: `tests/test_new_window.py` (в т.ч. автоимя: файлы закрытых сессий его не сдвигают, два `Ctrl+N` → `s2`/`s3`, имя освобождается после выхода), `tests/test_session_registry.py` (реестр `session_*.pid`), `tests/test_gui_open.py` (`build_terminal_exec_argv`).

Автотест: `test_colon_session_creates_and_switches`.

### Пересылка команд между сессиями (`:send`)

```
:send
:send default echo from-other
:send stage uptime
:send! default seq 3
:send * echo everyone
:send ../oops echo hi
$$TOKEN=super-secret
:send beta curl -H "Bearer $TOKEN" https://api
:send! beta echo token=$TOKEN      # у цели выполнится, значение не светится
```

**Ожидание:** `:send` без аргументов — справка (`:send[!] <session|*> <command…>`, текущая и другие сессии, `pending inbox`). `:send default echo …` (своя сессия) — команда дописывается во ввод, блок `Forwarded from default: …`; запуск — Enter. `:send <сессия> …` — команда уходит в ящик `inbox_<сессия>.jsonl` (0600) в data-каталоге, журнал `Sent to <сессия> (insert): …`. `:send!` — режим `run`: целевая сессия выполнит команду сразу. `*` — всем сессиям, кроме своей. Команда материализуется у отправителя (`$VAR`/`$OUT`, алиасы). **Секреты `$$` едут именем:** в команде остаётся `$TOKEN`, а значение отправитель кладёт в секретное хранилище цели (`secrets_<сессия>.json`, 0600, чистится при выходе её сессии) — в журнале отправителя это видно как `secret value(s) → target secrets file: $TOKEN → beta`; если у цели своё значение этого имени, оно **не перезаписывается** (`target's own secret(s) kept`), и команда выполнится с ним. Поэтому пересланная команда с секретом у цели действительно выполняется, а значения нет ни в ящике, ни в её журнале/истории (проверить: `grep -r super-secret ~/.config/idvjpy/` — найдётся только в `secrets_*.json`). Если значение секрета засветилось в тексте иначе (`$OUT` блока, алиас, вставлено руками) — оно маскируется `****` и отправитель прямо говорит, что команда у цели не выполнится; для рабочей пересылки пишите `$NAME`. Целевая сессия опрашивает ящик раз в секунду (и перед доставкой перечитывает свой secrets-файл); сообщение для незапущенной сессии ждёт её старта. Пересылка, пришедшая во время набранного текста, дописывается в конец, не затирая. Неверное имя — `Usage: :send`. Tab после `:send ` / `:send! ` подсказывает имена сессий (`*` — всем остальным; текущая помечена `(this session)`), Tab/Enter подставляют имя. Команды `:send …` / `:send! …` попадают в `history_*.txt` (повтор по ↑, `:h /`), но в выпадающих подсказках не предлагаются (как `:llm` / `:rg`); голый `:send` (справка) не пишется. Если в этот момент показывался скринсейвер, приход команды его снимает (видно журнал).

Автотест: `tests/test_session_mailbox.py`.

---

## Секция 30: Каталог seed (`:welcome`)

```
:welcome
```

**Ожидание:** `:welcome` показывает каталог seed (`Empty command database`, `--seed`, `.md`) даже если БД уже не пустая. На старте с живыми тегами — блок **Разделы** (`linux` / `k8s` / `свои`, …), без каталога empty-DB.

Автотест: `test_colon_welcome_shows_seed_catalog`, `test_startup_shows_sections_when_db_has_tags`.

---

## Секция 31: Снимок БД (`:backup`)

```
:backup
#keep echo still-here
:backup
```

**Ожидание:** на пустой БД — `Empty database, nothing to backup`, каталога `backups/` нет. После `#keep` — `Backup: …/test_history-manual-….db`, файл открывается SQLite и содержит `keep`. Лишние аргументы — `Usage: :backup`.

Автотест: `test_colon_backup_empty_db`, `test_colon_backup_writes_sqlite_copy`.

---

## Секция 32: Проводник и терминал (`:fm`, `:term`)

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

## Секция 33: Screensaver (`:screensaver`)

```
:screensaver
x
:screensaver stars
x
:screensaver matrix
x
:screensaver 0
:screensaver nope
> sleep 3
```

**Ожидание:** `:screensaver` открывает полноэкранную заставку — по умолчанию «матричный дождь» (`screensaver_matrix: true`): падающие столбцы глифов, голова яркая, хвост затухает. `:screensaver stars` — звёздное поле: звёзды летят на зрителя, среди них живые часы (`HH:MM:SS`) и дата (`YYYY-MM-DD`); `:screensaver matrix` — наоборот, вернуть дождь (выбор только на этот показ, `settings.yml` не меняется). При `screensaver_matrix: false` заставка сразу открывается звёздным полем. Общее: сверху на всю ширину — зелёная лента `!tag[tid]  cmd` если в БД есть команды; снизу слева справка команд (печать слева направо, отступ от края); снизу справа `load` 1/5/15 и `mem` (опрос раз в секунду из `/proc`), с таким же отступом от правого угла; в узком окне load может перекрыть справку. `x` закрывает и **не** попадает во ввод. После `screensaver_idle` секунд без клавиш/клика то же самое само (в тестах `screensaver_idle: 0` — выкл). `:screensaver 0` выключает на сессию; неизвестный аргумент (`:screensaver nope`) — `Usage:` со `matrix|stars`. Во время `--demo` idle-скринсейвер не стартует. `screensaver_stars: false` убирает летающую пыль/токены в звёздном поле (на матричный холст не влияет). **Возврат из `> cmd` заставкой не встречает:** пока TUI спит (настоящий TTY: `>` , Ctrl+O, `:ed`), заставка не открывается, а после возврата простой отсчитывается заново — проверка с малым `screensaver_idle` (например, `:screensaver 5`, затем `> sleep 20`): после выхода из `sleep` виден журнал с `TTY: … Exit code: 0`, а не заставка.

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

1. `echo a`, `echo b`, `echo c`; `:r 1` — во вводе `echo b`; `:r 0` — `echo c`; `:r 5` — `too far back`. С секретом: `$$S=xyz`, `echo v=$S`, `:cmd` — в буфере `echo v=xyz`, в журнале `echo v=****`; `:cmd show` печатает `echo v=xyz`.
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
16. Ожидание ответа видно: пока запрос идёт, под шапкой блока крутится спиннер и время — `⠋ thinking… 3s / 60s` (второе число — `timeout` провайдера), кадр меняется ~10 раз в секунду. Спиннер исчезает, как только пришёл ответ (или ошибка): остаётся markdown-ответ без служебной строки. При `F6` (простой режим) кадр без разметки — `⠋ thinking… 3s / 60s` обычным текстом. Ввод и журнал при этом свободны: можно листать и набирать следующее.

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
2. Первый старт кладёт **шаблон языка в режиме auto**: `LC_ALL=ru_RU.UTF-8 python3 app.py --data-dir /tmp/idvj-ru` → `settings.yml` = `src/settings/ru.yml` (русские комментарии); `LC_ALL=en_US.UTF-8` → `en.yml`; неизвестная локаль — тоже `en`. Явный `--lang` / `$IDVJPY_LANG` бьёт локаль.
3. Без флага, из каталога с `settings.yml` — данные остаются в нём (portable).
4. Без флага из пустого каталога (и без env) — системный каталог ОС (см. `src/data_dirs.py`).
5. `IDVJPY_DATA_DIR=/tmp/idvj-env python3 app.py` — каталог из переменной.

Автотест: `tests/test_data_dirs.py`.

### pip-установка из wheel (v1.55)

1. Из репозитория: `packaging/build_wheel.sh` → `packaging/dist/idvjpy_term-*.whl`.
2. В чистом venv (`pip install --no-deps <wheel>` без зависимостей не запустится — нужны deps; обычный `pip install <wheel>` ставит их из PyPI).
3. `idvjpy --data-dir /tmp/idvj-pip` — первый запуск создаёт settings/БД/history + шаблоны `settings.yml` (файл языка из `src/settings/<lang>.yml`), `llm_providers.yml`, `.bashrc_term_default` в `/tmp/idvj-pip`; `:q` — выход.
4. `idvjpy --demo short --demo-quit` — автотур из установленного пакета, корректный выход.
5. `python3 -m idvjpy_boot --demo short --demo-quit` — тот же запуск через `python -m`.
6. Ресурсы (CSS/demos/примеры) берутся из пакета: демо и темы работают без каталога репозитория рядом.
7. Из корня репозитория: `uv tool install .` → `idvjpy --help`; зависимости ставятся автоматически (textual и др.). `uv tool uninstall idvjpy-term`.
8. Из GitHub без локальной сборки: `pipx install git+https://github.com/webxed/IDvjPy` / `uv tool install git+https://github.com/webxed/IDvjPy` — корневой `setup.py` вкладывает `src/` на этапе сборки.

Автотест: `tests/test_packaging_root.py` (корневой и packaging pyproject не разъезжаются, `setup.py --version`, MANIFEST).

Проверено вручную: wheel `idvjpy_term-1.56.0` поставлен в чистый каталог; headless-`run_test` с `data_dir` (provisioning из встроенных примеров) и реальный pty-прогон `--demo short --demo-quit` (exit 0).

### Кластерный журнал `:kctx` (v1.58; список переменных настраивается с v1.129)

Переменные из списка `kctx_vars` в settings.yml (по умолчанию — `NS POD DEPLOY SVC ING APP CTR QUOTA` плюс helm `RELEASE CHART VALUES`) запоминаются по кластерам в `kctx.json` (data-каталог). Порядок имён там же задаёт порядок в списках `:kctx`.

1. Войти в кластер обычной строкой — `klogin prod` (alias → `tsh kube login`) или `kubectl config use-context prod` (когда tsh недоступен).
2. Задать `$NS=team-a`, `$POD=api-7f` → в журнале появились снимки кластера `prod` (см. `kctx.json` рядом с `settings.yml`).
3. `:kctx` — список кластеров: имя, число снимков, время последнего; у текущего — «← current».
4. `:kctx prod` — блок входа (`klogin prod || kubectl config use-context prod`) и список ранее использованных наборов переменных (`1. NS=… POD=… (дата)`).
4.1. Если у кластера ровно один набор, `:kctx <cluster>` применяет его **сразу**: списка из одной строки нет, InfoBlock `kctx <cluster> #1: NS=…` с пометкой `(single set — applied at once)`. При двух и более наборах — прежний список, применение только по номеру.
5. `:kctx 1` — применить свежайший набор: переменные в `.bashrc_term_<instance>`, InfoBlock `kctx prod #1: NS=…`. Проверить: `cat .bashrc_term_default`, `echo $NS` в новой команде.
6. `:kctx staging 2` — вход в staging и применение его набора №2 одной строкой.
7. `:kctx 99` без открытого списка — подсказка «нет открытого списка»; после `:kctx <cluster>` с одним снимком — «набора 99 нет».
8. Ввод `:kctx ` + первые буквы кластера — подсказки имён из журнала (Tab/Enter).
9. Не-списочные переменные (`$EDITOR=…`) в журнал кластеров не пишутся.
10. `kctx_vars` в settings.yml: с `kctx_vars: [NS, RELEASE]` присваивание `$RELEASE=myapp` (после входа в кластер) пишет снимок, а `$POD=api-7f` — нет; `:kctx prod` показывает `RELEASE=myapp`.
11. `kctx_vars: []` (или `false`) — журнал выключен: присваивания ничего не пишут, `:kctx` без журнала говорит `kctx journal is off: kctx_vars: [] in settings.yml`.
12. Список можно писать строкой: `kctx_vars: NS, $RELEASE` (`$` и `:` отбрасываются, негодные имена — мимо).

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
- `:q` `:w` `:h` `:c` `:?` `:md` `:cd` `:fm` `:term` `:env` `:session` `:new` `:welcome` `:backup` `:screensaver` `:r` `:cmd` `:theme` `:playbook` `:update` работают
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

---

## Секция 34: Полный вывод (`:log`, F7)

```
seq 1 400
:log
:log 1
:log 999
printf 'alpha\nhit-line\ngamma\n'   # затем F7: `/` → hit → Enter → f → Esc
```

**Ожидание:** после `seq 1 400` журнал показывает последние 300 строк с пометкой `100 lines truncated ... F7 views full`. `:log` (или `F7`) открывает полноэкранный **Line-API** просмотрщик со **всеми** 400 строками (в подзаголовке `400 lines · … chars`); стрелки/PgUp/PgDn прокручивают, Esc/q закрывают. `:log 1` — предыдущий блок; `:log 999` — `is too far back`. Поиск внутри: `/` → образец → Enter (в подзаголовке `hit · line N/M`), `n` / `N` — следующее/предыдущее с заворотом, Esc — закрыть поле. Строка совпадения подсвечивается **целиком** — фоном акцента на всю ширину плюс bold, а не только найденными символами (только `bold` без фона = регрессия `Strip.apply_style`, см. v1.132). `f` — режим «только совпадения»: на экране остаются только строки с образцом, в подзаголовке `matches N/M · line K · f / Esc — all lines`, причём `K` — номер в **исходном** выводе, а `n`/`N` идут по отобранным строкам; повторный `f` или Esc возвращают весь вывод, место совпадения сохраняется. `f` без поиска — подсказка `Filter needs a search first…` и полный список; новый образец без совпадений снимает фильтр (пустой экран хуже полного). Пустой вывод — `Output is empty.`; нет блоков — `No command block to view.`

Автотест: `tests/test_output_viewer.py`.

---

## Секция 35: Справки cheat.sh (`:cht`)

Нужна сеть (или прокси; при 407 — `$PROXY_USER`/`$PROXY_PASS`).

```
:cht
:cht tar
:cht python read file
:cht go/:learn
:cht ~snapshot
:cht tar?Q
```

**Ожидание:** `:cht` без аргумента — `Usage: :cht <query>` с текущим URL и опциями. `:cht tar` — блок `$ :cht tar` с текстом шпаргалки (без ANSI). `:cht python read file` — вопрос по языку (пробелы → `+`). `:cht go/:learn` — спецстраница. `:cht tar?Q` — без комментариев. Вывод — обычный блок: работают `$OUT`, `|`, F3, F7 (там же поиск `/`), `:/`. Запрос пишется в `history_*.txt` (повтор по ↑, `:h`), но **не** появляется в подсказках. Нет сети — блок с `Network error ...` и код 1; пустой ответ — `Nothing found for '…'`.

Автотест: `tests/test_cheat_sh.py`.

---

## Секция 36: Метки буферов и пайп из блока (`:name`, `|@label`)

```
printf 'alpha\nbeta\ngamma\n'
:name buff
F8                     # диалог метки: пусто — снять, Esc — отмена
|@buff grep beta
:name
|@1 grep beta
:name buff-
:name -
:c
```

**Ожидание:** `:name buff` метит последний завершённый блок — в шапке появляется `[buff]`. `F8` открывает диалог с предзаполненной меткой (`Input.select_all`): Enter — сохранить, пусто + Enter — снять метку, Esc — отмена; невалидная метка (напр. `3`) — `Invalid label`. `|@buff grep beta` берёт stdin из этого блока (источник **не** выполняется заново) и даёт `beta`; в `history_*.txt` записан **полный** вызов `printf '…' | grep beta`, а не `|@buff grep beta`. `:name` — список меток (`buff  <-  <команда>  (N lines)`); `|@1 …` — из одного блока назад (0 = последний); `:name buff-` снимает метку, `:name -` — все. Неизвестная метка — `no labelled block '…'. Labels: …`; `:name 3` — `Usage: :name` (чисто цифровая метка запрещена: `|@3` значит «3-й блок назад»). `:c` чистит метки вместе с блоками. Примеры для подбора `awk` по большому выводу без повторного `cat`/`kubectl`.

Автотест: `tests/test_block_labels.py`.

`:send <сессия> |@buff grep beta` — метка раскрывается в `<источник> | grep beta` до отправки (в другой сессии своих меток нет, поэтому источник там выполнится заново); если метки нет у отправителя — команда не уйдёт.

---

## Секция 37: Файловые подсказки (`file_completion`)

```
touch podfile.txt project.log
cat po
kubectl get po
grep ot
cat podfile.txt | grep ot
cat ./po
cd po
```

**Ожидание:** при `file_completion: auto` (по умолчанию) `cat po` показывает файлы (`podfile.txt`), а `kubectl get po` — **не** листит cwd (нет мусора от `kubectl`/`docker`/`git`). У `grep`/`sed`/`awk`/`jq` первый аргумент — шаблон: `grep ot` файлов не листит, а `grep -n x po` — листит. Контекст считается по текущему сегменту строки: в `cat podfile.txt | grep ot` подсказки относятся к `grep`, а не к `cat`. Список, оставшийся от ранее набранного текста, скрывается сам (Esc жать не нужно), и Enter больше не затирает набранное исчезнувшим кандидатом. Явные пути (`./po`, `/…`, `~/…`) и `cd`/`pushd` работают во всех режимах. `file_completion: paths` — только явные пути и `cd`/`pushd` (голое `cat po` — без файлов). `file_completion: off` — файловых подсказок нет. Неизвестное значение — как `auto`.

Автотест: `tests/test_file_completion.py`.

---

## Секция 38: Подсказки из истории (`history_completion`)

```
@ echo no-timeout-abc
> echo tty-abc
kubectl get pods
@ ec              # в списке: ↺ @ echo no-timeout-abc
> ec              # в списке: ↺ > echo tty-abc
kub ec            # ↺ kubectl get pods (Tab/Enter — вставить, второй Enter — запуск)
```

**Ожидание:** при наборе обычной команды в выпадающем списке появляются (под маркером `↺`, свежие сверху) подходящие строки из `history_*.txt`, в том числе начинающиеся с `@` и `>` — их нет в `session_history` (для `@` команда запускается уже без префикса). `Tab`/`Enter` вставляют полную команду в строку (не запускают); следующий `Enter` — запуск. Дедупликация с кандидатами из БД/сессии. `history_completion: false` — только `↑` и `:h /text`; короткий ввод (<2) и `:`/`!`/`?`/`#`/`$` — без истории.

Автотест: `tests/test_history_completion.py`.

### Какие `:`-команды остаются в истории (`history_queries`)

```
:llm offline привет
:stats
:h 5                  # в файле истории есть `:llm …`, но нет `:stats`
```

**Ожидание:** в `history_*.txt` (↑ / `:h`) попадают только вызовы команд из списка `history_queries` в `settings.yml` (по умолчанию `llm, cht, rg, md, run, send, send!`) — и с аргументами: `:llm` без вопроса не записывается. В подсказках эти строки не появляются, даже когда их достали из истории через ↑. `history_queries: []` (или `false`/`null`) — вызовы `:`-команд в историю не пишутся вообще; ключа нет — набор по умолчанию.

Автотест: `tests/test_history_queries.py`.

### Лента сессии (↑) против файла истории (v1.127)

```
:stats
?demo
$NS=team-a
#saved echo saved-line
!1
:h 5                  # в файле только то, что разрешено; в ↑ — всё набранное
# порядок ↑ — хронология набора (v1.131): :stats → обычная команда → ↑ даёт команду
:stats
echo after-colon
echo stale-role
↑                     # первой — echo stale-role (последняя набранная), затем :stats
```

**Ожидание:** по ↑ во время сессии перелистывается **всё**, что вводилось — `:`-команды, `?теги`, `!ссылки`, `#теги`, `$VAR=…` (включая то, что в файл не пишется), в порядке набора: строки файла (которых в этой сессии не набирали) идут первыми, лента сессии — последней, поэтому последняя набранная строка возвращается первой. Разница видна на паре «`:`-команда, затем обычная команда»: раньше обычная команда пропадала вглубь файла, и первой всплывала `:`-команда (`:screensaver` → `vault …` — первой появлялась `:screensaver`); то же касается подсказок `↺` и `:h /text` («свежие сверху» — по времени, а не по тому, в файле строка или только в ленте). В `history_<instance>.txt` попадает только разрешённое: обычные команды, `>`/`@`-строки, `# command`, хвост `history_queries`; `:stats`, `?demo`, `!1`, `#tag cmd`, `$VAR=…` в файле не появляются. Секреты (`$$VAR=…`) не запоминаются ни в ленте, ни в файле — значение не должно всплывать в строке. Повторы в ленте не дублируются; подсказки по `:`-строкам даёт своя таблица (`:`-строки в выпадающий список из ленты не попадают).

Автотест: `tests/test_session_history.py`.

### Таймаут, stdin и возврат терминала (v1.126)

```
read line; echo "rc=$? line=[$line]"   # фоновая команда видит EOF, а не клавиатуру
sleep 15                              # больше command_timeout → сообщение и подсказка
:kctx <cluster>                       # tsh kube login — без command_timeout
```

**Ожидание:** фоновая команда не получает терминал TUI: `stdin` — `/dev/null` (пайп `| cmd` по-прежнему передаёт данные), поэтому `read`/`tsh`/`kubectl`/`ssh` не «крадут» клавиши и мышь и не могут оставить терминал в чужом режиме — раньше зависший на вводе `tsh kube login` из `:kctx` делал ввод нерабочим, а заставку нельзя было закрыть. По таймауту группа убивается и подчищается (процесса не остаётся, хвост вывода попадает в блок), в блоке — `Process timed out …` и подсказка `@ cmd` (без таймаута) / `> cmd` (настоящий TTY). После убийства (таймаут или F4) приложение возвращает терминал в свой режим и снимает заставку. `:kctx <cluster>` запускает вход без `command_timeout`: `tsh` ходит в сеть и в 10 с легко не укладывается; висящий вход останавливают F4 / `:kill`.

Автотест: `tests/test_command_stdio.py` (stdin-EOF, пайп, таймаут с убийством группы и подсказкой).

---

## Секция 39: Поиск по markdown (`:rg`, Obsidian-vault)

```
mkdir -p /tmp/vault && printf '# note\nneedle here\n' > /tmp/vault/note.md
:rg
:rg needle /tmp/vault
:rg 1
:rg 9
:md /tmp/vault/note.md
:md /tmp/vault/note.md#L2
↑
# большой файл: выше md_render_lines открывается raw-видом, без подвисания
seq 1 5000 | sed 's/^/line /' > /tmp/vault/big.md
:md /tmp/vault/big.md
:md /tmp/vault/big.md#L4200
```

**Ожидание:** `:rg` без аргумента — `Usage: :rg <pattern> [dir]`, текущая база (`md_dir` / cwd), бэкенд (`ripgrep` или `built-in python`) и подсказка установки rg, если его нет. `:rg needle /tmp/vault` — заголовок с числом совпадений/файлов и фрагменты вида `note.md:2  needle here`: клик по `путь:строка` открывает файл встроенным md-просмотрщиком сразу на строке совпадения. `:rg 1` открывает первый результат (1-based) на его строке, `:rg 9` — `No result 9`. `:md /tmp/vault/note.md` открывает файл по пути (абсолютному или относительно `md_dir`/cwd); `:md …#L2` — сразу на строке 2 (в заголовке `· line 2`). `y` (или клик по имени файла в шапке) копирует **полный путь** в буфер; шапка показывает `copied: /путь`. `↑` (или `:h`) возвращает `:rg …` / `:md …`: они пишутся в `history_*.txt`, но в подсказках не предлагаются. `:md /tmp/vault/big.md` (5000 строк > `md_render_lines: 1000`) открывается мгновенно как **исходник** в Line-API просмотрщике: подзаголовок `5000 lines · raw view (over md_render_lines=1000)`, поиск `/` и `n`/`N`, `#L4200` — сразу на строке 4200 (`start_line`), `y` копирует путь и показывает `Path copied: …`. Паттерн — регулярное выражение, «умный регистр»; скрытые/служебные каталоги (`.git`, `.obsidian`, `node_modules`) пропускаются.

Автотест: `tests/test_md_search.py`.

---

## Секция 40: Режим чтения журнала (новый вывод не уводит вид)

```
seq 1 200
# колесом вверх — читаем; затем из другой сессии: :send! default seq 1 3
# далее в журнале: Esc, ls, Enter
```

**Ожидание:** пока вид журнала отскроллен вверх (колесо/PgUp) или фокус на блоке журнала, новый вывод (фон `:watch`, ответ `:llm`, долгая команда, пришедший `:send`) **дописывается вниз, но viewport и фокус не двигаются** — можно спокойно читать/копировать. Слежение возвращается само, когда докрутил до нижнего края, и принудительно — при запуске команды (Enter). При этом `|` / `$OUT` берут stdout блока, на котором был фокус (это и есть документированное «сфокусированного блока»).

Автотест: `tests/test_journal_follow.py`.

## Секция 41: Подсказки `:`-команд

```
:                       # список всех команд приложения с описанием
:m                      # фильтр по буквам → :md, :mv
<Esc>                   # закрыть подсказку
:wa <Tab>               # вставляет `:watch ` (команда не запускается)
:c                      # точное имя + Enter — выполняется :c, а не подстановка
:/                      # поиск по журналу — список команд не показывается
# в справке :? — клик по имени команды вставляет её вызов во ввод
```

**Ожидание:** на `:` открывается список всех `:`-команд с коротким описанием рядом (`:md  — markdown viewer; #L<n> — source line`), набранные буквы фильтруют список; `Tab`/`Enter` вставляют `:команда ` во ввод (запуск — отдельным Enter), `Esc`/`PgUp`/`PgDn` закрывают список. Полностью набранное имя (`:c`) не мешает работе: Enter выполняет команду. `:/text` остаётся поиском по строкам журнала; после имени с пробелом (`:cd `, `:llm `, `:send `) начинаются свои подсказки (пути, провайдеры, сессии). В самой справке `:?` имена команд — кликабельные ссылки: клик вставляет `:команда ` во ввод (ничего не запускает, строку не затирает — как `!tag` в `??`); имя вне таблицы игнорируется. Новые `:`-команды обязаны попадать в таблицу `src/colon_commands.py` — это проверяет автотест.

Автотест: `tests/test_colon_commands.py`.

---

## Секция 45: Подсказки тегов при наборе `?` и клик по строке

```
#vault vault write auth/approle/login role_id=$ROLE_ID
#vault vault read secret/data/app
#vault=HashiCorp Vault
?                      # список тегов: ?vault  (2)  HashiCorp Vault
?va                    # фильтр по буквам
<Tab>                  # вставляет ?vault (без запуска)
<Enter>                # запускает запрос (обычное выполнение)
?                      # снова список; клик по строке ?vault — вставил и сразу выполнил
??                     # «все команды» — список тегов не мешает
?vault <пробел>        # подсказки закрыты
```

**Ожидание:** при наборе `?` (и `?префикс`) открывается список тегов: имя, число команд и комментарий тега, часто используемые — выше; буквы фильтруют, `Esc` закрывает. Ссылкой (и подсветкой) в строке становится **только сама команда** — `?vault`; счётчик `(2)` и комментарий тега остаются обычным текстом. `Tab`/`Enter` вставляют `?tag` в строку (запуск — отдельным Enter, как у `:`-команд); **клик по строке списка** подставляет `?tag` и сразу выполняет запрос. `??` (все команды) и `?tag[tid]` список не перебивает; пробел после `?tag` закрывает подсказки. В остальных списках (пути, `:команды`, `!tag`) клик по строке только вставляет — запуска нет. Нужен `terminal_mouse: true`.

Автотест: `tests/test_tag_query_hints.py`.

---

## Секция 46: Ожидание ответа `:llm` (thinking-анимация)

```
:llm ds распиши шаги       # блок под шапкой крутит спиннер, пока идёт запрос
⠋ thinking… 3s / 60s       # кадр + время + лимит провайдера (timeout)
<ответ>                    # спиннер исчез — пришёл markdown-ответ
```

**Ожидание:** пока запрос идёт в фоне, в блоке меняются кадры спиннера (~10 раз в секунду) и растёт время; второе число — допустимый лимит (`timeout` провайдера, по умолчанию 60 с). Запрос не выглядит зависанием: видно и что ждём, и сколько допустимо. Ответ (или ошибка) заменяет служебную строку целиком — вечного спиннера не остаётся. `F6` рисует кадр без разметки. Журнал и ввод при этом не блокируются.

Автотест: `tests/test_llm.py` (анимация и разные кадры, снятие после ошибки, простой режим).

---

## Секция 47: Стили в `src/app.tcss`

```
cat src/app.tcss      # Textual CSS: $surface, dock, layout, text-style
python3 -m pytest tests/test_stylesheet.py -q
```

**Ожидание:** стили TUI лежат в `src/app.tcss` (не `app.css`): это Textual CSS, а не браузерный — расширение `.tcss` не даёт редакторам разбирать файл CSS-сервером (иначе сыпались ложные «property value expected» / «Unknown property» на каждой `$переменной`). При запуске видны те же цвета и рамки, что и раньше: `CSS_PATH` указывает на `app.tcss`, в wheel файл попадает через glob `src/**/*`.

Автотест: `tests/test_stylesheet.py`.

---

## Секция 48: Тема `matrix` и подсветка блока в фокусе

```
:theme matrix            # зелёный фосфор на почти чёрном (сохраняется в settings.yml)
:theme                   # в списке есть matrix
:theme textual-dark      # вернуться; рамки снова свои
Ctrl+P → тема из списка  # палитра команд: подсветка применяет тему сразу, палитра открыта
Esc                      # палитра закрыта — правая рамка ввода на месте (v1.134)
# блок в фокусе: фон — мягкий оттенок основного цвета темы, а не яркая заливка
seq 1 20
<Tab>                    # фокус на блоке — фон лишь слегка светлее
:?
<Tab>                    # на большом блоке справки заливка тоже не слепит
```

**Ожидание:** `:theme matrix` включает свою тему — фон почти чёрный с зелёным оттенком, текст/акценты зелёные (`#00ff5f`, как в скринсейвере), рамки поля ввода, подсказок и просмотрщика md тоже зелёные. У остальных тем рамки остались прежними (фиолетовыми) — тема меняет их только у matrix. `d` и `:theme` работают как раньше; выбор сохраняется в `settings.yml` и подхватывается при следующем запуске. Подсветка блока в фокусе — 25% основного цвета темы поверх фона (в textual-dark скачок яркости ~19 вместо ~65 со старым `$primary-darken-1`): блок видно, но заливка не бьёт по глазам. **Смена темы через палитру команд (`Ctrl+P`) тоже не должна менять рамку поля ввода:** раньше после открытия палитры и любой смены темы поле получало `width: 1fr` из чужого `DEFAULT_CSS` (`textual.command.CommandInput` — совпадало имя класса), и с `margin: 0 1` правая рамка уезжала за правый край экрана. Класс переименован в `CommandLineInput` (v1.134); поле всегда шириной «экран − 2», рамка видна со всех сторон.

Автотест: `tests/test_themes.py`.

---

## Секция 42: Выделение мышью в журнале (Line API)

```
seq 1 5              # блок с несколькими строками
протянуть мышью по строкам 1–3   # выделение идёт через строки, а не только по первой
<отпустить кнопку>   # выделенное — в буфере (CLIPBOARD/PRIMARY/OSC 52)
:?                   # то же на большом инфоблоке
```

**Ожидание:** при протяжке мышью по блоку выделяется именно тот текст, который под курсором (несколько строк), выделенное подсвечивается и по отпусканию кнопки копируется в буфер; `Ctrl+C` снимает то же выделение, а не весь блок. Выделение идёт **ровно за курсором** (одна клетка = один символ) и влево, и вправо; не «цепляется» за конец строки и не отстаёт. Работает при `line_api_blocks: true` так же, как при `false`: в Line API Textual не рисует выделение сам, поэтому подсветка накладывается в `render_line`, а координаты строк и символов проставляют `_retag_offsets` / `_with_offset` (компоситор ищет символ по `meta['offset']`).

Автотесты: `tests/test_line_api_block.py` (протяжка по строкам, подсветка, `:?`), `tests/test_mouse_selection.py`.

---

## Секция 43: Консоль под приложением (Ctrl+O)

```
> less /etc/hosts    # вышли из less
Ctrl+O               # TUI уходит в сторону — виден реальный терминал
                     # листаем скроллбек (Shift+PgUp / колесо)
<любая клавиша>      # вернуться в TUI
```

**Ожидание:** Ctrl+O (как в Midnight Commander) сворачивает TUI и показывает консоль под ним — то, что печаталось в настоящем TTY (вывод `> cmd`, оболочка `> vim`/`> htop`). На время просмотра работает прокрутка и выделение самого терминала; любая клавиша возвращает в приложение, заголовок обновляется. Терминал без поддержки `suspend` — явное сообщение в журнале (`Error: this terminal cannot suspend the TUI to show the console.`).

Автотест: `tests/test_ux_extras.py`.

---

## Секция 44: Ответ `:llm` в markdown

```
:llm ds распиши шаги сборки образа
```

**Ожидание:** ответ приходит с форматированием — заголовки, списки, код и таблицы читаются как документ (`llm_render_markdown: true` в `settings.yml`, по умолчанию). Плоская копия не меняется: `F3`, `|`, `$OUT`/`$BLOCK`, `:w` и поиск по журналу (`:/`) работают с исходным текстом; `F2` (построчный курсор) показывает строки без форматирования, как раньше. `F6` (простой режим) или `llm_render_markdown: false` — прежний моноширинный вывод.

Автотесты: `tests/test_llm.py` (markdown, выключено ключом, простой режим).

---

## Секция 49: Вывод цветных команд — как в терминале (`ansi_colors`)

```
alias ww='curl wttr.in; curl v2d.wttr.in/Irkutsk;'
ww                     # цветной арт wttr.in
ls --color=always /
printf 'работаю 0%%\rработаю 50%%\rготово\n'
:llm ds привет        # ответ в markdown — цвета не нужны
```

**Ожидание:** вывод с ANSI-цветами рисуется цветами блока (SGR → стили Textual), а не выводится в терминал сырыми escape-кодами — раньше из-за этого цвета текли на соседние клетки, `\x1b[0m` сбрасывал стиль приложения, а `\r` уводил курсор в начало строки: вывод выглядел сломанным при том, что сама команда отрабатывала. Теперь курсорные/стирающие/OSC-последовательности и управляющие символы вырезаются всегда, а `\r`-перерисовка (прогресс-бары `curl`/`docker`/`pip`) сворачивается до итоговой строки — в блоке виден результат, а не все промежуточные кадры (для этого вывод читается байтами: `text=True` переводил `\r` в `\n`).

Плоский текст всегда без escape-кодов: `F3` (копия блока), `| cmd`, `$OUT`/`$BLOCK`, `:log` / `F7`, `@key` (вычитка значений из таблиц vault) — в буфер обмена и в следующую команду не уходят ANSI-последовательности. `F6` (простой режим) и `ansi_colors: false` выключают цвета: вывод плоский.

Автотесты: `tests/test_ansi_output.py` (юнит: SGR/OSC/управляющие/`\r`, лимит разбора; Pilot: цвета в кадре без сырых ESC, `F3` и `|` получают плоский текст, `F6` и ключ выключают цвета), `tests/test_cheat_sh.py` (`strip_ansi` — общий разбор).

---

## Секция 50: Прогон цепочки — runbook (`:run`)

Проверка на цепочке vault (комментарии-директивы уже в seed):

```
python3 src/seed_vault.py --seed   # в data-каталоге: без него в БД останется старый vapprole
:run vapprole --dry      # план: видно режимы шагов, ничего не выполняется
:run vapprole            # токен (manual) → роль (manual) → role_id → secret_id
                         # (manual) → login → подмена токена → проверка
:run vapprole --step     # полуавтомат: каждый шаг вставляется и ждёт Enter
:run stop                # остановить между шагами (или Esc)
:run <тег-без-директив> --dry   # в плане note: the tag has no run: directives — every step will run auto
```

**Ожидание:** перед прогоном в журнал печатается план (шаги с режимами и подсказками), в подзаголовке — `RUN vapprole · 3/9 · auto · Esc stops`. Шаги `auto` идут сами и ждут завершения команды; `manual` вставляет строку в ввод и ждёт — её можно править и запустить Enter, а пустой Enter пропускает шаг; `prompt` оставляет ввод пустым и ждёт набранную строку. Шаги 1 и 2 в `vapprole` — префиксы (`$$VAULT_TOKEN=`, `$ROLE=`): значение надо **дописать** после `=`, иначе роль останется пустой. Если в теге нет ни одной `run:`-директивы (устаревший сид, свой тег до v1.124), план печатает `note: the tag has no run: directives — every step will run auto` — это предупреждение, а не отказ; при `--step` оно снимается (все шаги и так ждут Enter). Ошибка auto-шага (`exit ≠ 0`) останавливает прогон с сообщением о номере шага (`run:continue` в комментарии отменяет остановку); Esc останавливает на любом шаге, сама команда — F4 / `:kill`. Пока прогон идёт, заставка не всплывает, `:send` откладывается, смена сессии отклоняется; `:run` пишется в `history_*.txt` (↑ / `:h`), но не в подсказки, а вставленные прогоном шаги не попадают в `:playbook`.

Свой YAML (`:playbook`-файл тоже подойдёт):

```yaml
title: vault approle
pause: 0.3
steps:
  - type: $$VAULT_TOKEN=
    manual: true
    caption: токен из vault.website (вставить после =)
  - $ROLE=
  - prompt: имя AppRole
```

Автотесты: `tests/test_runbook.py` (27: разбор директив/YAML/плана и Pilot: auto-цепочка, manual ждёт Enter, prompt ждёт набранную строку, пустой Enter пропускает шаг, тег без директив — `note:` в плане, стоп по ошибке и `run:continue`, Esc и `:run stop`, `--dry`, свой YAML, отказы при `:watch`/втором прогоне).

---

## Секция 52: Импорт библиотеки по ссылке (`:import <url>`)

Файл всей библиотеки — из TUI (`:export * library.json`; расширение `.json` = вся библиотека,
`.md` = Markdown-каталог) или лаунчером из каталога репозитория (из каталога данных — по пути):

```text
:export * library.json                        # в TUI; файл появится в cwd приложения
python3 /путь/к/IDvjPy/backup_db.py export library.json   # CLI: ляжет в backups/ каталога данных
cd <каталог с library.json> && python3 -m http.server 8000
```

`python3 backup_db.py …` из чужого каталога падает на `can't open file '…/backup_db.py': [Errno 2]` —
лаунчер живёт в репозитории; `settings.yml` и `backups/` он берёт из текущего каталога.

В TUI:

```text
:import http://127.0.0.1:8000/library.json --dry             # отказ: http:// не шифрован
:import http://127.0.0.1:8000/library.json --dry --insecure # план (явно разрешён http://)
:import https://host/library.json                           # план + драфт подтверждения
:import https://host/library.json --yes                     # импорт сразу
:import                                                     # берёт library_url из settings.yml
:import --nope                                              # Usage: :import …
```

**Ожидание:** ссылка распознаётся по схеме (`https://` / `http://`), имя без схемы — по-прежнему локальный файл. По умолчанию разрешён только `https://` (`Refusing …: http:// is not encrypted. Use https:// or pass --insecure if you trust the source.`); `--insecure` снимает запрет, и это видно в сообщении. Загрузка идёт в фоне (UI не блокируется, в подзаголовке `Fetching …`), лимит 2 МБ, таймаут 10 с, прокси с логином — те же `$PROXY_USER` / `$PROXY_PASS`, что у `:update` и `:llm` (при «407» — подсказка). Внешний импорт **всегда** сначала показывает план (`Import preview — <url>`: сколько строк добавится/пропустится, какие теги новые; отдельной строкой — предупреждение, если в файле есть `run:`-директивы: `:run <тег>` выполнит шаги `auto` без подтверждения), а во ввод подставляется готовая строка `:import <url> --yes` — импорт начинается только по второму Enter (принцип «собрал — потом запустил»). `--dry` показывает только план и ничего не подставляет; `--yes` импортирует сразу. Файл всей библиотеки (`tag_filter` пуст) — «обновить»: занятая пара `(тег, tid)` пропускается; файл одного тега — «добавить» с новыми `tid`. Payload со значением живого `$$`-секрета отклоняется (`Refused: …`) — значение секрета не должно приезжать извне и попадать в БД/журнал. `:import` без аргумента берёт `library_url` из `settings.yml` (пусто — `No import source: …`). Ошибка сети — явный текст в журнале, без пароля прокси и без userinfo из URL.

Автотесты: `tests/test_remote_import.py` (транспорт на фейковом `net.open_url`: только https, `--insecure`, чтение чанками и лимит размера, подсказка при 407, `safe_url` без userinfo; план импорта и сверка `run_mode` с `runbook`; Pilot: preview + драфт `--yes`, `--yes` применяет, `--dry` без драфта, `library_url` из settings, отказ при живом секрете, предупреждение про `run:`, локальный файл с `--dry`), `tests/test_net.py` (прокси-хелперы: `inject_proxy_userinfo`, `proxy_handler_map`, `redact_proxy_secrets`, `format_fetch_error`).

---

## Секция 51: Язык интерфейса (`:lang`, `:relang`, ключ `language`)

```text
:lang                 # текущий и список: Language: en / Available: en, ru, zh
:lang ru              # выбрать и сохранить в settings.yml
:lang zh              # китайский интерфейс (кириллицы нет, иероглифы в тексте)
:lang de              # Unknown language: de. Type :lang for the list.
:lang auto            # следовать $LANG / $LC_ALL
:relang               # справка: Current UI: en / Available: en, ru, zh / Use: :relang <code>
:relang ru            # перевести комментарии засеянной БД на русский (снимок в backups/)
:relang zh            # …на китайский (исходник — src/seed_text/zh/)
:relang de            # Unknown language: de. Type :relang for the list.
:relang auto          # по $LANG / $LC_ALL
:?                    # справка — на выбранном языке (ru: «Справка по командам», zh: 命令帮助)
:welcome              # каталог seed («Пустая база команд» / 空命令数据库)
:screensaver          # подсказки внизу — из locales/<lang>/screensaver.yml
```

Разово при запуске: `python3 app.py --lang ru`, `$IDVJPY_LANG=ru python3 app.py`.

**Ожидание:** язык влияет только на текст — сообщения (`:kctx`, `:watch`, `:run`, `:llm offline`, стартовый блок), подсказки `:`-команд, каталог `:welcome`, строки справки заставки и сама справка `:?` / `:? <тема>` (`calc`, `run`, `i`, `md`, `llm`, `tags`, `vars`, `kctx`, `send`, `session`, `import`). `en` — источник правды: `src/locales/en.yml` + части `src/locales/en/*.yml` (`screensaver`, `seed`) + `src/locales/help/en/*.txt`; `ru` и `zh` — перевод всего того же (204 ключа; тест сторожит паритет ключ-в-ключ). Отсутствующий ключ отдаёт английский текст, неизвестный ключ печатается как есть (пустоты нет). Команды, имена тегов, ключи настроек, имена файлов и слоган «Define your variables…» не переводятся. Смена языка применяется к тексту, напечатанному **после** неё — уже показанные блоки не перерисовываются. `:relang <код>` переводит не UI, а **комментарии библиотеки в БД**: трогает только канонические теги/команды сидов (матч по тегу и тексту команды; linux-дополнения `logs` / `file[12]` / `net[10..11]` — по позиции `tid-1`), пользовательские теги, команды и правленые руками комментарии остаются, перед записью — снимок БД в `backups/`. Проверка: `python3 -m pytest tests/test_i18n.py tests/test_seed_i18n.py tests/test_relang.py -q`.

**Контент по языкам.** Демо-туры: базовый `src/demos/<tour>.yml` хранит шаги, текст — в `src/demos/text/<lang>/<tour>.yml` (`title`, `captions`/`types` по номеру шага), так что `--demo short` говорит на языке интерфейса (слои `en` и `zh`). Комментарии сидов: `src/seed_text/<lang>/<handbook>.yml` (ключ — тег + позиция), язык берётся из `language` в `settings.yml` / `$IDVJPY_LANG`; поэтому `python3 src/seed_git.py --seed` при `language: en` кладёт английские подписи, при `language: zh` — китайские, а при `language: ru` — базовые русские (встроенные в `seed_*.py`). Уже посеянную БД переводит `:relang <код>` (или `python3 src/relang.py --lang zh`): переписываются только комментарии канонических строк сидов, пользовательские теги/команды и правленые руками комментарии остаются, снимок — в `backups/`. Полный повторный `--seed` тоже сменит язык, но заменит свои теги (`:backup` перед этим). Справочники: `handbook_md_path` сначала ищет `docs/<lang>/NAME` (есть `docs/en/` и `docs/zh/`). `:llm` без `answer_language` у провайдера отвечает на языке интерфейса (`off`/`none` выключают правило).

**Автотесты:** `tests/test_i18n.py` (паритет ключей en↔**каждый** язык (ru, zh) — параметризовано, отсутствие кириллицы в `en`, ловушка YAML-ключей `off`/`n`/`N`, нормализация кода языка (`ru_RU.UTF-8` → `ru`), приоритет CLI → env → settings, `auto` по `$LC_ALL`, `:lang` — список/смена/сохранение/неизвестный код, язык из settings применяется при старте, у каждой локали **свой** файл каждой справки, все `catalog.desc.*`, каталог заставки сходится с встроенным набором), `tests/test_seed_i18n.py` (покрытие встроенных комментариев и «тег ровно в одном файле» — для каждого языка слоя; кириллицы нет в `en`), `tests/test_demo_i18n.py` (ключи демо-слоя совпадают с `en`, перевод реально накладывается на шаги, команды не трогаются), `tests/test_relang.py` (11: en↔ru/zh для команд и тегов, правленые и пользовательские строки не трогаются, снимок БД, linux-extra по tid, повторный прогон — no-op, CLI, `:relang` в TUI), `tests/test_seed_catalog.py` / `tests/test_commands.py` (каталог из локалей; `docs/<lang>/<NAME>.md` для каждого языка), `tests/test_screensaver.py` (строки из каталога), `tests/test_colon_commands.py` (подсказки из локали).

---

**Версия документа**: v1.98
**Версия приложения**: v1.152
**Автотесты**: `tests/test_cmd_scenarios.py`, `tests/test_commands.py`, `tests/test_completion.py`, `tests/test_tags.py`, `tests/test_seed_catalog.py`, `tests/test_json_viewer.py`, `tests/test_demo.py`, `tests/test_screensaver.py`, `tests/test_calc.py`, `tests/test_ipcalc.py`, `tests/test_md_search.py`, `tests/test_output_viewer.py`, `tests/test_journal_follow.py`, `tests/test_session_mailbox.py`, `tests/test_session_registry.py`, `tests/test_colon_commands.py`, `tests/test_help_topics.py`, `tests/test_secrets.py`, `tests/test_history_import.py`, `tests/test_db_transfer.py`, `tests/test_backup_cli.py`, `tests/test_net.py`, `tests/test_remote_import.py`, `tests/test_relang.py`, `tests/test_demo_i18n.py`, `tests/test_history_import.py`, `tests/test_tag_ref_click.py`, `tests/test_line_api_block.py`, `tests/test_ux_extras.py`, `tests/test_llm.py`, `tests/test_tag_query_hints.py`, `tests/test_mouse_selection.py`, `tests/test_ansi_output.py`  
**Дата**: 2026-09-15
