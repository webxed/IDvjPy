# IDvjPy_term на Windows: запуск через WSL

Нативно под Windows TUI стартует, но **команды не выполняются**: исполнение
в `src/app.py` рассчитано на `/bin/bash`, которого на Windows нет (плюс
`os.getpgid`/`killpg`, `signal.SIGKILL` и MSYS-пути `$PWD`). Поэтому рабочий
путь без правок кода — **WSL2**: внутри него приложение видит настоящий Linux,
bash и pty, а репозиторий остаётся на Windows-диске.

## Что нужно

- Windows 10/11 с WSL2;
- дистрибутив Linux с Python **3.12+** (проверено на Ubuntu 24.04 — 3.12.3);
- Windows Terminal (рекомендуется: в нём WSL получает нормальный pty).

## 1. Проверить WSL

В PowerShell:

```powershell
wsl -l -v          # список дистрибутивов и версия WSL
wsl --status       # версия по умолчанию
```

Если WSL нет:

```powershell
wsl --install -d Ubuntu
```

После установки — перезагрузка и первичная настройка пользователя Ubuntu.

## 2. Окружение Python

Репозиторий на Windows-диске виден из WSL как `/mnt/c/…`. Виртуальное
окружение лучше держать **в домашнем каталоге WSL**, а не на `/mnt/c`:
импорт модулей и запуск тестов заметно быстрее.

```bash
cd /mnt/c/Users/<имя>/.../IDvjPy
python3 --version                                  # нужен 3.12+
python3 -m venv ~/.venvs/idvjpy
~/.venvs/idvjpy/bin/pip install -r requirements.txt
```

Если `venv` не создаётся (`ensurepip is not available`):

```bash
sudo apt update && sudo apt install -y python3.12-venv
```

Альтернатива — штатный `./setup.sh`: он создаёт `.venv` **в репозитории**
(каталог в `.gitignore`), но на `/mnt/c` это медленнее.

## 3. Запуск

Из PowerShell откройте WSL (или профиль Ubuntu в Windows Terminal):

```powershell
wsl
```

Внутри:

```bash
cd /mnt/c/Users/<имя>/.../IDvjPy
source ~/.venvs/idvjpy/bin/activate
python3 app.py
```

Выход — `:q`. Полезные варианты:

```bash
python3 app.py --demo short                     # автотур
python3 app.py --instance-name=work             # отдельные .bashrc_term_work и history_work.txt
python3 app.py --lang ru                        # язык интерфейса
python3 app.py --data-dir "/mnt/c/Users/<имя>/idvjpy-data"
```

Прочие флаги и сценарии — в [`README.md`](../README.md) и [`DEMO.md`](../DEMO.md).

### Без ручной активации

`source ~/.venvs/idvjpy/bin/activate` — команда **оболочки**; `python3 app.py`
уже не может её выполнить за вас (и добавлять активацию внутрь `app.py` не
нужно: путь к venv у каждого свой, а сам скрипт — ещё и pip-пакет).
Активация вообще не обязательна: зависимости лежат в venv, достаточно
запустить его интерпретатор напрямую.

```bash
~/.venvs/idvjpy/bin/python app.py
~/.venvs/idvjpy/bin/python -m pytest tests/test_shell_env.py -q
```

`source …/activate` нужен только для интерактивной работы, когда вы сами
набираете `python3`, `pip` или `pytest` в терминале. Для `> cmd` активация
тоже не нужна: TTY-обёртка вызывает `sys.executable`, то есть тот же
интерпретатор venv.

Одной строкой из PowerShell (без входа в WSL):

```powershell
wsl -e bash -lc 'cd /mnt/c/Users/<имя>/.../IDvjPy && ~/.venvs/idvjpy/bin/python app.py'
```

Если хочется полной семантики активации (дочерние команды видят `python3` из
venv), но без изменения вашего интерактивного shell — функция в `~/.bashrc`:

```bash
idvjpy() {
    PATH="$HOME/.venvs/idvjpy/bin:$PATH" VIRTUAL_ENV="$HOME/.venvs/idvjpy" \
        "$HOME/.venvs/idvjpy/bin/python" /mnt/c/Users/<имя>/.../IDvjPy/app.py "$@"
}
```

Автоматический `source ~/.venvs/idvjpy/bin/activate` в `~/.bashrc` тоже
сработает, но включит venv во **всех** ваших shell-сессиях WSL — это уже
глобальная настройка окружения, а не запуск одного приложения.

## 4. Где живут данные

Два запуска (нативный Windows и WSL) по умолчанию **не видят друг друга**:

| Запуск | Каталог данных |
|--------|----------------|
| WSL (Linux) | `~/.config/idvjpy` (`/home/<имя>/.config/idvjpy`) |
| Нативный Windows | `%APPDATA%\IDvjPy` |

Чтобы WSL-сессия работала с той же библиотекой тегов и историей, что и
Windows-запуск:

```bash
IDVJPY_DATA_DIR="/mnt/c/Users/<имя>/AppData/Roaming/IDvjPy" \
    ~/.venvs/idvjpy/bin/python app.py
```

Не запускайте две сессии одновременно на одной базе: SQLite и lock-файлы
приложения между Windows- и Linux-ФС не согласованы.

### Сиды: в какую базу

Сиды берут ту же базу, что и приложение: каталог данных (`~/.config/idvjpy`)
плюс `database_tags_file` из его `settings.yml` (`data_dirs.resolve_data_dir`).
Поэтому запускать их можно прямо из репозитория — база больше не появляется
рядом с исходниками:

```bash
~/.venvs/idvjpy/bin/python /mnt/c/.../IDvjPy/src/seed_linux_commands.py --seed
# Seeded 4 tags (49 commands) into /home/<имя>/.config/idvjpy/mytags.db
```

Остальные справочники — так же:

```bash
~/.venvs/idvjpy/bin/python /mnt/c/.../IDvjPy/src/seed_git.py --seed
~/.venvs/idvjpy/bin/python /mnt/c/.../IDvjPy/src/seed_k8s_chains.py --seed
~/.venvs/idvjpy/bin/python /mnt/c/.../IDvjPy/src/seed_ops.py --seed
```

`--db` по-прежнему главнее: им можно направить сид в конкретный файл, не
трогая каталог данных. Portable-режим тоже сохранён: `settings.yml` в текущем
каталоге делает этот каталог каталогом данных.

Проверка: `??` в TUI показывает теги (`proc`, `file`, `net`, `kube`, …).
Если база общая с Windows-запуском (`IDVJPY_DATA_DIR=/mnt/c/.../AppData/Roaming/IDvjPy`),
сид идёт в тот же файл, что читает приложение, — `--db` не нужен.

## 5. Тесты

```bash
~/.venvs/idvjpy/bin/pip install -r requirements-dev.txt
~/.venvs/idvjpy/bin/python -m pytest tests/test_shell_env.py -q   # по затронутым файлам
```

В интерактивном shell после `source ~/.venvs/idvjpy/bin/activate` те же
команды короче — `pytest …`, `python3 …`.

Полный прогон `python3 -m pytest tests/ -v` идёт около 20 минут — запускайте
его осознанно (см. `AGENTS.md`).

## 6. Необязательные пакеты

- **Буфер обмена вне Textual** (`pyperclip`): `sudo apt install -y xclip`.
  Внутренний буфер Textual и OSC 52 работают и без него.
- **`:key`** (шифрованное хранилище): `~/.venvs/idvjpy/bin/pip install cryptography`
  — в `requirements.txt` его намеренно нет.
- **Инструменты сидов** ставятся внутрь WSL (Windows-версии не видны):
  `kubectl`, `helm`, `sqlite3` (`sudo apt install sqlite3`), `git` и т.п.
- **`:md` со скан-PDF**: `ocrmypdf` + tesseract и языковой пакет
  (`sudo apt install ocrmypdf tesseract-ocr-rus tesseract-ocr-eng`).
- **`:ed`**: `sudo apt install -y vim` (или `nano`).

## 7. Известные ограничения

- `/mnt/c` медленнее нативной ФС WSL: первый импорт и чтение БД заметно
  дольше. Если мешает — клонируйте репозиторий в `~/`, но это будет уже
  отдельная копия с отдельным `.git`.
- `git` из WSL может ругнуться на «dubious ownership» — лечится
  `git config --global --add safe.directory /mnt/c/.../IDvjPy`.
- **Git и проверки — на стороне Windows.** В Windows у git включён
  `core.autocrlf=true`, а в WSL он по умолчанию выключен, поэтому `git`
  из WSL видит изменённым весь репозиторий (CRLF в рабочем дереве против LF
  в индексе), а `python3 check_release.py` из WSL сообщает «trailing
  whitespace» на каждом файле. Запускайте `git` и `check_release.py` /
  `bump_version.py` через Windows-`python`, а в WSL гоняйте только `ruff`, `pytest`
  и само приложение. Разовый обход без правки конфига:
  `git -c core.autocrlf=true --no-pager diff --check`.
- Нативный запуск (`python app.py` в PowerShell) стартует, но любая команда
  падает с `[WinError 3]`. Причины — жёсткий `/bin/bash` в
  `_execute_in_thread`, `_run_in_tty`, `_launch_window`, `_capture_watch_tick`,
  отсутствующие `os.getpgid`/`killpg` и `signal.SIGKILL`, а также MSYS-путь
  `$PWD`; это отдельная задача (shell-исполнитель под Windows).

## Чек-лист

```text
[ ] wsl -l -v показывает Ubuntu и version 2
[ ] python3 --version внутри WSL — 3.12+
[ ] ~/.venvs/idvjpy/bin/pip install -r requirements.txt — без ошибок
[ ] ~/.venvs/idvjpy/bin/python app.py — TUI открылся, echo hello возвращает hello
[ ] :q — выход без висящих процессов
```
