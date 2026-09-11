# Демостенд в Docker

Маленький образ (~100 МБ) с уже наполненной библиотекой тегов: TUI можно потрогать,
не ставя Python и не трогая свои настройки. Все данные живут в томе
`idvjpy-demo-data`, код — внутри образа.

## Быстрый старт

```bash
cd docker
docker compose run --rm idvjpy        # образ соберётся при первом запуске
```

Из корня репозитория то же самое: `docker compose -f docker/compose.yaml run --rm idvjpy`.

При первом запуске стенд сам:
1. создаёт `/data/settings.yml` и `/data/llm_providers.yml` из шаблонов `src/*.example.yml`;
2. наполняет библиотеку тегов (`linux`, `k8s`, `git`, `ops` — 849 команд, ~5 с);
3. запускает TUI.

Повторные запуски ничего не пересобирают — библиотека уже в томе.

## Что попробовать

| Ввод | Что показывает |
|------|----------------|
| `:?` | справка: префиксы и горячие клавиши |
| `??` | вся библиотека по тегам (клик по `tag[tid]` вставляет ссылку во ввод) |
| `?kpod` | команды одного тега с `tid` |
| `!` | список тегов по мере набора |
| `!! kpod[1] && klog[1]` | сборка одной строки из двух тегов |
| `echo hello` + Enter | обычная команда в журнал (TUI не блокируется) |
| `seq 1 12` → `\| grep 7` | пайп stdout сфокусированного блока |
| `$OUT` | последняя непустая строка вывода блока |
| `:llm ask найди поды и покажи логи` | LLM получает задачу + библиотеку тегов (нужен ключ) |
| `:editor $OUT` | правка строки вывода во внешнем редакторе (`nano`) |
| `:md SEED_LINUX_COMMANDS.md` | справочник с форматированием |
| `:stats` / `:export * catalog.md` | метрики библиотеки / каталог в Markdown |
| `:screensaver` | starfield |
| `:q` | выход |

## Автопоказ (удобно для скринкаста)

```bash
docker compose run --rm idvjpy --demo short --demo-quit   # короткий тур
docker compose run --rm idvjpy --demo full  --demo-quit   # полный
docker compose run --rm idvjpy --demo ip                  # myip → jq → wiki
```

Один шаг полного тура ходит в сеть (`curl` на `api.agify.io`) — без сети он просто
покажет ошибку шага.

## Без compose

```bash
docker build -f docker/Dockerfile -t idvjpy-demo .
docker run --rm -it -v idvjpy-demo-data:/data idvjpy-demo
# без интерактива (docker выделяет pty сам):
docker run --rm -t -v idvjpy-demo-data:/data idvjpy-demo --demo short --demo-quit
```

## Данные и сброс

В томе `idvjpy-demo-data` лежит всё изменяемое: `settings.yml`, `mytags.db`,
`history_default.txt`, `.bashrc_term_default`.

- **Настройки** — правьте изнутри приложения: `:editor settings.yml` (в контейнере
  стоит `nano`). Так же можно править `llm_providers.yml`.
- **Ключ для `:llm`** — либо `docker compose run --rm -e DEEPSEEK_API_KEY=... idvjpy`,
  либо прямо в TUI: `$DEEPSEEK_API_KEY=sk-...`, затем `:llm ...`.
- **Сброс к заводским** — `docker volume rm idvjpy-demo-data`: следующий запуск снова
  создаст шаблоны и наполнит библиотеку.
- **Снимок БД** — `:backup` внутри приложения пишет в `/data/backups`; вынести наружу:
  `docker run --rm -v idvjpy-demo-data:/data -v "$PWD":/out alpine cp -r /data/backups /out/`.

## Что внутри и что заведомо не работает

- База `python:3.12-alpine` плюс `bash` (приложение запускает команды и TTY через
  `/bin/bash`), `ncurses-terminfo-base` (terminfo для `TERM=xterm-256color`), `nano`,
  `git`, `curl`, `jq`, `procps`; Python-зависимости — из `requirements.txt`.
- `docker` и `kubectl` **не** установлены: теги `dck`/`kpod` — это шаблоны команд, их
  можно собирать и листать, но выполнить `kubectl get pods` в контейнере нечем.
  Расширить образ:
  ```dockerfile
  FROM idvjpy-demo
  RUN apk add --no-cache docker-cli kubectl
  ```
  и добавить нужные монтирования (`/var/run/docker.sock`, `~/.kube/config`).
- `:fm` / `:term` не откроются — в контейнере нет X/Wayland.
- `:i` (Ingress Analyzer) требует `kubectl` и живой кластер.
- При старте приложение сверяет версию с GitHub (`check_updates: true` из шаблона).
  Без сети это просто сообщение; отключается в `:editor settings.yml`.
- Процессы внутри контейнера работают под `root` — для демо это нормально, том
  именованный (прав хоста это не касается).

## Проверка стенда

- **Смоук TUI локально.** В образе есть `tui-smoke.py`: он поднимает настоящий pty
  (Textual без tty не работает), задаёт размер 120×40, читает отрисованное,
  падает на traceback/таймауте и умеет требовать подстроку:

  ```bash
  docker run --rm -v idvjpy-demo-data:/data --entrypoint python3 idvjpy-demo \
    /usr/local/bin/tui-smoke.py --expect IDvjPy_term --timeout 180 \
      -- /usr/local/bin/idvjpy-demo --demo short --demo-quit
  ```

- **CI** (`.github/workflows/tests.yml`, job `docker-demo`): сборка образа через
  BuildKit с кэшем GitHub Actions, затем первый запуск (шаблоны + посев), проверка
  непустой библиотеки в томе, идемпотентность второго запуска и рендер TUI под pty.
- Статические проверки согласованности стенда — `tests/test_docker_stand.py`
  (без сборки образа).

## Как это собрано

- `docker/Dockerfile` — образ; контекст сборки — корень репозитория.
- `docker/entrypoint.sh` — подготовка `/data`, однократный посев, запуск `app.py`
  с проброшенными аргументами.
- `docker/compose.yaml` — сервис `idvjpy` с `tty`/`stdin_open` и именованным томом.
- `/.dockerignore` — в контекст не попадают `.git`, `.venv`, `tests/`, `packaging/`,
  данные и сборки, поэтому сборка быстрая, а образ не тянет лишнего.
