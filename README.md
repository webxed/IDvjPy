# IDvjPy — ID Variables & Joiner on Python

<p align="center">
  <img src="screen-demo-ip.gif" alt="IDvjPy_term: python3 app.py --demo ip" width="800">
</p>

<p align="center"><em>Define your variables, join your command.</em></p>

Keyboard-driven TUI that treats **tags as command templates** and assembles them into shell lines (`!tag[tid]`, `!!`). Python **3.12+**, [Textual](https://textual.textualize.io/).

**IDvjPy_term** v1.36 — умный терминал для создания командных строк из тегов.

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
- Остановка фоновой команды без ожидания timeout: `F4` / `:kill` (SIGTERM всей группе)
- Поиск по содержимому команд: `?kubectl wide` — если тега нет, ищет по тексту/комментариям
- Алиасы из `~/.bashrc` (в том числе `$1` / `$2` / `$@`), фоновое выполнение команд
- `> cmd` — настоящий TTY (htop, vim, ssh); клик и PgUp/PgDn активируют видимый блок журнала

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

## Запуск

```bash
python3 app.py
python3 app.py --instance-name=user1   # отдельный .bashrc_term_user1 и history_user1.txt
python3 app.py --demo                  # автотур: печатает команды сам (Esc — стоп)
python3 app.py --demo ip               # myip → jq .cc → Wiki URL → hello pipe → echo Hello, $OUT
python3 app.py --demo full --demo-quit
```

Код приложения лежит в `src/`. В корне рабочей копии — данные: `settings.yml`, база тегов, `.bashrc_term*`, `history_<instance>.txt`. Seed-справочники: `python3 src/seed_git.py --seed` и т.п. При пустой БД каталог в журнале: клик по `--seed` вставляет команду во ввод, клик по `.md` или `:md файл.md` открывает справочник (`terminal_mouse: true`).

| Путь | Назначение |
|------|------------|
| `src/` | TUI, CSS, seed-скрипты, шаблон `.bashrc_term.example` |
| `app.py` / `backup_db.py` | лаунчеры (не правят данные) |
| `settings.yml`, `*.db`, `.bashrc_term*` | настройки, теги, переменные |

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
| `:` | Команды приложения | `:q`, `:cd`, `:fm`, `:term`, `:session`, `:welcome`, `:backup`, `:screensaver`, `:r`, `:playbook`, `:md`, `:?` |
| `\| cmd` | Пайп stdout сфокусированного блока (в историю, как обычная команда) | `\| grep error` |
| `$OUT` | По запросу: последняя непустая строка блока (не хранится) | `echo Hello, $OUT` |
| `$VAR=val` | Локальная переменная (пишет `.bashrc_term_<instance>`) | `$EDITOR=nvim` |

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
- `:i …` — Kubernetes Ingress Analyzer (`:i` без аргументов — справка)
- `:cd [path]` — показать / сменить cwd для shell-команд (то же делает `cd path`). База тегов, история и `.bashrc_term*` остаются в каталоге запуска; пустой `mytags.db` в новой папке не создаётся.
- `:fm [path]` — проводник ОС в новом окне (cwd или путь). Linux: `xdg-open`; macOS: `open`; Windows: `explorer`. Свой: `$FILEMAN`
- `:term [path]` — системный терминал в новом окне. Linux: `xdg-terminal-exec` / `gnome-terminal` / …; macOS: Terminal.app; Windows: `wt` или `cmd`. Свой: `$TERMINAL`
- `:env` — перечитать `.bashrc_term*` (и алиасы `~/.bashrc`) в уже запущенном приложении. После `> cmd` экспорты **того же** bash подхватываются сами (вложенный `> bash` + `export` внутри — нет)
- `:session` — текущий инстанс (история + `.bashrc_term_*`). `:session NAME` — переключить или создать (БД тегов общая)
- `:welcome` — каталог seed, как при пустой БД (клик `--seed` / `.md`). На старте при непустой БД — блок **Разделы** с живыми тегами по handbook (`linux`, `k8s`, `git`, ops, `свои`)
- `:backup` — снимок SQLite в `backups/` (как перед `--seed`). Пустую базу не копирует. Вернуть: скопировать файл поверх рабочей БД.
- `:screensaver` — DevOps starfield сразу. Простой как в Norton Commander: звёзды летят на зрителя; ближе — `k8s` / `git` / `!!`. Вместе с ними летают живые часы (`15:35:42`) и дата (`2026-08-26`). Сверху ярко-зелёная лента на всю ширину с командами из БД (`!tag[tid]  cmd`). Снизу слева — справка команд (печать слева направо, отступ от края как раньше); снизу справа — load 1/5/15 и RAM (раз в секунду из `/proc`), с таким же отступом от правого угла; в узком окне load может наехать на справку. Спрятанные справочники (`#name--`) не показываются. Любая клавиша или клик закрывает (в ввод не попадает). Таймаут: `screensaver_idle` в `settings.yml` (секунды, `0` = выкл). `:screensaver 0` / `:screensaver 120` — на эту сессию. `screensaver_stars: false` — без летающей пыли/токенов (часы, лента и load остаются).
- `:r` — команда сфокусированного блока во ввод
- `:/text` / `:g` / `:n` / `:N` — поиск по строкам журнала (с блока `/` открывает `:/`; `n`/`N` — следующее / предыдущее)
- `:export tag [file]` / `:import file` — один тег в JSON и обратно
- `:playbook [file.yml]` — записать команды этой сессии (Enter) как YAML для `--demo` (по умолчанию `playbook.yml`). `:playbook -` — превью в журнале; `:playbook clear` — забыть записанное. Клавиши (Tab/F5) и мышь не пишутся. В YAML: `loop: true` / `loop: N` — крутить шаги (Esc — стоп); см. [DEMO.md](DEMO.md).
- `:update` — сверить `VERSION` с GitHub [`webxed/IDvjPy`](https://github.com/webxed/IDvjPy) `main`. При старте то же самое, если `check_updates: true` (пишет в журнал только если на GitHub новее). Прокси с логином: `$PROXY_USER` / `$PROXY_PASS` в `.bashrc_term` (плюс `HTTPS_PROXY` / `HTTP_PROXY`).
- `:theme [name]` — тема TUI (`dark` / `light` / `nord` / …); пишется в `settings.yml`. Клавиша `d` — dark/light
- `:?` — эта справка внутри TUI

## Горячие клавиши

| Клавиша | Действие |
|---------|----------|
| `Tab` | Из ввода — на последний блок журнала (`:h`, `:?`, команда); если открыт список подсказок — применить кандидата |
| `Esc` | Фокус на ввод. В построчном режиме: сначала выключить режим, повторный Esc — во ввод |
| `↑` / `↓` | `history_<instance>.txt` (+ сессия) во вводе; набранный текст фильтрует совпадения; прокрутка журнала, если фокус на блоке |
| `PgUp` / `PgDn` | Прокрутка журнала на страницу; активным становится **видимый** блок (без прыжка к его началу). Из ввода — переход в просмотр |
| клик по блоку | Фокус на блоке без прокрутки к началу (`terminal_mouse: true`). В пустой БД: клик по `--seed` — во ввод; по `.md` — справочник. В `??`: клик по тегу вставляет `!tag ` в позицию курсора (не затирает строку) |
| `Space` / `←` `→` | Свернуть / развернуть блок |
| `F3` | Копировать полный stdout блока |
| `Ctrl+C` | Скопировать всю строку ввода; если фокус на блоке журнала — весь блок (как F3) |
| `F5` | JSON viewer для сфокусированного (или последнего) блока |
| `F6` | Простой вывод (без Rich-тегов, удобнее выделять мышью) |
| `F2` | Построчный режим в блоке |
| `Shift+Insert` / `Ctrl+V` | Вставка во ввод (не затирает уже набранное). В построчном режиме `Ctrl+V` дописывает текущую строку |
| `Ctrl+D` | Очистить всю строку ввода |
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

[`settings.yml`](settings.yml):

```yaml
max_lines: 100000
history_lines: 20
database_tags_file: mytags.db
command_timeout: 10          # 0 = без таймаута
history_keep: 500            # хвост истории как лента; старше — без повторов. 0 = не сжимать. :h compact
terminal_mouse: true         # клик выделяет блок; false — выделение текста ОС
theme: textual-dark          # `d` / `:theme`; сохраняется при смене
check_updates: true          # старт: сверка VERSION с GitHub main; :update всегда
screensaver_idle: 120        # простой → starfield; 0 = выкл. :screensaver — сразу
screensaver_stars: true      # летающие звёзды; false — чёрный холст (часы/лента/load остаются)
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
