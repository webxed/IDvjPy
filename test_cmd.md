# План тестирования IDvjPy_term v1.1.18

Ручной прогон TUI и зеркальные автотесты (Textual Pilot).

Автотесты по этому файлу:

```bash
python3 app.py                          # ручной прогон
python3 -m pytest tests/test_cmd_scenarios.py -v
python3 -m pytest tests/ -v             # весь набор, включая JSON/completion
```

Команды ниже безопасны (`echo`/`printf`/`seq`). Боевые `systemctl`/`nginx` не обязательны.

**Важно (отличие от v1.1.5):** `#tag` сохраняет команду **как есть**. Ссылки `!tag[tid]` / `!ID` / `!!` раскрываются при **просмотре** `?tag[tid]` и при **выполнении**, не при сохранении.

---

## Подготовка

```bash
python3 app.py
```

Автотесты поднимают приложение сами, в изолированной tmp-директории (своя БД, не `history_v2.db`).

| Клавиша | Действие |
|---------|----------|
| `Enter` | Отправить команду. Если открыт список подсказок — вставить кандидата, **не** запускать |
| `Esc` | Скрыть подсказки / вернуть фокус во ввод |
| `Tab` | Вставить выбранную подсказку |
| `Up`/`Down` | История сессии (если список подсказок закрыт) |
| `PageUp`/`PageDown` | Фокус между блоками |
| `F3` | JSON viewer для последнего блока |
| `F5` | Копировать stdout сфокусированного блока |
| `F6` | Simple output |
| `Shift+Insert` / `Ctrl+V` | Вставка из буфера |
| `Ctrl+D` | Очистить строку ввода |

---

## Секция 1: Переменные окружения

```
$PROJECT=/tmp/idivjopy_test
$EDITOR=nvim
echo $PROJECT
echo $EDITOR
```

**Ожидание:** `Variable $PROJECT set to ...`; `echo $PROJECT` печатает `/tmp/idivjopy_test`.

Синтаксис: `$VAR=value` или `$ VAR=value`. Локальные переменные приоритетнее `os.environ`.

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

**Ожидание:** список тегов; все команды с `<gid>` и `tag[tid]`; пустой тег — `(None found)`.

Автотест: `test_s06_query`.

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

## Секция 11: Навигация, история, F5

```
echo first
echo second
```

Up / Esc / Up — `echo second`, затем `echo first`.

PageUp / PageDown — фокус на блоках. Esc — обратно во ввод.

На блоке `echo first`: F5.

**Ожидание:** в буфере `first` (полный raw_stdout, без заголовка).

Автотест: `test_s11_nav_history_copy`.

---

## Секция 12: Команды приложения

```
echo hist-line
:h
:w test_output.txt
:?
:i
:c
```

**Ожидание:** `:h` показывает `hist-line` в одном блоке; `test_output.txt` создан; `:?` — help; `:i` — help ingress; `:c` — `All blocks cleared.`

`:q` — выход (в конце сессии).

Автотест: `test_s12_colon_commands`.

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

**Ожидание:** soft-delete: `cleanup[1]` пропал; после `#cleanup-` тег пустой / `(None found)`.

Автотест: `test_s13_delete`.

---

## Секция 14: Алиасы

Алиасы грузятся из `~/.bashrc` при старте. Для проверки без правки home:

в тесте алиас задаётся в `app.aliases`. Вручную можно добавить `alias mytest="echo Hello from alias"` в `~/.bashrc` и перезапустить.

```
mytest
```

**Ожидание:** `Hello from alias`.

Автотест: `test_s14_aliases`.

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
- `seq 1 400`: в UI последние ~300 строк + `truncated for UI stability`; F5 копирует полный вывод

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

## Критерии успеха

- Команды сохраняются с корректным `tid`; `-`/`=`/`+` внутри текста не ломают парсер
- Комментарии тегов и команд видны в `?` / `??` / `?tag`
- Ссылки **не** раскрываются при `#save`, раскрываются в `?tag[tid]` и при выполнении
- `!tag[tid]` и `!ID` вставляют во ввод
- `!! tag[tid]` работает сразу; `!! 1 2` — из кэша (старт или `??`)
- `| cmd` берёт stdout сфокусированного/последнего блока
- `$VAR` подставляется; `$JSON` после Enter в viewer
- `:q` `:w` `:h` `:c` `:?` работают
- Soft-delete `#tag-` / `#tag-tid`
- Большой вывод не вешает UI (обрезка + полный `raw_stdout`)
- JSON viewer и path-completion без крашей

---

## Проверка БД после ручного прогона

```bash
sqlite3 history_v2.db "SELECT tag, tid, command, comment FROM commands WHERE deleted = 0 ORDER BY tag, tid;"
sqlite3 history_v2.db "SELECT tag, comment FROM tags ORDER BY tag;"
cat .bashrc_term_default
cat history.txt
```

---

**Версия документа**: v1.4  
**Версия приложения**: v1.1.18  
**Автотесты**: `tests/test_cmd_scenarios.py`  
**Дата**: 2026-08-14
