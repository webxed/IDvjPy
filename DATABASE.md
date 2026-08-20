# Как приложение читает команды из базы данных

IDvjPy_term хранит тегированные команды в SQLite. Этот файл описывает текущую схему, кэш в памяти и все пути чтения (состояние на **v1.23**).

Код: `src/database_v2.py` (доступ к SQLite), `src/app.py` (маршрутизация `?`, `!`, `!!`, Tab, старт). Старый модуль `src/database.py` приложение не использует.

При первом запуске файл БД создаётся пустым. Если живых команд нет (`has_live_commands` = false), в журнале показывается каталог seed-скриптов.

---

## Файл базы

Путь задаётся в `settings.yml`:

```yaml
database_tags_file: mytags.db
```

При старте `CommandRunner.on_mount()` читает этот ключ в `self.db_file` и вызывает `database.init_db()`. Если ключа нет, используется запасной `mytags.db` (`FILE_DATABASE`).

`history_<instance>.txt` к SQLite не относится: туда пишутся только обычные shell-команды текущей сессии (без префиксов `# ? ! : | $`). Старый `history.txt` копируется в файл инстанса, если его ещё нет.

---

## Схема

Две таблицы.

### `commands`

| Колонка | Смысл |
|---------|--------|
| `id` | Глобальный ID, autoincrement по всей таблице. Используется в `!1`, `!! 1 2`. |
| `tag` | Имя тега |
| `tid` | Локальный ID внутри тега. Используется в `!deploy[1]`, `!! deploy[1]`. |
| `command` | Текст команды (ссылки `!tag[tid]` сохраняются как есть, без раскрытия) |
| `timestamp` | Время записи |
| `deleted` | Soft-delete: `0` живая, `1` скрыта |
| `comment` | Комментарий к этой команде (`#tag=ID=text`) |

Уникальность: `(tag, tid)`. Индекс: `idx_tag_tid` по `(tag, tid)` для `deleted = 0`.

### `tags`

| Колонка | Смысл |
|---------|--------|
| `tag` | PRIMARY KEY |
| `comment` | Комментарий к тегу (`#tag=text`) |

---

## Как устроено каждое чтение

Постоянного соединения и пула нет. Каждая функция в `database_v2.py`:

1. `sqlite3.connect(db_file, timeout=10)`
2. `row_factory = sqlite3.Row` (доступ по имени колонки)
3. `SELECT` / `UPDATE` / `INSERT`
4. `commit` при записи
5. `close`

Почти все выборки команд фильтруют `deleted = 0`. Удалённые через `#tag-` / `#tag-tid` в списках и выполнении не видны.

---

## Кэш `last_query_results`

В приложении это словарь `{глобальный id: текст команды}`. Это не полная копия БД, а карта **глобальных** id.

Заполняется так:

1. **Старт** — `_populate_query_results()`: `get_all_commands_with_ids()`, словарь перезаписывается целиком.
2. **Каждые 5 секунд** (`DB_RELOAD_INTERVAL`) — `_periodic_db_reload()`: те же строки дописываются/обновляются (несколько копий приложения с одной БД).
3. **Запросы `?` / `??` / `?tag`** — словарь **очищается**, затем наполняется только тем, что вернул этот запрос.

Из кэша читаются в первую очередь **числовые** id (`!! 1 2` и часть раскрытия `!ID`). Формат `tag[tid]` кэш не использует: всегда живой SQL.

Нюанс: команду только что сохранили через `#`, числовой `!! 1` может не найти её, пока не выполнен `?`/`??` или не сработал 5-секундный reload. `!! deploy[1]` при этом работает сразу, потому что идёт в БД.

---

## Пути чтения по командам TUI

### `?`

- `get_all_tags()` — уникальные теги живых команд
- `get_all_tags_with_comments()` — комментарии из таблицы `tags`

Кэш результатов запроса при этом сбрасывается (список тегов не наполняет карту id → команда).

### `??`

- `get_all_commands_with_ids()` — все живые команды, сортировка `tag`, `tid`
- группировка в UI по тегу, показ `<gid>` и `tag[tid]`
- каждый `id` пишется в `last_query_results`

### `?tag`

- `get_commands_by_tag(tag)` — `id, tid, command, comment`
- `get_tag_comment(tag)`
- кэш заполняется только командами этого тега

### `?tag[tid]`

- одна строка: `get_command_by_tid(tag, tid)`
- ссылки в тексте раскрываются через `_resolve_command_references()` (дополнительные чтения БД на каждую `!tag[tid]` / `!ID`)
- в UI шаги Original → Final

### `!tag[tid]`

Всегда SQL: `get_command_by_tid`. Текст **вставляется во ввод**, команда не запускается. Enter после этого — уже выполнение (и при наличии ссылок — ещё одно раскрытие).

### `!N` (глобальный id)

SQL: `get_command_by_global_id`. Тоже только вставка во ввод. Кэш здесь не обязателен.

### `!! …`

Разбор токенов и разделителей (`&&`, `||`, `;`, `|`, пробел и др.):

| Токен | Откуда текст |
|-------|----------------|
| `deploy[1]` | `get_command_by_tid` (БД) |
| `1`, `2` | **только** `last_query_results`; иначе ошибка `not found in last query results` |

Собранная строка вставляется во ввод, не выполняется.

### Tab-подсказки

`get_commands_by_prefix(prefix)`:

```sql
SELECT DISTINCT command FROM commands
WHERE deleted = 0 AND command LIKE 'префикс%'
ORDER BY command
```

К этому добавляются команды из истории сессии и файлы текущей директории (path-контекст). Это не подстановка по `tid`.

### Раскрытие ссылок в произвольной строке

Если во вводе есть `!tag[tid]` или `!ID` (и это не чистый `!` / `!!` без операторов), `CommandParser` разбирает строку и для каждого токена вызывает:

- `tag` + `tid` → `get_command_by_tid`
- `global_id` → сначала `last_query_results`, иначе `get_command_by_global_id`

Результат снова кладётся во ввод (ещё один Enter — выполнение).

---

## Что базу не читает

- Обычный ввод без префикса (`echo …`) — subprocess, без SQL
- `#tag cmd` — запись (`add_command`), не чтение (кроме `#tag+` / `#tag-`, там сначала lookup)
- `$VAR=value` — `.bashrc_term_*` и `local_env`, не SQLite
- JSON viewer / `$JSON` — не БД команд

---

## Функции чтения в `database_v2.py`

| Функция | SQL-смысл |
|---------|-----------|
| `get_all_tags` | `DISTINCT tag WHERE deleted = 0` |
| `get_commands_by_tag` | все живые команды тега по `tid` |
| `get_command_by_tid` | одна команда `(tag, tid)` |
| `get_command_by_global_id` | одна команда по `id` |
| `get_all_commands_with_ids` | все живые: `id, tag, tid, command, comment` |
| `get_commands_by_prefix` | `command LIKE prefix%` для completion |
| `get_tag_comment` / `get_all_tags_with_comments` | таблица `tags` |
| `get_command_comment` | `commands.comment` |

Проверка глазами:

```bash
sqlite3 mytags.db "SELECT tag, tid, id, command FROM commands WHERE deleted = 0 ORDER BY tag, tid;"
sqlite3 mytags.db "SELECT tag, comment FROM tags ORDER BY tag;"
```
