# IDvjPy — ID Variables & Joiner on Python

<p align="center">
  <img src="idvj-all.gif" alt="IDvjPy_term: python3 app.py --demo all" width="800">
</p>

<p align="center"><em>Define your variables, join your command.</em></p>

Keyboard-driven TUI that treats **tags as command templates** and assembles them into shell lines (`!tag[tid]`, `!!`). Python **3.12+**, [Textual](https://textual.textualize.io/).

**IDvjPy_term** v1.90 — умный терминал для создания командных строк из тегов.

## Что это?

IDvjPy — терминальное приложение (TUI) на Python (Textual) с клавиатурным управлением.
Постоянная тегированная история команд хранится в SQLite.

**Философия:** теги — переменные с шаблонами команд; приложение собирает их в сложные командные строки.

Код приложения лежит в `src/`. В рабочей папке — данные: `settings.yml`, база тегов, `.bashrc_term*`. При пустой БД в журнале показывается каталог seed-справочников (Linux, [цепочки k8s](K8S_CHAINS.md), git, ops): клик по зелёной `--seed` вставляет команду во ввод, клик по `.md` открывает справочник.

Запуск: `python3 app.py` (лаунчер; код в `src/`). Тесты: `python3 -m pytest tests/ -v` (dev-зависимости: `pip install -r requirements-dev.txt`). Справка в приложении: `:?`.

## Возможности

- Персистентные теги и сборка команд (`!tag[tid]`, `!!`)
- Справочники команд (seed): Linux, [цепочки для расследования k8s](K8S_CHAINS.md), git, docker, helm, ansible, systemd, lsof/strace, sysstat, sort/jq, ip/ethtool, tcpdump/mtr/TLS, apt/rpm и другие ops
- Журнал по блокам: фокус, сворачивание, пайп `|` из сфокусированного блока
- Автодополнение путей и команд из истории/БД
- Построчный режим в выводе блока (копирование и дописывание во ввод)
- JSON viewer (F5) с черновиком `jq` и `$JSON`
- Переменные `$VAR` (файлы `.bashrc_term` / `.bashrc_term_<instance>`); `$OUT` — последняя строка блока, только в момент команды
- Секреты `$$VAR=value`: значение прячется при вводе и в журнале (`****`), хранится в `secrets_<instance>.json` (0600) — не в `.bashrc_term`/history; в командах — `$VAR`. Ключ `clear_clipboard_after_secret` очищает буфер обмена после вставки значения в `$$NAME=…`
- Остановка фоновой команды без ожидания timeout: `F4` / `:kill` (SIGTERM всей группе)
- Поиск по содержимому команд: `?kubectl wide` — если тега нет, ищет по тексту/комментариям
- Мониторинг командой: `:watch 5 kubectl get pods` — перезапуск каждые N сек в одном блоке
- Гигиена библиотеки: `:mv tag[1] tag2` (перенос команды) и `:mv tag tag2` (переименование)
- Метрики: счётчики запусков (use_count/last_used) и `:stats` — топ по запускам, теги, «never run»
- Каталог в Markdown: `:export * [file.md]` — вся библиотека по тегам с комментариями
- Сравнение выводов: `:diff` — unified diff сфокусированного блока с предыдущим
- История вывода сессии: `:o [N]`, `:o /текст`, `:o clear` — grep по прошлым выводам после `:c`
- k8s автодополнение: `kubectl get pod <Tab>` — имена из кластера (`k8s_completion: true`)
- UX: `:r N` — команда блока N назад; `:cmd [N] [show]` — команда блока с подставленными значениями (секреты включены) в буфер; счётчик `N running` в заголовке; `:alias <tag>` — команды в bash-функции
- LLM из TUI: `:llm [провайдер] сообщение` (без имени — `default:`; `$OUT`/`$BLOCK` вставляют вывод блока; `@файл` вкладывает текст файла (UTF-8, ≤200 KB; можно несколько); контекст беседы — `history_turns: N` у провайдера (`:llm reset [<провайдер>|*]`); запросы пишутся в `history_*.txt`, но не в подсказки)
- Чистая история: опечатки (`command not found`, 127) автоматически убираются из `history_*.txt`
- `:llm` язык ответа: `answer_language: Russian` у провайдера — жёсткое правило против ответов не на языке пользователя (напр. китайского)
- :llm ask: `:llm ask [<провайдер>] <задача>` — провайдеру (по умолчанию, или указанному первым словом) уходит задача **плюс** шпаргалка приложения и выжимка библиотеки тегов (тег/tid/команда/комментарий, релевантные задаче — выше, остальные — именами). Ответ приходит готовыми ссылками `!kpod[1]` / `!! kpod[1] && klog[1]`; существующие ссылки дополнительно показываются кликабельной строкой (вставка во ввод, запуск — отдельным Enter). Для обычного `:llm` тот же контекст включает ключ провайдера `app_context: true|N` (`N` — бюджет символов, по умолчанию 6000; нет ключа/false — выключено). Логика — `src/llm_context.py`
- Внешний редактор: `:ed <файл>` (правки в файле), `:ed $OUT|$BLOCK` (вывод блока), `:ed` (пустой буфер). TUI на паузе (как `> cmd`). Редактор — `editor:` в `settings.yml` (можно с аргументами: `code --wait`), иначе `$VISUAL`/`$EDITOR`, иначе системный. В пути раскрываются `$VAR`/`$OUT` (`:ed $TMPDIR/pod-$OUT.json`); однострочный результат правит ввод (запуск — Enter), многострочный остаётся файлом с показанным путём (`@файл` / `| cmd`)
- Алиасы из `~/.bashrc` (в том числе `$1` / `$2` / `$@`), фоновое выполнение команд
- `> cmd` — настоящий TTY (htop, vim, ssh); клик и PgUp/PgDn активируют видимый блок журнала
- Калькулятор без спец-команд: строка, начинающаяся с цифры (или `(` / `-`) и целиком разбираемая как арифметика/перевод единиц, считается локально — `512Mi + 20% in Gi`, `20% of 512Mi`, `2Gi/512Mi`, `500m in cores`
- ipcalc: IPv4-сети считаются так же, без спец-команд — `192.168.1.0/24`, `300 hosts` → `/23` (как jodies.de/ipcalc)
- Кластерный журнал kubectl: переменные стека (`NS POD DEPLOY SVC ING APP CTR QUOTA`) запоминаются по кластерам в `kctx.json` (data-каталог). `:kctx` — список кластеров; `:kctx <cluster>` — вход (`klogin <c> || kubectl config use-context <c>`) и ранее использованные наборы переменных; `:kctx N` возвращает набор (переменные → `.bashrc_term_*`); `:kctx <cluster> N` — вход и применение одной строкой

## Установка

Нужен Python 3.12+.

```bash
./setup.sh                 # создаёт .venv и ставит зависимости
source .venv/bin/activate
# или: pip install -r requirements.txt
# тесты: pip install -r requirements-dev.txt
```

На Linux для буфера обмена нужны `xclip` или `xsel` (на Wayland — `wl-clipboard`).

Переменные: при первом старте копируется [`src/.bashrc_term.example`](src/.bashrc_term.example) в `.bashrc_term_<instance>`. Демо: [`DEMO.md`](DEMO.md) (живой сценарий) и `python3 app.py --demo` (автонабор для записи видео).

### Установка как pip-пакета (wheel)

Собранный wheel можно поставить в любой venv и запускать командой `idvjpy` без клонирования репозитория.

```bash
# из репозитория: собрать wheel (копирует актуальный src/ во вложенный ресурс пакета)
packaging/build_wheel.sh                 # → packaging/dist/idvjpy_term-<версия>-py3-none-any.whl

# в целевом окружении:
python3 -m venv .venv && source .venv/bin/activate
pip install packaging/dist/idvjpy_term-*.whl

idvjpy                       # запуск (те же флаги, что у python3 app.py)
idvjpy --demo short          # автотур из установленного пакета
python3 -m idvjpy_boot       # то же самое через python -m
```

В wheel входят код и ресурсы (`app.css`, `demos/`, примеры конфигов, `.bashrc_term.example`); хранилища пользователя (settings/БД/history) в пакет **не** кладутся — при первом запуске они создаются в системном data-каталоге (`--data-dir` → `$IDVJPY_DATA_DIR` → системный каталог ОС, см. «Запуск»). Так один и тот же пакет можно обновлять (`pip install -U`), не трогая свои теги и историю.

Версия пакета соответствует версии приложения (`CommandRunner.VERSION` → `MAJOR.MINOR.0`).

### Установка в систему (pipx / uv / `--user`)

Чтобы `idvjpy` была всегда доступна как обычная команда, ставьте wheel изолированно — системный Python при этом не трогается.

```bash
# pipx — отдельное окружение на приложение
pipx install packaging/dist/idvjpy_term-*.whl
pipx upgrade idvjpy-term        # после сборки нового wheel
pipx uninstall idvjpy-term

# uv (>= 0.4) — то же в стиле uv; ставит бинарь в ~/.local/bin
uv tool install packaging/dist/idvjpy_term-*.whl
uv tool list                    # idvjpy-term v1.60.0 / idvjpy
uv tool upgrade idvjpy-term
uv tool uninstall idvjpy-term

# или в активный venv через uv
uv venv && uv pip install packaging/dist/idvjpy_term-*.whl

# пользовательская установка (без изоляции)
python3 -m pip install --user packaging/dist/idvjpy_term-*.whl   # ~/.local/bin/idvjpy
```

Замечания:
- На Debian/Ubuntu системный `pip install` без venv блокируется (PEP 668, `externally-managed-environment`) — используйте `pipx`/`uv` или `--user`.
- Установка прямо из git тоже работает: корневой [`pyproject.toml`](pyproject.toml) + [`setup.py`](setup.py) на этапе сборки вкладывают `src/` в пакет (то же, что `packaging/build_wheel.sh`).

```bash
# прямо из GitHub — без локальной сборки wheel
pipx install git+https://github.com/webxed/IDvjPy
uv tool install git+https://github.com/webxed/IDvjPy
```

- Куда попадают данные при первом запуске — см. «Запуск» ниже: системный каталог ОС (`~/.config/idvjpy` и аналоги), либо `--data-dir` / `$IDVJPY_DATA_DIR`. При обновлении/удалении пакета теги, история и настройки сохраняются.

## Запуск

```bash
python3 app.py [--data-dir PATH]
```

Данные (settings/БД/history): `--data-dir` → `$IDVJPY_DATA_DIR` → текущий каталог (если в нём уже есть `settings.yml`) → системный каталог (`~/.config/idvjpy`, macOS `~/Library/Application Support/IDvjPy`, Windows `%APPDATA%\IDvjPy`). При первом запуске в новом каталоге создаются `settings.yml` (копия [`src/settings.example.yml`](src/settings.example.yml)) и `llm_providers.yml` (копия примера). Личный `settings.yml` в git **не входит** — настройки не утекают в репозиторий.

```bash
python3 app.py
python3 app.py --instance-name=user1   # отдельный .bashrc_term_user1 и history_user1.txt
python3 app.py --demo                  # автотур: печатает команды сам (Esc — стоп)
python3 app.py --demo ip               # myip → jq .cc → Wiki URL → hello pipe → echo Hello, $OUT
python3 app.py --demo features         # новые команды v1.44 (см. DEMO.md)
python3 app.py --demo all              # всё подряд: calc, ipcalc, JSON, теги, :stats, :diff, :watch, :kctx (без сети)
python3 app.py --demo full --demo-quit
```

Код приложения лежит в `src/`. В корне рабочей копии — данные: `settings.yml`, база тегов, `.bashrc_term*`, `history_<instance>.txt`. Seed-справочники: `python3 src/seed_git.py --seed` и т.п. При пустой БД каталог в журнале: клик по `--seed` вставляет команду во ввод, клик по `.md` или `:md файл.md` открывает справочник (`terminal_mouse: true`).

| Путь | Назначение |
|------|------------|
| `src/` | TUI, CSS, seed-скрипты, шаблон `.bashrc_term.example` |
| `app.py` / `backup_db.py` | лаунчеры (не правят данные) |
| `settings.yml` | личные настройки — **не в git** (`.gitignore`); копия `src/settings.example.yml`, создаётся при первом запуске |
| `*.db`, `.bashrc_term*`, `history_*.txt` | теги, переменные, история — тоже вне git |

## Демостенд в Docker

Потрогать TUI, не ставя Python: маленький образ (~100 МБ, `python:3.12-alpine`) с уже
наполненной библиотекой тегов. Данные — в томе `idvjpy-demo-data` (`settings.yml`,
`mytags.db`, history), код — в образе. Что попробовать и как сбросить —
[`docker/README.md`](docker/README.md).

```bash
cd docker
docker compose run --rm idvjpy                          # собрать и запустить
docker compose run --rm idvjpy --demo short --demo-quit # автопоказ (туру нужен TTY)

docker volume rm idvjpy-demo-data                       # сброс к заводским
```

Первый запуск сам создаёт `/data/settings.yml` из шаблона и наполняет библиотеку
(`linux`, `k8s`, `git`, `ops` — 849 команд, ~5 с). Внутри образа есть `bash`, `nano`,
`git`, `curl`, `jq`, `procps`; `docker`/`kubectl` CLI намеренно не входят — теги вроде
`dck`/`kpod` это шаблоны команд, а не установленный CLI. Без compose:

```bash
docker build -f docker/Dockerfile -t idvjpy-demo .
docker run --rm -it -v idvjpy-demo-data:/data idvjpy-demo
```

CI собирает этот образ и прогоняет смоук — job `docker-demo` в
[`.github/workflows/tests.yml`](.github/workflows/tests.yml): провижининг, посев,
идемпотентность повторного запуска и рендер TUI под настоящим pty
(`docker/tui-smoke.py`).

## Система префиксов

| Префикс | Назначение | Пример |
|---------|------------|--------|
| (нет) | Выполнить shell-команду | `ls -la` |
| `> cmd` | Отдать настоящий TTY (htop, vim, ssh). После выхода — env/$PWD той же оболочки | `> htop` |
| `@ cmd` | Выполнить без `command_timeout` (долгие не-TTY задачи) | `@ terraform apply` |
| `#tag cmd` | Сохранить команду с тегом (текст как есть) | `#deploy rsync -av src/ host:` |
| `# command` | В историю, не выполнять (как `# …` в bash; пробел после `#`) | `# curl https://example.com` |
| `#tag=` / `#tag=ID=` | Комментарий к тегу / команде | `#deploy=prod rsync` |
| `#tag+` / `#tag+ID` | Подставить на редактирование | `#deploy+1` |
| `#tag-` / `#tag-tid` | Мягкое удаление | `#deploy-` / `#deploy-1` |
| `#name--` / `#name!!` | Спрятать / вернуть все теги справочника | `#ansible--` / `#ansible!!` |
| `#tag!` / `#tag!tid` | Восстановить после удаления | `#deploy!` / `#deploy!1` |
| `?` / `??` / `?tag` / `?tag[tid]` | Запрос тегов / всех / по тегу / превью; `?text` (2+ симв., не тег) — поиск по содержимому команд и комментариев | `?deploy`, `?wide` |
| `!tag[tid]` / `!N` | Вставить команду во ввод (не запускает) | `!deploy[1]` |
| `!! …` | Собрать строку во вводе | `!! deploy[1] && start[1]` |
| `:` | Команды приложения | `:q`, `:cd`, `:fm`, `:term`, `:session`, `:welcome`, `:backup`, `:screensaver`, `:r`, `:cmd`, `:kctx`, `:playbook`, `:md`, `:?` |
| `\| cmd` | Пайп stdout сфокусированного блока (в историю, как обычная команда) | `\| grep error` |
| `$OUT` | По запросу: последняя непустая строка блока (не хранится) | `echo Hello, $OUT` |
| `$VAR=val` | Локальная переменная (пишет `.bashrc_term_<instance>`) | `$EDITOR=nvim` |
| `$$VAR=val` | Секретная переменная: ввод и вывод маскируются (`****`), файл `secrets_<instance>.json` (0600) | `$$TOKEN=…` → `curl -H "Bearer $TOKEN"` |
| `$VAR=@key` / `$$VAR=@key` | Взять значение из вывода блока: строка, первый токен которой — `key` (`@last` — последняя строка) | `vault read …` → `$$VAULT_TOKEN=@token` |

### Секретные переменные (`$$VAR=value`)

Токены, пароли и ключи можно держать в TUI, не показывая их на экране:

```text
$$TOKEN=...        # задать секрет (значение прячется при вводе)
$$TOKEN            # статус: is set (value hidden) / is not set
$$TOKEN-           # удалить
curl -H "Bearer $TOKEN" https://api.example   # обычная подстановка $TOKEN
```

- **Ввод.** С первого символа значения строка ввода маскируется; имя секрета — в подзаголовке (`Secret $TOKEN: value hidden`).
- **Хранение (только сессия).** `secrets_<instance>.json` (права `0600`) создаётся при задании и **удаляется при выходе** из приложения — значения не переживают перезапуск. В `.bashrc_term`, `history_*.txt` и playbook-лог не пишется; уже существующий файл подхватывается при старте, по `:env` и `:session`.
- **Вывод.** В журнале значение — `****`: шапка блока, показываемые stdout/stderr, `:o` и строка `TTY: …`. При этом `raw_stdout` настоящий — `|`, `$OUT` и `F3` работают с реальными данными.
- **LLM.** Секреты не уходят в `:llm`: значения в сообщении (в т.ч. попавшие туда через `$OUT` / `$BLOCK` / `@файл`) заменяются на `****` перед отправкой, в шапке блока — `secrets: hidden`.
- **Захват из вывода.** `$VAR=@key` / `$$VAR=@key` берёт значение из сфокусированного (или последнего) завершённого блока: строка, первый токен которой равен `key` — удобно для таблиц `vault read` / `vault write` (`Key  Value`); `@last` — последняя непустая строка (например, после `| jq -r .field`). Пример — плейбук `vapprole` ([`docs/SEED_VAULT_COMMANDS.md`](docs/SEED_VAULT_COMMANDS.md)).
- **Буфер обмена при вставке секрета.** `clear_clipboard_after_secret: true` в `settings.yml` — после вставки значения в строку `$$NAME=…` CLIPBOARD/PRIMARY/внутренний буфер очищаются (по умолчанию `false`; обычная вставка буфер не трогает; некоторые clipboard-менеджеры могут сохранить историю).

Ограничения: маскируется вся строка ввода (имя тоже — оно видно в подзаголовке); в интерактивном `> cmd` реальный терминал показывает значение, пока TUI на паузе; если команда сама печатает секрет, в журнале — `****`, но `F3` отдаст настоящий вывод; строка, начинающаяся с `$$`, всегда трактуется как секрет.

**Калькулятор (без префикса):** строка, начинающаяся с цифры (или `(` / `-`) и целиком разбираемая как арифметика или перевод единиц, считается локально — shell не запускается, результат появляется блоком с заголовком `calc:`. Остальные строки (`7z …`, `(cd … && …)`, `-la`, `2>/dev/null …`) по-прежнему уходят в shell — в них есть слова, которые не разбираются как арифметика. Полная справка в TUI: `:? calc`.

- Арифметика: `+ - * / ^ ( )` — `1024*3`, `(2+3)*4`, `2^10`, `-5 + 8`
- Проценты: `512Mi + 20% in Gi` (увеличить на 20%), `512Mi - 15%`, `512Mi * 20%` (доля), `2 + 10%`
- `of` — доля от значения: `20% of 512Mi` → `102.4Mi`, `1/3 of 1Gi`, `20% of (512Mi + 1Gi)`; как умножение (`512Mi * 20%`)
- Память: `B`; `K/M/G/T` = `KB/MB/GB/TB` (×1000); `Ki/Mi/Gi/Ti` = `KiB/MiB/GiB/TiB` (×1024); k8s-стиль слитно: `512Mi`, `1.5 Gi`
- CPU: `m` — миллиядро, `cores`; `500m in cores` → `0.5 cores`, `0.5 in m` → `500m`
- `1Gi/512Mi` → `2` (сколько раз влезает); `524288 in Mi` → `0.5Mi`; сумма ресурсов: `512Mi + 1Gi + 256Mi in Mi`
- IP-подсети (как jodies.de/ipcalc): `192.168.1.0/24`, `10.1.2.3/255.255.255.0`, голый `8.8.8.8` (классовая маска по умолчанию) — адрес, маска (=N), wildcard, сеть/префикс, диапазон хостов, broadcast, число хостов, класс/RFC1918 и бинарный вид; обратная задача — `300 hosts` → `/23` (минимальный префикс под N хостов)

`#name--` прячет все теги справочника (`linux`, `k8s`, `git` и ops: `ansible`, `helm`, …). `#name!!` возвращает. В `??` / `?` спрятанные теги видны в блоке Hidden; в `!`-автоподсказках и completion по тексту команды их нет. `#tag-` по-прежнему прячет один тег.

`!` и `!!` подставляют текст во ввод. Запуск — отдельным Enter. В `??` клик по тегу вставляет `!tag ` / `!tag[tid] ` **в позицию курсора** (строку не затирает; можно кликать несколько тегов подряд). Нужен `terminal_mouse: true`.

Алиасы с `$1` / `$2` / `$@` подставляют аргументы (`alias klogin="tsh kube login $1"` → `klogin cluster` становится `tsh kube login cluster`). Без `$n` остаток строки по-прежнему дописывается к телу алиаса.

### Команды приложения (`:`)

- `:q` — выход
- `:w file` — записать вывод в файл
- `:h [N]` — последние N строк `history_<instance>.txt` одним блоком (по умолчанию из `settings.yml`; строки можно брать построчным режимом)
- `:h /text` — поиск по этому файлу в подсказках (без учёта регистра, свежие сверху, одинаковые строки один раз). Esc+Enter — тем же поиском в журнал
- `:h compact` — ужать старую историю (уникальные строки); последние `history_keep` строк не трогает. На старте — только если файл длиннее `2 × history_keep`
- `:c` — очистить блоки журнала
- `:json` / `:json <file>` — JSON viewer (последний блок или файл)
- `:md <file.md>` — справочник Markdown с форматированием (клик по имени в приветствии; Esc закрывает)
- `:llm [<провайдер>] <сообщение>` — запрос к LLM по `llm_providers.yml` (секреты только из окружения: `$DEEPSEEK_API_KEY`). `@файл` вкладывает текст, `$OUT` / `$BLOCK` — вывод блока, `history_turns: N` держит контекст беседы
- `:llm offline <сообщение>` / `:llm ask offline <задача>` — встроенный офлайн-провайдер (`mock: true`): отвечает без сети и ключей; есть в любом конфиге, пока не переопределён своим `offline:` (демо, проверка проводки)
- `:llm ask [<провайдер>] <задача>` — к задаче добавляется шпаргалка приложения и выжимка библиотеки тегов; ответ — готовые ссылки `!tag[tid]` (кликабельные, только существующие). Ключ `app_context` в провайдере включает то же для обычного `:llm`
- `:llm reset [<провайдер>|*]` — очистить контекст беседы (память сессии)
- `:ed [<файл>|$OUT|$BLOCK]` — внешний редактор (`editor:` в `settings.yml`, иначе `$VISUAL`/`$EDITOR`); TUI на паузе. В пути раскрываются `$VAR`/`$OUT` (`:ed $TMPDIR/pod-$OUT.json`); однострочный результат правит ввод, многострочный остаётся файлом
- `:o [N]` — последние N выводов сессии (по умолчанию 5); `:o /text` — grep по ним (переживает `:c`); `:o clear` — забыть
- `:stats` — сводка библиотеки: запуски по тегам, топ-10, «never run»
- `:mv <tag>[<tid>] <dst>` — перенести команду в другой тег; `:mv <tag> <dst>` — переименовать тег (комментарий едет)
- `:diff` — unified diff stdout сфокусированного блока с предыдущим
- `:kill [all]` — остановить запущенную команду; `:watch <сек> <команда>` — повторять её в одном блоке (`:watch stop`)
- `:alias <tag> [file.sh]` / `:alias * [library.sh]` — выгрузить команды bash-функциями `tag_tid()`
- `:i …` — Kubernetes Ingress Analyzer (`:i` без аргументов — справка)
- `:cd [path]` — показать / сменить cwd для shell-команд (то же делает `cd path`). База тегов, история и `.bashrc_term*` остаются в каталоге запуска; пустой `mytags.db` в новой папке не создаётся.
- `:fm [path]` — проводник ОС в новом окне (cwd или путь). Linux: `xdg-open`; macOS: `open`; Windows: `explorer`. Свой: `$FILEMAN`
- `:term [path]` — системный терминал в новом окне. Linux: `xdg-terminal-exec` / `gnome-terminal` / …; macOS: Terminal.app; Windows: `wt` или `cmd`. Свой: `$TERMINAL`
- `:env` — перечитать `.bashrc_term*` (и алиасы `~/.bashrc`) в уже запущенном приложении. После `> cmd` экспорты **того же** bash подхватываются сами (вложенный `> bash` + `export` внутри — нет)
- `:session` — текущий инстанс (история + `.bashrc_term_*`). `:session NAME` — переключить или создать (БД тегов общая)
- `:welcome` — каталог seed, как при пустой БД (клик `--seed` / `.md`). На старте при непустой БД — блок **Разделы** с живыми тегами по handbook (`linux`, `k8s`, `git`, ops, `свои`)
- `:backup` — снимок SQLite в `backups/` (как перед `--seed`). Пустую базу не копирует. Вернуть: скопировать файл поверх рабочей БД.
- `:screensaver` — DevOps starfield сразу. Простой как в Norton Commander: звёзды летят на зрителя; ближе — `k8s` / `git` / `!!`. Вместе с ними летают живые часы (`15:35:42`) и дата (`2026-08-26`). Сверху ярко-зелёная лента на всю ширину с командами из БД (`!tag[tid]  cmd`). Снизу слева — справка команд (печать слева направо, отступ от края как раньше); снизу справа — load 1/5/15 и RAM (раз в секунду из `/proc`), с таким же отступом от правого угла; в узком окне load может наехать на справку. Спрятанные справочники (`#name--`) не показываются. Любая клавиша или клик закрывает (в ввод не попадает). Таймаут: `screensaver_idle` в `settings.yml` (секунды, `0` = выкл). `:screensaver 0` / `:screensaver 120` — на эту сессию. `screensaver_stars: false` — без летающей пыли/токенов (часы, лента и load остаются).
- `:r` — команда сфокусированного блока во ввод; `:r N` — N блоков назад (0 = последний)
- `:cmd [N] [show]` — материализовать команду блока с текущими значениями `$VAR` (включая секреты) → в буфер обмена; `show` ещё и печатает (секреты становятся видны)
- `:/text` / `:g` / `:n` / `:N` — поиск по строкам журнала (с блока `/` открывает `:/`; `n`/`N` — следующее / предыдущее)
- `:export tag [file]` / `:import file` — один тег в JSON и обратно
- `:playbook [file.yml]` — записать команды этой сессии (Enter) как YAML для `--demo` (по умолчанию `playbook.yml`). `:playbook -` — превью в журнале; `:playbook clear` — забыть записанное. Клавиши (Tab/F5) и мышь не пишутся. В YAML: `loop: true` / `loop: N` — крутить шаги (Esc — стоп); см. [DEMO.md](DEMO.md).
- `:update` — сверить `VERSION` с GitHub [`webxed/IDvjPy`](https://github.com/webxed/IDvjPy) `main`. При старте то же самое, если `check_updates: true` (пишет в журнал только если на GitHub новее). Прокси с логином: `$PROXY_USER` / `$PROXY_PASS` в `.bashrc_term` (плюс `HTTPS_PROXY` / `HTTP_PROXY`).
- `:theme [name]` — тема TUI (`dark` / `light` / `nord` / …); пишется в `settings.yml`. Клавиша `d` — dark/light
- `:kctx` — кластерный журнал (`kctx.json`): список кластеров; `:kctx <cluster>` — вход (`klogin <c>` или `kubectl config use-context <c>`) и ранее использованные наборы `NS`/`POD`/…; `:kctx N` — применить набор N; `:kctx <cluster> N` — вход и применение одной строкой
- `:?` — эта справка внутри TUI

## Горячие клавиши

| Клавиша | Действие |
|---------|----------|
| `Tab` | Из ввода — на последний блок журнала (`:h`, `:?`, команда); если открыт список подсказок — применить кандидата |
| `Esc` | Фокус на ввод. В построчном режиме: сначала выключить режим, повторный Esc — во ввод |
| `↑` / `↓` | `history_<instance>.txt` (+ сессия) во вводе; набранный текст фильтрует совпадения; прокрутка журнала, если фокус на блоке |
| `PgUp` / `PgDn` | Прокрутка журнала на страницу; активным становится **видимый** блок (без прыжка к его началу). Из ввода — переход в просмотр |
| клик по блоку | Фокус на блоке без прокрутки к началу (`terminal_mouse: true`). В пустой БД: клик по `--seed` — во ввод; по `.md` — справочник. В `??`: клик по тегу вставляет `!tag ` в позицию курсора (не затирает строку) |
| протянуть мышью по журналу | Выделение текста внутри приложения; отпустили кнопку — выделенное сразу в буфере (CLIPBOARD/PRIMARY/OSC 52). `Shift`+протяжка — нативное выделение терминала (если предпочитаете его) |
| `Space` / `←` `→` | Свернуть / развернуть блок |
| `F3` | Копировать полный stdout блока |
| `Ctrl+C` | Если есть выделение мышью — копирует его; иначе всю строку ввода / весь блок журнала (как F3) |
| `F5` | JSON viewer для сфокусированного (или последнего) блока |
| `F6` | Простой вывод (без Rich-тегов, удобнее выделять мышью) |
| `F2` | Построчный режим в блоке |
| `Shift+Insert` / `Ctrl+V` | Вставка во ввод (не затирает уже набранное). В построчном режиме `Ctrl+V` дописывает текущую строку |
| `Ctrl+D` | Очистить всю строку ввода |
| `Ctrl+W` / `Ctrl+Backspace` | Во вводе: удалить слово слева от курсора (удобно подчищать вставленный вывод, напр. из `kubectl`). `Ctrl+Backspace` срабатывает там, где терминал шлёт его отдельной клавишей; универсально — `Ctrl+W` |
| `Ctrl+F` / `Ctrl+Delete` | Во вводе: удалить слово справа от курсора |
| `Ctrl+←` / `Ctrl+→` | Во вводе: курсор на слово влево / вправо |
| `Ctrl+Z` | Во вводе: отменить последнее изменение (печать / удаление / word-delete / вставку). Стек сбрасывается после отправки команды и по `Ctrl+D` |
| `d` | Тёмная / светлая тема (`textual-dark` / `textual-light`), сохраняется в `settings.yml`. Когда фокус во вводе, `d` печатается как буква; тема: фокус на журнале или `:theme` |

### Построчный режим (блок в фокусе)

По умолчанию выключен. Включить: `Tab`/`PgUp` на блок, затем `Enter` или `F2`.

| Клавиша | Действие |
|---------|----------|
| `↑` / `↓` | Строка вверх / вниз (на краю блока — снова скролл журнала) |
| `Home` / `End` | Первая / последняя строка |
| `Enter` | Скопировать строку (без конечных пробелов) и перейти во ввод, курсор в конец |
| `Shift+Enter` / `Ctrl+V` | Дописать строку во ввод через пробел, остаться в блоке |
| `Esc` / `F2` | Выключить режим |
| `/` | Начать поиск (`:/` во вводе) |
| `n` / `N` | Следующее / предыдущее совпадение |

Если `Shift+Enter` срабатывает как обычный Enter, терминал не отличает клавиши — используйте **Ctrl+V**. Пока фокус во вводе, `Ctrl+V` по-прежнему вставляет из буфера.

### JSON viewer

- `Enter` на узле: закрыть viewer, выставить `$JSON`, буфер обмена, черновик во вводе: `\| jq '.path'` (из блока) или `jq '.path'` (из файла).
- Пример: `jq $JSON test.json`.
- Поиск: `/` или поле вверху; `n` / `N` — следующее / предыдущее совпадение.

## Автодополнение

- Пути: `./` `../` `/` `~`, токен с `/`, `cd`/`pushd`, или аргумент не-флаг после команды.
- **Tab** для пути заменяет только текущий токен; полная команда из истории/БД — всю строку.
- Каталог с `/` (`ls ~/`) — первый кандидат сам каталог; Enter выполняет его, Tab не форсирует дочерний путь.
- Точное совпадение всей строки скрывает список, Enter выполняет команду.
- **Пробел в конце** (`ls` + пробел): список закрывается, Enter запускает набранное, а не более длинного кандидата (`ls -la`). Чтобы взять кандидата — Tab без завершающего пробела.
- **`!file` / `!kube`**: сразу по `!` список тегов (`[file, kube, log]`). Tab выбирает тег, затем команды: `<139> file[1]  ls -la`, во ввод — `!file[1]`. Сборка `#file !file[1] | !file[2]` с расшифровкой сверху списка.

## Конфигурация

Шаблон — [`src/settings.example.yml`](src/settings.example.yml) (он же копируется как `settings.yml` при первом запуске в новом data-каталоге; личный `settings.yml` в git не попадает):

```yaml
max_lines: 100000
history_lines: 20
history_keep: 500            # хвост истории как лента; старше — без повторов. 0 = не сжимать. :h compact
database_tags_file: mytags.db
backup_dir: backups          # снимки БД (:backup, --seed)
command_timeout: 10          # 0 = без таймаута
terminal_mouse: true         # true — мышь у приложения (клик/колесо; протяжка выделяет и копирует в буфер); false — выделение средствами терминала
theme: textual-dark          # `d` / `:theme`; сохраняется при смене
check_updates: true          # старт: сверка VERSION с GitHub main; :update всегда
screensaver_idle: 120        # простой → starfield; 0 = выкл. :screensaver — сразу
screensaver_stars: true      # летающие звёзды; false — чёрный холст (часы/лента/load остаются)
k8s_completion: false        # имена k8s-ресурсов из кластера в подсказках (`kubectl get pod <Tab>`)
clear_clipboard_after_secret: false  # вставка значения в `$$NAME=…` очищает CLIPBOARD/PRIMARY
editor: nano                 # `:ed`; можно с аргументами (code --wait); пусто → $VISUAL/$EDITOR
```

Переменные читаются из `.bashrc_term_<instance>` (приоритет) и `.bashrc_term` (дополняет). Формат: `export VAR=val` или `VAR=val`. Если файлов нет, при старте копируется [`src/.bashrc_term.example`](src/.bashrc_term.example). В работающем приложении: `:env` или правка файла из `> vim .bashrc_term_default` (после выхода TTY перечитает файлы и снимет `export` той же оболочки). В `.bashrc_term` TTY-экспорты сами не пишутся — для этого `$VAR=val`.

Файл БД (`database_tags_file`, по умолчанию `mytags.db`) **не входит в git**. При первом запуске создаётся пустая SQLite-схема; в журнале каталог seed-скриптов (сверху, без прыжка вниз). Клик по зелёной `--seed` вставляет команду во ввод; Enter запускает; затем `??` (или ~5 с). Клик по имени `.md` или `:md файл.md` открывает справочник с форматированием (Esc закрывает). Нужен `terminal_mouse: true`.

## Архитектура

- **`CommandRunner`** — приложение Textual
- **`JournalScroll`** — журнал: скролл клавишами активирует видимый блок
- **`CommandBlock`** / **`InfoBlock`** / **`QueryResultsBlock`** — блоки журнала
- **`LineNavigable`** — построчный курсор в блоке

Модули в [`src/`](src/): [`app.py`](src/app.py), [`database_v2.py`](src/database_v2.py), [`command_parser_v2.py`](src/command_parser_v2.py), [`json_viewer.py`](src/json_viewer.py), [`md_viewer.py`](src/md_viewer.py), [`screensaver.py`](src/screensaver.py), [`seed_catalog.py`](src/seed_catalog.py), [`ingress_analyzer.py`](src/ingress_analyzer.py), [`app.css`](src/app.css). Корневой [`app.py`](app.py) только запускает TUI.

Подробности сессии и поведения: [`COMPACT_SUMMARY.md`](COMPACT_SUMMARY.md). Как читается БД: [`DATABASE.md`](DATABASE.md).

## Тесты

```bash
python3 -m pytest tests/ -v
```

## Справочники команд

Каждый сид перезаписывает **только свои** теги. Если в БД уже есть команды, перед заменой пишется снимок SQLite в `backups/` (`mytags-pre-git-YYYYMMDD-HHMMSS.db` и т.п.; каталог — `backup_dir` в `settings.yml`). То же вручную: `:backup` → `mytags-manual-….db`. Пустую базу не копирует. `seed_ops.py` делает **один** снимок на все модули. Вернуть: скопировать файл поверх `mytags.db`.

Цепочки для расследования k8s: [`K8S_CHAINS.md`](K8S_CHAINS.md). `python3 src/seed_k8s_chains.py --seed` (не трогает `proc` / `file` / `net` / `kube`).

| Скрипт | Документация | Теги |
|--------|--------------|------|
| `python3 src/seed_linux_commands.py --seed` | [`SEED_LINUX_COMMANDS.md`](docs/SEED_LINUX_COMMANDS.md) | `proc` `file` `net` `kube` |
| `python3 src/seed_k8s_chains.py --seed` | [`K8S_CHAINS.md`](K8S_CHAINS.md) | `kpod` `klog` `kquota` … |
| `python3 src/seed_git.py --seed` | [`SEED_GIT_COMMANDS.md`](docs/SEED_GIT_COMMANDS.md) | `git` `gstat` `gsync` … |
| `python3 src/seed_ops.py --seed` | все ops ниже | docker + helm + ansible + http + netfw + ip + netdbg + data + host + disk + systemd + sysinfo + sysstat + vault + text + pipe + rsync + find + recon + ssh + pkg + user |
| `python3 src/seed_docker.py --seed` | [`SEED_DOCKER_COMMANDS.md`](docs/SEED_DOCKER_COMMANDS.md) | `dck` `dcmp` `dps` `dlog` |
| `python3 src/seed_helm.py --seed` | [`SEED_HELM_COMMANDS.md`](docs/SEED_HELM_COMMANDS.md) | `helm` `hls` |
| `python3 src/seed_ansible.py --seed` | [`SEED_ANSIBLE_COMMANDS.md`](docs/SEED_ANSIBLE_COMMANDS.md) | `ansible` `aplay` `avault` `agalaxy` `achk` `aping` |
| `python3 src/seed_http.py --seed` | [`SEED_HTTP_COMMANDS.md`](docs/SEED_HTTP_COMMANDS.md) | `curl` `ngx` `trf` |
| `python3 src/seed_netfw.py --seed` | [`SEED_NETFW_COMMANDS.md`](docs/SEED_NETFW_COMMANDS.md) | `ss` `nst` `ipt` `nft` `fwd` |
| `python3 src/seed_ip.py --seed` | [`SEED_IP_COMMANDS.md`](docs/SEED_IP_COMMANDS.md) | `ip` `eth` `ilink` `iiface` |
| `python3 src/seed_netdbg.py --seed` | [`SEED_NETDBG_COMMANDS.md`](docs/SEED_NETDBG_COMMANDS.md) | `pcap` `ncat` `hops` `tls` `npath` `tlschk` |
| `python3 src/seed_data.py --seed` | [`SEED_DATA_COMMANDS.md`](docs/SEED_DATA_COMMANDS.md) | `pg` `kf` |
| `python3 src/seed_host.py --seed` | [`SEED_HOST_COMMANDS.md`](docs/SEED_HOST_COMMANDS.md) | `tar` `gz` `zip` `tstat` `zstat` |
| `python3 src/seed_disk.py --seed` | [`SEED_DISK_COMMANDS.md`](docs/SEED_DISK_COMMANDS.md) | `df` `du` `mount` `fdisk` `lsblk` `smart` `ncdu` |
| `python3 src/seed_systemd.py --seed` | [`SEED_SYSTEMD_COMMANDS.md`](docs/SEED_SYSTEMD_COMMANDS.md) | `sctl` `jctl` `dmesg` `sstat` `sfail` `kmsg` |
| `python3 src/seed_sysinfo.py --seed` | [`SEED_SYSINFO_COMMANDS.md`](docs/SEED_SYSINFO_COMMANDS.md) | `hinfo` `lsof` `strace` `hstat` `lport` `pdbg` |
| `python3 src/seed_sysstat.py --seed` | [`SEED_SYSSTAT_COMMANDS.md`](docs/SEED_SYSSTAT_COMMANDS.md) | `vmstat` `iostat` `mpstat` `oload` |
| `python3 src/seed_vault.py --seed` | [`SEED_VAULT_COMMANDS.md`](docs/SEED_VAULT_COMMANDS.md) | `vault` `vstat` `vkv` |
| `python3 src/seed_text.py --seed` | [`SEED_TEXT_COMMANDS.md`](docs/SEED_TEXT_COMMANDS.md) | `grep` `awk` `sed` |
| `python3 src/seed_pipe.py --seed` | [`SEED_PIPE_COMMANDS.md`](docs/SEED_PIPE_COMMANDS.md) | `sort` `uniq` `cut` `tr` `wc` `xargs` `tee` `jq` |
| `python3 src/seed_rsync.py --seed` | [`SEED_RSYNC_COMMANDS.md`](docs/SEED_RSYNC_COMMANDS.md) | `rsync` `rchk` |
| `python3 src/seed_find.py --seed` | [`SEED_FIND_COMMANDS.md`](docs/SEED_FIND_COMMANDS.md) | `find` `fchk` |
| `python3 src/seed_recon.py --seed` | [`SEED_RECON_COMMANDS.md`](docs/SEED_RECON_COMMANDS.md) | `dig` `nmap` |
| `python3 src/seed_ssh.py --seed` | [`SEED_SSH_COMMANDS.md`](docs/SEED_SSH_COMMANDS.md) | `ssh` `scp` `schk` `ossh` `ocert` |
| `python3 src/seed_pkg.py --seed` | [`SEED_PKG_COMMANDS.md`](docs/SEED_PKG_COMMANDS.md) | `apt` `dnf` `rpm` `aptq` `rpmq` |
| `python3 src/seed_user.py --seed` | [`SEED_USER_COMMANDS.md`](docs/SEED_USER_COMMANDS.md) | `ident` `perm` `uidchk` |

`seed_ops.py` не трогает linux / k8s / git. `seed_http` / `seed_netfw` / `seed_ip` / `seed_netdbg` / `seed_rsync` / `seed_recon` / `seed_ssh` не затирают linux-тег `net`. `seed_text` / `seed_pipe` / `seed_find` / `seed_disk` не затирают `file`. `seed_host` не затирает `smart` / `df`. `seed_systemd` / `seed_sysinfo` / `seed_sysstat` не затирают `proc` / `logs`.

## Зависимости

- `textual==7.3.0`, `rich==14.3.0`, `pyperclip==1.11.0`, `PyYAML==6.0.3`, `Pygments==2.19.2`, `portalocker`

## Лицензия

[MIT](LICENSE). Авторы: markovskiy.pavel & Gemini, GLM, CLAUDE, DeepSeek, Grok.
