# Справочник SQLite: база библиотеки изнутри

Теги **`sqlvars`** (переменные), **`sqlite`** (схема, запросы, правка), **`sqlstat`** (обзор).

Тема — SQL на **живой базе приложения**: `SELECT` / `WHERE` / `GROUP BY` / `ORDER BY`, `LIKE`,
`sqlite_master`, `EXPLAIN QUERY PLAN`, `DELETE`, подзапрос, `VACUUM`, `PRAGMA`, `.dump`.
Библиотека тегов — настоящая база, которую приложение читает при каждом `?` / `!` / `Tab`,
поэтому запросы не «учебные на бумаге»: результат видно в журнале.

```bash
python3 src/seed_sqlite.py --seed
# или вместе с остальными ops:
python3 src/seed_ops.py --seed
```

```text
$TAG=tegg
$TEXT=kubectl
!! sqlvars[1]
!! sqlstat[1]
```

`$DBFILE` подставляет **само приложение** — это файл библиотеки, который оно открыло (каталог
данных + `database_tags_file`), поэтому справочник не угадывает путь. Своё значение в
`.bashrc_term*` важнее: `export DBFILE=~/other/mytags.db`.

Нужен CLI `sqlite3` (`apt install sqlite3`, `dnf install sqlite`, `brew install sqlite`):
само приложение работает на встроенном модуле Python и без него, а справочник — про
настоящую утилиту. Первая команда набора проверяет, что она есть.

Удаление в приложении — **мягкое** (`#tag-` → `deleted = 1`), поэтому жёсткое стирание здесь
сознательно руками: tid 11–13 меняют базу, остальные только читают.

---

## sqlite (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `command -v sqlite3 \|\| echo 'sqlite3 not found: install sqlite3'` | Есть ли CLI |
| 2 | `sqlite3 $DBFILE ".tables"` | Таблицы базы |
| 3 | `sqlite3 $DBFILE ".schema"` | Схема: `commands`, `tags`, индекс |
| 4 | `sqlite3 $DBFILE "SELECT name, type FROM sqlite_master …"` | Таблицы и индекс (`sqlite_master`) |
| 5 | `sqlite3 -header -column $DBFILE "SELECT tag, COUNT(*) AS n … GROUP BY tag ORDER BY n DESC;"` | Теги по числу команд |
| 6 | `… "SELECT tag, tid, command FROM commands WHERE deleted = 0 ORDER BY tag, tid;"` | Живые команды с tid |
| 7 | `… "SELECT tag, comment FROM tags ORDER BY tag;"` | Комментарии тегов |
| 8 | `… "SELECT tag, tid, command FROM commands WHERE deleted = 1 …"` | Мягко удалённое |
| 9 | `… "SELECT command FROM commands WHERE command LIKE '%$TEXT%' AND deleted = 0 LIMIT 20;"` | Поиск по тексту (`LIKE`) |
| 10 | `… "EXPLAIN QUERY PLAN SELECT command FROM commands WHERE tag = '$TAG' AND deleted = 0;"` | План запроса (индекс `idx_tag_tid`) |
| 11 | `… "DELETE FROM commands WHERE tag = '$TAG'; DELETE FROM tags WHERE tag = '$TAG';"` | **Стереть тег жёстко** (меняет базу) |
| 12 | `… "DELETE FROM commands WHERE deleted = 1; DELETE FROM tags WHERE tag NOT IN (…);"` | **Вычистить мягко удалённое** (меняет базу) |
| 13 | `sqlite3 $DBFILE "VACUUM;"` | **Сжать файл** (меняет файл) |
| 14 | `sqlite3 $DBFILE "PRAGMA integrity_check;"` | Целостность базы |
| 15 | `sqlite3 $DBFILE ".dump" > mytags.sql` | SQL-дамп в `mytags.sql` (текущий каталог) |
| 16 | `sqlite3 $DBFILE` | Интерактивный sqlite3 (лучше `> sqlite3 $DBFILE`) |

---

## sqlstat (tid)

| tid | Цепочка |
|-----|---------|
| 1 | `!sqlite[5]` → `!sqlite[8]` → `!sqlite[14]` (живые теги → мягко удалённое → целостность) |

---

## Что здесь изучается

| Приём | Где смотреть | Смысл |
|-------|--------------|-------|
| `SELECT … WHERE` | tid 6, 8 | Фильтр по колонке; `deleted = 0` — живые строки |
| `GROUP BY` + `COUNT(*)` | tid 5 | Агрегат: сколько команд в каждом теге |
| `ORDER BY` | tid 5, 6 | Сортировка результата (`n DESC` — по убыванию агрегата) |
| `LIKE` | tid 9 | Подстрочный поиск (`%` — любое число символов) |
| `sqlite_master` | tid 4 | Служебная таблица: что вообще есть в файле |
| `EXPLAIN QUERY PLAN` | tid 10 | Как SQLite собирается выполнять запрос: `idx_tag_tid` вместо полного сканирования |
| `DELETE … WHERE` | tid 11, 12 | Удаление строк (в отличие от `UPDATE deleted = 1` у `#tag-`) |
| Подзапрос | tid 12 | `tag NOT IN (SELECT DISTINCT tag FROM commands)` — «теги без единой строки» |
| `VACUUM` | tid 13 | Пересобрать файл: место удалённых строк возвращается файловой системе |
| `PRAGMA` | tid 14 | Служебные команды SQLite (`integrity_check` — проверка целостности) |
| `.dump` / `.tables` / `.schema` | tid 2, 3, 15 | Команды самой утилиты (с точкой): метаданные и текстовый слепок |
| Флаги CLI | tid 5+ | `-header -column` — заголовки колонок и выравнивание (результат читаемее) |

---

## Схема, по которой идут запросы

Две таблицы: `commands` (`id`, `tag`, `tid`, `command`, `timestamp`, `deleted`, `comment`,
`use_count`, `last_used`) и `tags` (`tag`, `comment`). Уникальность `(tag, tid)`,
частичный индекс `idx_tag_tid` по `(tag, tid)` при `deleted = 0`.
Подробно — [`DATABASE.md`](../DATABASE.md).

Свои `%` / `_` в `LIKE` (tid 9) — это шаблон, а `?text` в приложении ищет их буквально
(`_escape_like` + `ESCAPE '\'`), поэтому результаты могут отличаться.

---

## Жёсткое удаление тега: порядок действий

1. `:backup` — снимок SQLite в `backups/` на случай ошибки.
2. Убедиться, что это тот тег: `?tegg` (список команд) и `??`.
3. `$TAG=tegg` → `!sqlite[11]` (или SQL из [`DATABASE.md`](../DATABASE.md) вручную).
4. `!sqlite[12]` — заодно вычистить мягко удалённое, `!sqlite[13]` — `VACUUM`.
5. Списки в уже открытом окне берутся из кэша в памяти: перезапустите приложение (или сделайте
   это на закрытом) — иначе тег будет виден до следующей мутации из UI.

Мягкое удаление для «просто убрать с глаз» остаётся дешевле: `#tegg-` (тег), `#tegg-2` (команда),
`#handbook--` (целый справочник), возврат — `#tegg!` / `#tegg!2` / `#handbook!!`.

---

## Смежное

| Задача | Где |
|--------|-----|
| Снимок и возврат базы | `:backup`, `python3 backup_db.py backup` / `restore <file>` |
| Экспорт/импорт (JSON/CSV/Markdown) | `:export`, `:import`, `python3 backup_db.py` |
| Комментарии тегов и команд из SQL | `?tag` / `??` показывают их; правила — `#tag=` / `#tag=ID=` |
| Счётчики запусков | `:stats` (колонки `use_count` / `last_used`) |
