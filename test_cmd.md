# План тестирования IDvjPy_term v1.1.2

Этот файл содержит последовательность команд для полноценного тестирования всех возможностей приложения через TUI интерфейс.

## Подготовка к тестированию

Перед началом убедитесь, что приложение запущено:
```bash
python3 app.py
```

---

## Секция 1: Первоначальная настройка и переменные окружения

### 1.1. Создание переменных проекта
```bash
$PROJECT=/home/user/test_project
$EDITOR=nvim
$DB_HOST=localhost
$DB_PORT=5432
```

### 1.2. Проверка переменных
```bash
echo $PROJECT
echo $EDITOR
echo $DB_HOST
```

**Ожидаемый результат**: Переменные должны подставиться корректно

---

## Секция 2: Сохранение команд с тегами

### 2.1. Сохранение dev-команд
```bash
#start python app.py
#start python -m debug app.py --port=8080
#test python -m pytest tests/ -v
#test python -m pytest tests/test_user.py
#test python -m coverage run -m pytest
#lint flake8 . --max-line-length=120
#lint pylint app.py --rcfile=.pylintrc
#format black .
```

### 2.2. Сохранение deploy-команд
```bash
#deploy systemctl restart nginx
#deploy nginx -t
#deploy systemctl reload nginx
#deploy git pull origin main
#deploy docker-compose up -d --build
```

### 2.3. Сохранение backup-команд
```bash
#backup rsync -av /data /backup/daily
#backup rsync -av --delete /data /backup/mirror
#backup tar -czf backup-$(date +%Y%m%d).tar.gz /data
```

### 2.4. Сохранение git-команд
```bash
#git git status
#git git diff
#git git log --oneline -10
#git git add .
#git git commit -m "updates"
```

---

## Секция 3: Комментарии к тегам

### 3.1. Добавление комментариев к тегам
```bash
#start=Startup commands for development server
#test=Testing and quality assurance commands
#lint=Code quality and linting tools
#deploy=Deployment and server management
#backup=Backup and data preservation
#git=Git version control operations
```

---

## Секция 4: Комментарии к отдельным командам

### 4.1. Комментарии к dev-командам
```bash
#start=1=Start application in normal mode
#start=2=Start application in debug mode on port 8080
#test=1=Run all tests with verbose output
#test=2=Run specific test file
#test=3=Run tests with coverage report
#lint=1=Check code style with flake8
#lint=2=Check code quality with pylint
#format=1=Format code with black
```

### 4.2. Комментарии к deploy-командам
```bash
#deploy=1=Full restart of nginx service
#deploy=2=Test nginx configuration
#deploy=3=Reload nginx without downtime
#deploy=4=Pull latest changes from git
#deploy=5=Rebuild and restart docker containers
```

### 4.3. Комментарии к backup-командам
```bash
#backup=1=Daily incremental backup to /backup/daily
#backup=2=Mirror backup with deletion of old files
#backup=3=Create compressed archive with date stamp
```

---

## Секция 5: Поиск и просмотр команд

### 5.1. Просмотр всех тегов
```bash
?
```

**Ожидаемый результат**: Список всех тегов с комментариями

### 5.2. Просмотр всех команд с группировкой
```bash
?*
```

**Ожидаемый результат**: Все команды сгруппированы по тегам, с комментариями к командам

### 5.3. Просмотр команд конкретного тега
```bash
?deploy
```

**Ожидаемый результат**: Команды тега `deploy` с комментариями

### 5.4. Просмотр команд другого тега
```bash
?test
```

**Ожидаемый результат**: Команды тега `test` с комментариями

---

## Секция 6: Выполнение команд по ID

### 6.1. Выполнение по новому формату (!tag[tid])
```bash
!deploy[1]
```

**Ожидаемый результат**: Команда `systemctl restart nginx` вставлена в поле ввода

```bash
# Нажмите Enter для выполнения
```

### 6.2. Выполнение по старому формату (!ID)
```bash
!1
```

**Ожидаемый результат**: Первая сохранённая команда вставлена в поле ввода

```bash
# Нажмите Enter для выполнения
```

### 6.3. Выполнение команды с комментариями
```bash
!test[3]
```

**Ожидаемый результат**: `python -m coverage run -m pytest` вставлена в поле ввода

---

## Секция 7: Сборка команд (!!)

### 7.1. Простая сборка с пробелами
```bash
!! 1 2 3
```

**Ожидаемый результат**: Три команды соединены пробелами

### 7.2. Сборка с последовательным выполнением
```bash
!! 4;5
```

**Ожидаемый результат**: Команды соединены через `;`

### 7.3. Сборка с условным выполнением
```bash
!! 6&&7
```

**Ожидаемый результат**: Вторая команда выполнится только если первая успешна

### 7.4. Сборка с пайпом
```bash
!! 4|8
```

**Ожидаемый результат**: Вывод первой команды передаётся во вторую

### 7.5. Комбинированная сборка
```bash
!! 1;6&&2
```

**Ожидаемый результат**: Комплексная команда с несколькими операторами

---

## Секция 8: Тестирование автоматической загрузки

### 8.1. Проверка загрузки при старте
```bash
# После первого запуска сразу выполните:
!! 1 2 3
```

**Ожидаемый результат**: Должно работать без предварительного `?*`

---

## Секция 9: Пайпинг между блоками

### 9.1. Выполнение команды для тестирования пайпинга
```bash
ls -la
```

**Действия**:
- Нажмите `PageUp` для фокуса на блоке с результатом `ls`
- Выполните:

```bash
| grep ".py"
```

**Ожидаемый результат**: Только .py файлы из вывода ls

### 9.2. Многоуровневый пайпинг
```bash
# Снова фокус на предыдущем блоке (PageUp)
| wc -l
```

**Ожидаемый результат**: Количество строк из предыдущего результата

---

## Секция 10: Навигация и история

### 10.1. Навигация по истории сессии
```bash
# Нажмите Up несколько раз
# Нажмите Down для возврата
```

**Ожидаемый результат**: Перемещение по истории команд текущей сессии

### 10.2. Навигация между блоками
```bash
# Нажмите PageUp несколько раз
# Нажмите PageDown для возврата
# Нажмите Escape для фокуса на поле ввода
```

**Ожидаемый результат**: Фокус перемещается между блоками команд

### 10.3. Копирование блока
```bash
# Фокус на любом блоке (PageUp/PageDown)
# Нажмите F5
```

**Ожидаемый результат**: Содержимое блока скопировано в буфер обмена

---

## Секция 11: Команды приложения

### 11.1. Просмотр истории
```bash
:h
:h 50
```

**Ожидаемый результат**: Последние 20/50 команд из history.txt

### 11.2. Запись блоков в файл
```bash
:w test_output.txt
```

**Ожидаемый результат**: Все блоки записаны в файл

### 11.3. Выход из приложения
```bash
:q
```

**Ожидаемый результат**: Приложение закрывается

---

## Секция 12: Удаление команд

### 12.1. Удаление конкретной команды
```bash
#test=4=This command will be deleted
#test-4
?test
```

**Ожидаемый результат**: Команда test[4] отсутствует в списке

### 12.2. Удаление всех команд тега
```bash
#cleanup Some temp commands
#cleanup echo "temp1"
#cleanup echo "temp2"
#cleanup-
?cleanup
```

**Ожидаемый результат**: Тег `cleanup` не найден (все команды удалены)

---

## Секция 13: Работа с алиасами

### 13.1. Создание временного алиаса
В другом терминале:
```bash
echo 'alias mytest="echo Hello from alias"' >> ~/.bashrc
```

В приложении:
```bash
mytest
```

**Ожидаемый результат**: Вывод "Hello from alias"

---

## Секция 14: Стресс-тестирование

### 14.1. Длинная команда
```bash
#stress find / -name "*.py" -type f -exec grep -l "import" {} \; 2>/dev/null | head -20
```

### 14.2. Команда с выводом ошибки
```bash
#invalid /bin/invalid-command-that-does-not-exist
```

**Ожидаемый результат**: Обработка ошибки корректно

### 14.3. Таймаут команды
```bash
#timeout sleep 15
```

**Ожидаемый результат**: Команда прервана по таймауту (по умолчанию 10 сек)

---

## Секция 15: Интеграционные сценарии

### 15.1. Полный цикл разработки
```bash
# 1. Инициализация проекта
$PROJECT=myapp
$EDITOR=vim

# 2. Сохранение команд разработки
#dev vim app.py
#dev python app.py
#dev python -m pytest

# 3. Сохранение команд деплоя
#prod systemctl restart myapp
#prod systemctl status myapp

# 4. Добавление комментариев
#dev=Development workflow
#dev=1=Edit main application file
#dev=2=Run application locally
#dev=3=Run test suite
#prod=Production deployment
#prod=1=Restart application service
#prod=2=Check service status

# 5. Выполнение команд
!dev[2]
# Нажмите Enter

!prod[1]
# Нажмите Enter

# 6. Сборка цепочки команд
!! dev[1];dev[3]&&prod[1]
# Нажмите Enter
```

### 15.2. Резервное копирование с проверкой
```bash
# Сохранение сценария бэкапа
#backup tar -czf /backup/data.tar.gz /data
#backup ls -lh /backup/data.tar.gz
#backup sha256sum /backup/data.tar.gz

# Выполнение с проверкой
!! backup[1];backup[2]&&backup[3]
# Нажмите Enter
```

---

## Секция 16: Тестирование edge cases

### 16.1. Пустой тег
```bash
#
```

**Ожидаемый результат**: Сообщение об ошибке "Invalid syntax"

### 16.2. Неверный формат ID
```bash
!abc[xyz]
!notanumber
```

**Ожидаемый результат**: Сообщение об ошибке "Invalid syntax"

### 16.3. Несуществующий ID
```bash
!9999
!deploy[999]
```

**Ожидаемый результат**: "Error: Command not found"

### 16.4. Специальные символы в комментариях
```bash
#special=Command with @#$ symbols
#special=1=Test special chars: @#$%^&*()
```

**Ожидаемый результат**: Комментарии сохранены корректно

### 16.5. Очень длинный комментарий
```bash
#long=1=This is a very long comment that should be stored properly in the database without any issues or truncation
```

**Ожидаемый результат**: Длинный комментарий сохранён полностью

---

## Секция 17: Производительность

### 17.1. Множественные команды
Сохраните 50+ команд:
```bash
#perf echo "test 1"
#perf echo "test 2"
# ... (повторить 50 раз)
```

### 17.2. Проверка быстродействия
```bash
?*
```

**Ожидаемый результат**: Все команды отображаются быстро, интерфейс не зависает

---

## Секция 18: Итоговая проверка

### 18.1. Финальная проверка всех функций
```bash
# 1. Переменные
echo $PROJECT

# 2. Все теги
?

# 3. Все команды
?*

# 4. Конкретный тег
?deploy

# 5. Выполнение команды
!deploy[1]

# 6. Сборка команд
!! 1 2 3

# 7. Пайпинг
ls -la
# PageUp на блок ls
| grep ".py"

# 8. История
:h

# 9. Запись в файл
:w final_test.txt

# 10. Выход
:q
```

---

## Критерии успешного тестирования

✅ **Успешное прохождение теста, если**:
- Все команды сохраняются корректно с правильными tid
- Комментарии к тегам отображаются в `?`
- Комментарии к командам отображаются в `?*` и `?tag`
- Команда `!!` работает сразу после запуска (без предварительного `?*`)
- Оба формата выполнения команд работают: `!tag[tid]` и `!ID`
- Пайпинг между блоками работает корректно
- Переменные окружения подставляются в командах
- Навигация (PageUp/PageDown, Up/Down, Escape) работает плавно
- F5 копирует содержимое блока в буфер обмена
- Команды приложения (`:q`, `:w`, `:h`) выполняются корректно
- Удаление команд работает (soft delete)
- Алиасы из ~/.bashrc раскрываются в командах

❌ **Тест не пройден, если**:
- Сообщения об ошибках не информативны
- Интерфейс зависает при выполнении команд
- База данных повреждается
- Комментарии не отображаются или обрезаются
- Команда `!!` не работает без предварительного `?*`

---

## Дополнительные проверки

### Проверка базы данных после тестирования
В отдельном терминале:
```bash
sqlite3 history_v2.db "SELECT tag, tid, command, comment FROM commands WHERE deleted = 0 ORDER BY tag, tid;"
sqlite3 history_v2.db "SELECT tag, comment FROM tags ORDER BY tag;"
```

### Проверка файлов
```bash
cat .bashrc_term
cat history.txt
cat test_output.txt
```

---

## Заметки для тестировщика

- Записывайте любые несоответствия в поведение приложения
- Проверяйте корректность работы после каждой секции
- Используйте `:w` для сохранения важных состояний
- Перезапускайте приложение между критическими тестами при необходимости
- Следите за сообщениями об ошибках в stderr

---

**Версия документа**: v1.0
**Версия приложения**: v1.1.2
**Дата создания**: 2026-01-29
**Автор**: markovskiy.pavel, Gemini (Google), Claude
