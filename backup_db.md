# backup_db.py - Database Import/Export Tool

Скрипт для импорта и экспорта базы тегов IDvjPy_term (**v1.24**, `mytags.db`). Поддерживает форматы JSON и CSV для редактирования команд в табличных редакторах.

Корневой `python3 backup_db.py` — лаунчер; код в `src/backup_db.py`. `settings.yml` и каталог `backups/` читаются из **рабочей директории** (рядом с базой), не из `src/`.

## Установка

Скрипт использует стандартные библиотеки Python. Убедитесь, что установлен Python 3.7+:

```bash
python3 --version
```

Зависимости (уже установлены в проекте):
- `yaml` (PyYAML)

## Конфигурация

Настройки бэкапов хранятся в `settings.yml`:

```yaml
# Директория для бэкапов (по умолчанию: backups)
backup_dir: backups
```

Все бэкапы автоматически сохраняются в директорию `backups/`. При импорте файлы также автоматически ищутся в этой директории, если не указан абсолютный путь.

### Использование других директорий

Чтобы сохранить бэкап в другое место, используйте абсолютный путь или префикс `./`:

```bash
# Абсолютный путь
python3 backup_db.py export /tmp/my_backup.json

# Текущая директория (с префиксом ./)
python3 backup_db.py export ./my_backup.json
```

## Обзор команд

```
backup_db.py <command> [options]

Команды:
  export           Экспорт базы в JSON
  import           Импорт базы из JSON
  export-csv       Экспорт команд в CSV
  import-csv       Импорт команд из CSV
  export-tags-csv  Экспорт комментариев тегов в CSV
  import-tags-csv  Импорт комментариев тегов из CSV
  list             Просмотр всех тегов в базе
```

---

## Экспорт/импорт JSON

### Экспорт в JSON

Полный бэкап базы с метаданными:

```bash
# Экспорт всех команд
python3 backup_db.py export backup.json

# Экспорт только одного тега
python3 backup_db.py export backup.json --tag python

# Экспорт с удалёнными командами
python3 backup_db.py export backup.json --include-deleted

# Указать конкретную базу данных
python3 backup_db.py export backup.json --db custom.db
```

**Формат JSON:**

```json
{
  "version": "2.0",
  "schema_version": "v2",
  "export_date": "2026-01-30T18:49:32.723003",
  "source_db": "mytags.db",
  "tag_filter": null,
  "total_commands": 8,
  "total_tags": 2,
  "tag_comments": {
    "deploy": "Управление nginx",
    "start": "Запуск приложения"
  },
  "commands": [
    {
      "id": 2,
      "tag": "deploy",
      "tid": 1,
      "command": "systemctl restart nginx",
      "timestamp": "2026-01-29 17:03:20.276280",
      "deleted": false,
      "comment": ""
    }
  ]
}
```

### Импорт из JSON

```bash
# Слияние с существующей базей (по умолчанию)
python3 backup_db.py import backup.json

# Замена всей базы
python3 backup_db.py import backup.json --mode replace

# Авто-назначение новых TID при конфликтах
python3 backup_db.py import backup.json --no-preserve-tid
```

**Режимы импорта:**

| Режим | Описание |
|-------|----------|
| `merge` (по умолчанию) | Обновление существующих команд + добавление новых |
| `replace` | Очистка базы перед импортом |

---

## Экспорт/импорт CSV

CSV формат предназначен для редактирования в таблицах (Excel, LibreOffice Calc, Google Sheets).

### Экспорт команд в CSV

```bash
# Экспорт всех команд
python3 backup_db.py export-csv commands.csv

# Экспорт одного тега
python3 backup_db.py export-csv commands.csv --tag python

# Экспорт с удалёнными командами
python3 backup_db.py export-csv commands.csv --include-deleted
```

**Формат CSV (commands.csv):**

```csv
tag;tid;command;comment
deploy;1;systemctl restart nginx;Перезапуск nginx
deploy;2;nginx -t;Проверка конфигурации
test;1;echo "test";Тестовая команда
```

**Структура:**
- `tag` - имя тега
- `tid` - локальный ID в пределах тега (число)
- `command` - текст команды
- `comment` - комментарий к команде (опционально)

### Импорт команд из CSV

```bash
# Слияние с существующей базей
python3 backup_db.py import-csv commands.csv

# Замена всей базы
python3 backup_db.py import-csv commands.csv --mode replace
```

**Правила импорта:**

1. **Обновление**: Если пара `tag`+`tid` существует - команда и комментарий обновляются
2. **Добавление**: Если пара `tag`+`tid` не существует - создаётся новая запись
3. **Пустые поля**: Пустые `tag` или `command` пропускаются с предупреждением
4. **Неверный TID**: Нечисловые `tid` пропускаются с предупреждением

---

## Экспорт/импорт комментариев тегов

### Экспорт комментариев тегов

```bash
python3 backup_db.py export-tags-csv tags.csv
```

**Формат CSV (tags.csv):**

```csv
tag;comment
deploy;Управление nginx
start;Запуск приложения
test;Тестовые команды
```

### Импорт комментариев тегов

```bash
python3 backup_db.py import-tags-csv tags.csv
```

---

## Просмотр базы данных

```bash
# Просмотр всех тегов
python3 backup_db.py list

# Просмотр с комментариями
python3 backup_db.py list --show-comments

# Указать конкретную базу
python3 backup_db.py list --db custom.db
```

**Пример вывода:**

```
Database: mytags.db
------------------------------------------------------------
  [deploy] 7 commands - Управление nginx
  [start] 1 commands - Запуск приложения
  [test] 1 commands
------------------------------------------------------------
  Total: 9 commands
```

---

## Типичные сценарии использования

### Бэкап перед изменениями

```bash
# Создать полный бэкап
python3 backup_db.py export backup_$(date +%Y%m%d).json
```

### Редактирование команд в Excel

```bash
# 1. Экспортировать в CSV
python3 backup_db.py export-csv commands.csv

# 2. Открыть в Excel, отредактировать, сохранить

# 3. Импортировать обратно
python3 backup_db.py import-csv commands.csv
```

### Перенос базы на другую машину

```bash
# На машине 1: экспортировать
python3 backup_db.py export my_commands.json

# Перенести файл my_commands.json

# На машине 2: импортировать
python3 backup_db.py import my_commands.json --mode replace
```

### Экспорт одного тега для обмена

```bash
# Экспортировать только тег python
python3 backup_db.py export python_scripts.json --tag python

# Импортировать в другую базу
python3 backup_db.py import python_scripts.json
```

### Массовое редактирование комментариев

```bash
# 1. Экспортировать команды
python3 backup_db.py export-csv commands.csv

# 2. Отредактировать колонку comment в таблице

# 3. Импортировать (обновятся существующие команды)
python3 backup_db.py import-csv commands.csv
```

---

## Работа с базой данных

### Файл базы данных

По умолчанию используется файл из `settings.yml`:

```yaml
database_tags_file: mytags.db
```

Можно указать другой файл через параметр `--db`:

```bash
python3 backup_db.py export backup.json --db /path/to/custom.db
```

### Структура базы (database_v2.py)

**Таблица `commands`:**
- `id` - глобальный уникальный ID (auto-increment)
- `tag` - имя тега
- `tid` - локальный ID в пределах тега (auto-increment)
- `command` - текст команды
- `timestamp` - время создания
- `deleted` - флаг мягкого удаления (0/1)
- `comment` - комментарий к команде

**Таблица `tags`:**
- `tag` - имя тега (PRIMARY KEY)
- `comment` - комментарий к тегу

---

## Обработка ошибок

### Экспорт

Если файл не существует или база пуста - будет выведено сообщение об ошибке.

### Импорт

При импорте CSV возможны предупреждения:
- `Row X has insufficient columns, skipping` - недостаточно колонок
- `Row X has empty tag or command, skipping` - пустые обязательные поля
- `Row X has invalid tid 'X', skipping` - неверный формат TID

Ошибки не прерывают импорт - продолжается обработка остальных строк.

---

## Советы

1. **Перед импортом** делайте бэкап существующей базы
2. **CSV кодировка**: UTF-8, корректно отображает кириллицу
3. **TID уникальны**: В пределах одного тега не могут быть дубликаты
4. **Режим merge**: Безопасен для обновления команд - существующие обновляются, новые добавляются
5. **Режим replace**: Полностью заменяет базу - используйте с осторожностью

---

## Примеры

```bash
# Полный цикл редактирования в таблице
python3 backup_db.py export-csv edit.csv
libreoffice edit.csv
python3 backup_db.py import-csv edit.csv

# Бэкап с датой
python3 backup_db.py export "backup_$(date +%F).json"

# Работаем с копией базы
python3 backup_db.py list --db test_history.db
python3 backup_db.py export test.json --db test_history.db
```
