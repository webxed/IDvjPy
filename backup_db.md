# backup_db.py - перенос библиотеки тегов

CLI для импорта/экспорта базы тегов IDvjPy_term (**v1.168**, `mytags.db`).
Форматы: JSON (перенос и слияние) и CSV (правка в таблицах).

Корневой `python3 backup_db.py` — лаунчер; код в `src/backup_db.py`. Запускать его надо из каталога репозитория; если данные живут в другом месте (типичный случай — алиас вида `idvjpy=~/WibeCoding/Idivjopy/app.py`), вызывайте по пути: `python3 ~/WibeCoding/Idivjopy/backup_db.py export library.json` — `settings.yml` и `backups/` при этом берутся из **текущего** каталога, а не из `src/`.
`settings.yml` и каталог `backups/` читаются из **рабочей директории** (рядом с базой), не из `src/`.

Вся работа с форматами живёт в **`src/db_transfer.py`** — это одна реализация и для CLI, и для TUI
(`:export`, `:import`, `:backup`). Раньше у CLI была своя JSON-схема и своя SQL-обвязка: обе стороны
писали `schema_version: "v2"` при разном наборе полей, а `id` из файла мог затереть чужую строку.
Теперь схема одна (запись), чтение терпимо к обоим историческим видам, а глобальные `id` из файлов
**не переносятся никогда**.

## Установка

Скрипт использует стандартные библиотеки Python и PyYAML (уже в проекте). Нужен Python 3.12+.

## Конфигурация

`settings.yml` в рабочей директории:

```yaml
database_tags_file: mytags.db   # файл базы
backup_dir: backups             # каталог для файлов переноса и снимков
```

Относительные имена файлов в командах пишутся в `backup_dir`; при импорте файл ищется сначала по
указанному пути, потом по имени в `backup_dir`. Абсолютный путь и `./имя` — «как сказано».

## Команды

```
python3 backup_db.py export <file.json> [--tag T] [--include-deleted]
python3 backup_db.py import <file.json> [--mode merge|replace] [--keep-tids]
python3 backup_db.py export-csv <file.csv> [--tag T] [--include-deleted]
python3 backup_db.py import-csv <file.csv> [--mode merge|replace]
python3 backup_db.py export-tags-csv <file.csv>
python3 backup_db.py import-tags-csv <file.csv>
python3 backup_db.py list [--show-comments]
python3 backup_db.py backup
python3 backup_db.py restore <file.json|file.csv> [--mode merge|replace]
```

У всех команд есть `--db <файл>` (по умолчанию — имя из `settings.yml`).

### JSON: перенос и слияние

```bash
python3 backup_db.py export backup.json                     # вся база
python3 backup_db.py export python.json --tag python        # один тег
python3 backup_db.py export all.json --include-deleted      # включая мягко удалённые
python3 backup_db.py import backup.json                     # merge (по умолчанию)
python3 backup_db.py import backup.json --mode replace      # очистить библиотеку и залить файл
```

Формат (канонический вид; `id`/`timestamp`/`deleted` пишутся, но при импорте не используются как ключи):

```json
{
  "version": "2.0",
  "schema_version": "v2",
  "export_date": "2026-09-19T21:00:00",
  "source_db": "mytags.db",
  "tag_filter": "python",
  "total_commands": 12,
  "total_tags": 1,
  "tag_comments": {"python": "про python"},
  "commands": [
    {"id": 42, "tag": "python", "tid": 1, "command": "python -V",
     "timestamp": "…", "deleted": 0, "comment": "версия"}
  ]
}
```

Импорт:

- `merge` (по умолчанию) — строки, у которых пара `(тег, tid)` уже занята живой командой, пропускаются
  (повторный импорт того же файла ничего не добавляет); остальные добавляются.
- `replace` — сначала очищаются команды и комментарии тегов, затем импорт.
- `--keep-tids` — сохранять `tid` из файла, если он свободен (по умолчанию каждой строке даётся новый `tid`).
- Мягко удалённые строки (`deleted: 1`) при импорте пропускаются.
- Комментарии тегов из `tag_comments` переносятся.

Тот же JSON можно забрать по ссылке: в TUI — `:import <https://…>` (или просто `:import`, если в
`settings.yml` задан `library_url` — статичная ссылка на общую библиотеку). Перед записью показывается
план (`--dry` — только план), а импорт начинается только по подтверждению (`:import <url> --yes` во вводе).
Файл всей библиотеки, каким его делает `export` (без `--tag`) или `backup`, импортируется как **обновление**:
занятая пара `(тег, tid)` пропускается; файл одного тега — как **добавление** с новыми `tid`.
Сделать такой файл можно и без CLI: в TUI `:export * library.json` (расширение решает формат: `.json` —
вся библиотека, `.md` — Markdown-каталог). CLI по ссылкам не ходит: скачайте файл и дайте его `import`.

**Точный слепок базы — это SQLite-снимок, а не JSON**: `backup`, `:backup` в TUI и авто-снимок перед
`--seed`. JSON/CSV — перенос и правка, они не восстанавливают `id`, `use_count` и мягкие удаления.

### CSV: правка в таблице

CSV команд (`tag;tid;command;comment`) — единственный **адресный** импорт: строка ищется по паре
`(тег, tid)`, существующая обновляется, отсутствующая добавляется. Комментарии тегов — отдельный файл
(`tag;comment`).

```bash
python3 backup_db.py export-csv commands.csv --tag python
$EDITOR backups/commands.csv
python3 backup_db.py import-csv commands.csv

python3 backup_db.py export-tags-csv tags.csv
python3 backup_db.py import-tags-csv tags.csv
```

### Прочее

```bash
python3 backup_db.py list --show-comments     # теги, число команд, комментарии (без TUI; в TUI — :stats / ??)
```

### backup и restore

```bash
python3 backup_db.py backup                    # снимок SQLite + JSON + CSV в backups/
python3 backup_db.py restore backup.json       # вернуть файл в базу
./backup_db.sh backup                          # то же через обёртку
./backup_db.sh restore backup.json
```

`backup` делает три вещи сразу: копию SQLite (`<база>-manual-<штамп>.db` — точный слепок),
`backup_<штамп>.json` (перенос) и `commands_<штамп>.csv` / `tags_<штамп>.csv` (правка).

`restore` **сначала снимает копию текущей базы** (`<база>-pre-restore-<штамп>.db`), потом импортирует
файл: `.json` — как `import`, `.csv` — по заголовку (с `tid` это команды, без — комментарии тегов).
Откат — скопировать снимок поверх базы.

`backup_db.sh` — тонкая обёртка над этими двумя командами (никакой своей логики разбора имён файлов).

## Снимки SQLite и `backup_dir`

Каждый `--seed` (если в базе уже есть команды), `:relang` и `:backup` кладут в `backup_dir` копию базы:
`mytags-pre-git-YYYYMMDD-HHMMSS.db`, `mytags-manual-….db` и т.п. Это полный слепок (включая `id`,
`use_count`, мягкие удаления) — вернуть его можно копированием файла поверх рабочей базы.

## Связь с TUI

| TUI | CLI | Что это |
|-----|-----|---------|
| `:export <tag> [f.json]` | `export --tag` | JSON одного тега |
| `:export * [f.md]` | — | Markdown-каталог библиотеки |
| `:export * [f.json]` | `export` (без `--tag`) | JSON всей библиотеки — файл для `library_url` |
| `:import <f.json>` | `import` | JSON в базу (в TUI — всегда с новыми `tid`) |
| `:import <https://…>` / `:import` (по `library_url`) | — (сначала скачать файл) | JSON всей библиотеки с общей ссылки: план → подтверждение → импорт |
| `:backup` | `backup` (без JSON/CSV) | снимок SQLite |
| — | `export-csv` / `import-csv` | адресная правка по `tid` |
| — | `export-tags-csv` / `import-tags-csv` | правка комментариев тегов |
| — | `restore` | импорт + снимок до операции |
| `:stats`, `??` | `list` | теги и счётчики |

## Тесты

```bash
python3 -m pytest tests/test_db_transfer.py tests/test_backup_cli.py -q
```

`tests/test_db_transfer.py` — форматы, терпимое чтение старого вида JSON, отказ от переноса `id`,
merge/replace, адресный CSV, Markdown; `tests/test_backup_cli.py` — команды CLI, round-trip,
`backup`/`restore`, обёртка `backup_db.sh`.
