# Сценарий демонстрации IDvjPy_term

Версия приложения: **v1.102**. Длительность живого рассказа: **12–15 минут**.

Тезис для зрителя: теги — переменные с шаблонами команд; приложение собирает их в строку. `!` / `!!` только подставляют текст во ввод, запуск — отдельным Enter.

Kubernetes не обязателен: `:i` — опциональный бис в конце.

## Автотур: как запустить

TUI сам печатает команды из YAML. Рядом можно поставить OBS или asciinema и не набирать руками.

Запуск из каталога с `app.py` (или с абсолютным путём к лаунчеру; данные — `settings.yml`, БД, history — берутся из **текущего** каталога):

```bash
python3 app.py --demo                     # bundled short, ~2–3 мин
python3 app.py --demo full                # bundled full, без htop / kubectl / :q
python3 app.py --demo ip                  # myip → jq .cc → Wiki URL → hello pipe → echo Hello, $OUT
python3 app.py --demo features            # новые команды v1.44: ?text, :mv, :stats, F4, :watch, :diff, :o, :export *, :alias
python3 app.py --demo all                 # всё подряд: calc/ipcalc/JSON/теги/утилиты (без сети и кластера)
python3 app.py --demo --demo-speed 1.5    # быстрее (2 = вдвое)
python3 app.py --demo full --demo-quit    # выйти, когда сценарий закончится
python3 app.py --demo path/to/tour.yml    # свой файл
```

| Флаг | Что делает |
|---|---|
| `--demo` | Имя bundled-тура (`short` по умолчанию, ещё `full`, `ip`, `features`, `all`) или путь к `.yml` |
| `--demo-speed N` | Множитель скорости: паузы и набор делятся на N (`1` = как в YAML) |
| `--demo-quit` | После последнего шага приложение закрывается (удобно для asciinema) |
| `--instance-name=…` | Как обычно: отдельные `.bashrc_term_*` и `history_*.txt` (БД тегов общая) |

Bundled-сценарии: `src/demos/short.yml`, `src/demos/full.yml`, `src/demos/ip.yml`, `src/demos/features.yml`, `src/demos/all.yml`.

Во время тура в subtitle: `DEMO · … · Esc stops`. **Esc** останавливает проигрывание, сессия остаётся — можно продолжить руками. `:q` выходит из приложения.

`short` пишет в текущую БД теги `tour` / `tourlog` / `tourpipe`; `full` — `check` / `logs` / `restart` / `pipeline`. Для записи без рабочих тегов запускайте из пустого каталога:

```bash
mkdir -p /tmp/idvj-demo && cd /tmp/idvj-demo
python3 /path/to/Idivjopy/app.py --demo --demo-quit
```

## Запись гифки (asciinema → agg)

Как пересобрать README-гиф `idvj-all.gif` или записать свой тур.

Установка (один раз): `sudo apt install asciinema` (или `python3 -m pip install --user asciinema`) и `cargo install --locked agg` (либо готовый бинарник/`.deb` из [asciinema/agg](https://github.com/asciinema/agg/releases)).

Запись — из **нейтрального каталога** (`/tmp/…`): шапки блоков печатают `cwd`, иначе в кадры попадёт личный путь. Туры работают в portable-режиме: рядом кладём `settings.yml` (маркер) и `llm_providers.yml`, поэтому рабочая БД тегов и история не затрагиваются.

```bash
# 0. Изолированный data-каталог (из корня репозитория)
mkdir -p /tmp/idvj-demo
cp src/settings.example.yml      /tmp/idvj-demo/settings.yml
cp src/llm_providers.example.yml /tmp/idvj-demo/llm_providers.yml

# 1. Запись: env -C меняет cwd процесса (без cd) — в кадре будет /tmp/idvj-demo
asciinema rec -q --overwrite --cols 120 --rows 34 \
  -t "IDvjPy_term --demo all" \
  -c "env -C /tmp/idvj-demo python3 $PWD/app.py --demo all --demo-speed 2 --demo-quit" \
  /tmp/idvj-demo/idvj-all.cast

# 2. GIF
agg --theme nord --font-size 14 --line-height 1.25 \
    --speed 1.3 --idle-time-limit 0.8 --fps-cap 12 \
    /tmp/idvj-demo/idvj-all.cast idvj-all.gif
```

- `--demo-speed N` ускоряет сам тур; `agg --speed N` — уже записанное. `--idle-time-limit` срезает паузы, `--fps-cap` / `--font-size` / `--line-height` / `--cols` / `--rows` уменьшают размер GIF (`agg -h` — все ключи, `--theme` — темы).
- Проверка, что личное не утекло: `grep -c "$HOME" idvj-all.cast` → `0`.
- Без `--demo-quit` после тура останется живая сессия (Esc останавливает проигрывание).
- Уже запущенное приложение можно записать вручную: `asciinema rec out.cast` (играете сами; `exit`/`:q` завершает).

## Тур features (новое в v1.44)

```bash
python3 app.py --demo features --demo-quit
```

Короткий автотур по командам v1.35–v1.44 (без сети и кластера):

`?text` — поиск по содержимому команд; `:mv tag[1] tag2` и переименование тега; `:stats` (счётчики запусков растут после повторов); `F4` останавливает `@ sleep 60` (SIGTERM группе); `:watch 1 …` тикает в одном блоке и останавливается `:watch stop`; `:diff` сравнивает два вывода; `:r 1` возвращает команду блока назад; `:o /text` находит вывод даже после `:c`; `:export * library.md` и `:alias mine run.sh` пишут файлы в текущий каталог.

Сбрасываемые перед повтором теги: `deploy` / `kube` / `mine` (и все, что `#`-сохранены в YAML). Файлы `library.md` / `run.sh` создаются в каталоге запуска — для чистой записи используйте пустой каталог, как выше.

Автотест-гвард: `tests/test_demo.py::test_bundled_features_tour_guards`.

## Тур all («всё подряд»)

```bash
python3 app.py --demo all --demo-quit
```

Самый полный автотур: один прогон по максимуму возможностей, **без сети и кластера** (годится для asciinema и CI). Порядок — пять актов:

- **A. Локальный счёт.** `:?`; калькулятор `1024*3`, `512Mi + 20% in Gi`, `20% of 512Mi`; `ipcalc` `192.168.1.0/24`, `300 hosts`, `8.8.8.8`. Блоки помечены `calc:`, shell не запускается.
- **B. Журнал.** `seq 1 12` → `| grep 7`; JSON `Tab → F5` (дерево, `↓`, `Enter` → `$JSON` и черновик `| jq`), явный `| jq '.pods[0].status'`, `:o /CrashLoop`.
- **C. Теги.** `#api`, `?chain[1]`, `??`, `!api[1]` + Enter, `!! api[1] && logs[1]`, `#api+1` (правка → второй Enter), `#api=2=…`, `#api-1` → `?api` → `#api!1`, `:mv tmp[1] logs`, `:stats`, `:export * library.md`, `:alias api run.sh`.
- **D. Обвязка.** `$HOST=localhost` + `echo ping $HOST`, `:env`, `:h 8`, `:c` и `:o /CrashLoop` (память выводов переживает очистку), `:diff` двух `printf`, `:r 1`, `:watch 1 date +%s` / `:watch stop`, `@ sleep 60` + F4, `:backup`, `:kctx`, `:screensaver 120` / `:screensaver 0`, `#`-комментарий в историю.
- **E. LLM.** `:llm` (список провайдеров), `:llm offline <сообщение>` и `:llm ask offline <задача>` — через встроенную офлайн-заглушку `offline` (`mock: true`): ответ без ключа и сети, в шапке `ask`-блока видно `app-ctx: N tags`. Настоящие провайдеры (`ds`, `openai`, `ollama`, …) — так же, по `llm_providers.yml`.

Тур создаёт в каталоге запуска файлы `library.md` / `run.sh` и теги `api` / `logs` / `chain` / `tmp` (перед повтором сбрасываются только они; handbook-теги не трогаются). Для акта E нужен любой валидный `llm_providers.yml` (как и для любого `:llm`) — обычно он создаётся сам; в пустом каталоге скопируйте пример. Для чистой записи:

```bash
mkdir -p /tmp/idvj-all && cd /tmp/idvj-all
cp /path/to/Idivjopy/src/llm_providers.example.yml llm_providers.yml
python3 /path/to/Idivjopy/app.py --demo all --demo-quit
```

Автотесты: `tests/test_demo.py::test_bundled_all_tour_guards`, `::test_bundled_all_plays`.

## Свой YAML

```yaml
title: my tour
start_pause: 1.4     # после сплэша, секунды
type_delay: 0.14     # пауза между буквами (~7 знаков/с). Длинные строки печатаются быстрее. Шаг может задать своё `type_delay`. Для `\n` в выводе: `echo -e "...\\n..."`
pause: 0.8           # пауза после каждого шага (шаг может переопределить)
command_timeout: 12  # ждать stdout блока, если wait_command: true
# quit: true         # то же, что --demo-quit
steps:
  - ":?"                                 # строка = набрать и Enter
  - type: "echo hello"
    wait_command: true                   # ждать *новый* блок в журнале (пайп `| jq` не путать с прошлым curl)
    caption: Журнал                      # текст в subtitle
  - keys: [tab, f2]                      # горячие клавиши (не набор)
  - paste: true                          # вставить буфер во ввод (после F2 Enter)
  - type: "!"
    enter: false                         # оставить текст / список подсказок
    pause: 1.2
  - type: "check[1]"
    clear: false                         # дописать к уже набранному
    enter: true
```

Повтор шагов (мониторинг). **Esc** останавливает, в том числе бесконечный цикл. `--demo-quit` сработает только когда конечный `loop: N` закончится.

```yaml
title: poll health
loop: true                 # или loop: 20 — столько кругов, 0/forever = бесконечно
pause: 0
command_timeout: 12
steps:
  - type: "curl -sS http://127.0.0.1:8080/health"
    wait_command: true
    pause: 5                 # пауза после команды = интервал опроса
```

Кусок сценария, не весь файл:

```yaml
  - type: "$HOST=http://127.0.0.1:8080"
  - loop: 10
    caption: health
    pause: 5                 # пауза между кругами (если есть вложенные steps:)
    steps:
      - type: "curl -sS $HOST/health"
        wait_command: true
        pause: 0
      - type: "date"
        wait_command: true
        pause: 0
```

Команда без вложенного списка — тот же `loop:` на шаге с `type:`:

```yaml
  - loop: true
    type: "curl -sS http://127.0.0.1:8080/health"
    wait_command: true
    pause: 5
```

- Перед проигрыванием теги из `#tag cmd` (и опционально `reset_tags: [hello]`) **удаляются из БД**, чтобы повторный `--demo` не плодил `hello[4]`.
- `caption` / `say` — подпись шага в subtitle.
- `keys`: `enter`, `escape`/`esc`, `tab`, `f2`…`f6`, `up`/`down`, `home`/`end`, `pageup`/`pagedown`, `ctrl+c`, `ctrl+d`, `ctrl+v`, или список. После `tab` в журнале следующий `type` снова берёт строку ввода (иначе Enter включит курсор строк, как F2).
- Не ставьте в YAML `> htop` / `vim` / `ssh`: TUI снимется и будет ждать человека.
- Не ставьте `:q` в шаги, если нужен хвост записи; для автовыхода — `--demo-quit`.

### Запись из обычной сессии

Пока работаете руками, каждая строка по Enter копится в лог (не Tab/F5/мышь, не `> htop`).

```
:playbook              # cwd/playbook.yml
:playbook tour.yml
:playbook -            # превью YAML в журнале
:playbook clear        # забыть лог и начать набор заново
```

Потом: `python3 app.py --demo tour.yml`. Shell-команды получают `wait_command: true`; `#tag`, `?`, `!`, `:` — нет. Теги из `#tag cmd` попадают в `reset_tags`. После записи YAML можно дописать `keys` / `caption` / `loop:` руками.

Ниже — ручной сценарий, если ведёте демо сами (с паузами и словами).

---

## Подготовка (до зрителей)

```bash
python3 src/seed_linux_commands.py --seed   # если БД пустая: теги proc / file / net / kube
python3 src/seed_git.py --seed              # опционально: git / gstat / gsync
# без seed при первом старте TUI сам покажет каталог: клик по --seed вставляет команду, клик по .md открывает справочник
python3 app.py
```

Рядом с запуском положить `demo.json`:

```json
{"service":"api","env":"prod","pods":[{"name":"api-7f","status":"CrashLoop"}]}
```

Для второго профиля: `python3 app.py --instance-name=user1` или в уже запущенном TUI `:session user1`.

---

## Акт 1. Это не «ещё один shell» (~2 мин)

| Что показать | Что набрать / нажать | Зачем |
|---|---|---|
| Справка | `:?` | карта префиксов |
| Тема | `d` | тёмная / светлая |
| Обычная команда | `echo hello-idvj` | блок в журнале, UI не блокируется |
| История сессии | `↑` / `↓` во вводе | как в bash, но только эта сессия |
| Пути | `ls ./` затем Tab | список под вводом, Tab берёт токен |
| Каталог приложения | `cd /tmp` → `pwd` → `:cd` | `cd` меняет cwd для shell-команд; теги остаются в каталоге запуска |
| Назад | `cd -` | как в shell |
| Переменная | `$HOST=api.prod.local` затем `echo ping $HOST` | пишется в `.bashrc_term`, живёт между запусками |
| Алиас с `$1` | если в `~/.bashrc` есть `alias klogin="tsh kube login $1"` — `klogin my-cluster` | аргумент подставляется, не дописывается в конец |
| Настоящий TTY | `> htop` (q чтобы выйти) | TUI снимается; так же `vim` / `ssh` / `less` |

Фраза: «Обычный Enter — вывод в журнал. `>` — если нужен настоящий терминал.»

---

## Акт 2. Журнал как рабочий стол (~3 мин)

Наполнить экран:

```bash
seq 1 40
python3 -m json.tool demo.json
echo "error: timeout connecting to $HOST"
echo "warn: retry ok"
```

| Что показать | Как |
|---|---|
| Фокус на последний блок | `Tab` из ввода |
| Клик по блоку | мышь (`terminal_mouse: true` в `settings.yml`) |
| Страница журнала | `PgUp` / `PgDn` — активен **видимый** блок, без прыжка к его началу |
| Свернуть | `Space` или `←` / `→` |
| Поиск по строкам | на блоке `/` → `timeout` Enter. Курсор на строке |
| Дальше / назад | `n` / `N` или `:n` / `:N` |
| Построчный режим | `F2` или Enter на блоке. `↑` `↓`, Home / End |
| Скопировать строку | Enter — буфер + возврат во ввод |
| Дописать несколько строк | `Ctrl+V` / Shift+Enter, остаётесь в блоке |
| Весь stdout блока | `F3` |
| Простой текст | `F6` — удобнее выделять мышью |
| Повторить команду блока | `:r` — строка во вводе, ещё не запущена |
| Пайп с фокуса | фокус на `seq` → `\| grep 27` |
| JSON из вывода | фокус на `json.tool` → `F5`. Enter на `.pods[0].name` → во вводе черновик `\| jq '…'`, переменная `$JSON` |
| JSON из файла | `:json demo.json` |

Фраза: «Журнал — не лог, а набор блоков. Ищете, копируете строку, пайте, открываете JSON — не выходя в другой инструмент.»

---

## Акт 3. Главное: теги как переменные (~5 мин)

Сюжет: деплой в три шага, которые потом собираются в одну строку.

Сохранить шаблоны (ссылки **не** раскрываются при `#`):

```text
#check curl -sI http://$HOST
#check=healthcheck of $HOST
#logs kubectl logs -l app=api --tail=50
#restart kubectl rollout restart deploy/api
#pipeline !check[1] && !logs[1]
```

Показать библиотеку:

```text
?
?check
??
?pipeline[1]
```

`?pipeline[1]` — превью, как раскроются ссылки.

Сборка:

1. Набрать `!` — список тегов `[check, logs, …]`, Tab выбирает тег.
2. Дальше список `<id> check[1]  curl …`, Tab вставляет **`!check[1]`**, не всю команду.
3. Enter на `!check[1]` — только подстановка; второй Enter — запуск.
4. Собрать цепочку: `!! check[1] && logs[1]` — во вводе уже живая командная строка.

Правка и жизненный цикл:

```text
#check+1                 подставить на редактирование, поправить, сохранить снова
#check=1=HEAD only
#logs-1                  мягкое удаление
?logs                    пусто
#logs!1                  вернули
:export check /tmp/check.json
:import /tmp/check.json  новые tid; тег можно унести коллеге
```

Фраза: «`#` кладёт шаблон в SQLite. `!` / `!!` собирают строку. Удаление мягкое, тег вывозится JSON-ом.»

Если БД уже живая — не сидить заново, брать свои теги `file` / `kube` вместо `check` / `logs`.

---

## Акт 4. Обвязка сессии (~1 мин)

```text
:h 10                     история оболочки одним блоком — строки копируются построчно
:w /tmp/demo-session.txt
:c                        очистить журнал (БД тегов не трогает)
Ctrl+D                    стереть ввод
:q                        выход
```

Перезапуск `python3 app.py` → `$HOST` и теги на месте.

---

## Акт 5. Мозг и инструменты (live, ~2 мин)

То, что нельзя безопасно проиграть автотуром (сеть, ключи, TTY). Показывайте руками — только при живом рассказе:

| Что показать | Как | Зачем |
|---|---|---|
| LLM-подбор связки | `:llm ask найди поды с именем api, покажи логи` | задача + шпаргалка приложения + выжимка тегов; ответ — ссылки `!tag[tid]`, кликом вставляются во ввод |
| Провайдер на выбор | `:llm ask openai <задача>` | ключ — из окружения (`$DEEPSEEK_API_KEY` и т.п.), конфиг — `llm_providers.yml` (создаётся из `src/llm_providers.example.yml`) |
| Файл в запрос | `:llm объясни @demo.json` | `@file` — вложить текст (≤200 КБ), `$OUT` / `$BLOCK` — вывод блока |
| Внешний редактор | `:ed $OUT` / `:ed notes.md` | TUI на паузе, редактор из `settings.yml` (`editor: nano`), `$VAR`/`$OUT` в пути |
| Справочник | `:md SEED_LINUX_COMMANDS.md` | форматированный Markdown в модалке |
| Ingress | `:i` / `:i analyze <ingress>` | нужен кластер и `crossplane` (опционально) |

Фраза: «Приложение само собирает контекст: команды из библиотеки, вывод блока, файл — и отдаёт задачу выбранному провайдеру.»

---

## Бис, если есть kubectl (~2 мин)

```text
:i
:i list -n kube-system     сам выставит $NS
:i analyze <ingress>
:i check <service>
```

Или из сида: `!kube[5]` → `kubectl get ns`.

---

## Финал (30 сек)

Три привычки:

1. **Сохранил** `#tag` — **собрал** `!!` — **запустил** Enter.
2. Блок в фокусе = источник: `|`, `:r`, F3, F5, поиск `/`.
3. `>` только когда нужен TTY; всё остальное остаётся в журнале.

---

## Короткий вариант (7 минут)

Оставить акты **1** (без алиаса и htop) → **2** (Tab, поиск, F2, F5) → **3** (save / `!` / `!!` / export).

Выкинуть `:h`, `:w`, `:c`, `:i`, F6, тему.
