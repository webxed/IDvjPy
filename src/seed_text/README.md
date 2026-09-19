# Тексты сидов по языкам (`seed_text/<lang>/<handbook>.yml`)

Команды и структура хэндбуков живут в `src/seed_<handbook>.py` (там же — встроенные
комментарии, базовый/русский текст). Переводы комментариев — здесь, по языкам:

```
src/seed_text/en/git.yml      # english comments
src/seed_text/en/k8s_chains.yml
...
```

Правила загрузки — `src/seed_lib.localized_tags()`: файлы языка сливаются в индекс
по **тегам** (имя файла роли не играет, тег встречается ровно в одном файле), а
отсутствующий ключ оставляет встроенный комментарий. Язык берётся из
`settings.yml: language` (или `$IDVJPY_LANG`), поэтому по умолчанию `--seed`
кладёт английские комментарии, а `language: ru` — русские (встроенные).

Язык **уже посеянной** библиотеки меняет `:relang <код>` (`src/relang.py`) —
переписывает комментарии канонических строк сидов, не трогая пользовательские
теги/команды и правленые руками комментарии; из терминала —
`python3 src/relang.py --lang ru`.

## Формат

```yaml
tags:
  git:
    comment: "git: status, diff, branches, remote, stash"   # подпись тега (в ?? и !)
    commands:
      3: "unstaged diff"        # позиция команды в хэндбуке (tid-1)
      4: "staged diff"
```

Ключи — позиции команд в порядке `SEED_TAGS` (не трогать!). Меняются только
значения. Пустые комментарии в файл не попадают.

## Как добавлять язык

1. `mkdir src/seed_text/<lang>` и скопировать туда файлы из `src/seed_text/en/`.
2. Перевести только значения.
3. Прогнать тесты: `python3 -m pytest tests/test_seed_i18n.py -q` — они требуют,
   чтобы наборы ключей совпадали с встроенными комментариями и чтобы в `en` не
   было кириллицы.

## Правила перевода (для агентов и людей)

- **НЕ переводить**: имена команд и утилит (`git`, `kubectl`, `helm`, `vault`,
  `ssh`, `jq`, `tar`, `iptables`, `systemd`, `journalctl`, `tcpdump`, `rsync`,
  `dig`, `nmap`, `apt`, `dnf`, `rpm`, `lsof`, `strace`, `ngrep`, `openssl`, …),
  флаги (`--no-pager`, `-la`, `-vv`), пути и имена файлов (`settings.yml`,
  `.bashrc_term`, `history_<instance>.txt`, `kctx.json`), переменные (`$NS`,
  `$POD`, `${VAR}`), префиксы и директивы (`#tag`, `!tag[tid]`, `??`, `$OUT`,
  `run:manual`, `run:prompt`, `run:pause=`, `run:continue`), имена тегов,
  аббревиатуры (`TLS`, `DNS`, `HTTP`, `L4/L7`, `CPU`, `RAM`, `JSON`, `YAML`,
  `k8s`, `RBAC`, `Ingress`).
- **Стиль подсказок** (`commands[i]`): 2–6 слов, с маленькой буквы, без точки;
  существительное или инфинитив: `"full status"`, `"unstaged diff"`,
  `"stop a process by PID"`.
- **Стиль подписи тега** (`comment`): как заголовок списка, через двоеточие:
  `"git: status, diff, branches"`.
- **Глоссарий** (держать единым по всем файлам): журнал → journal, блок → block,
  тег → tag, справочник → handbook, вывод → output, логи → logs, процессы →
  processes, файлы → files, сеть → network, сокеты → sockets, диски → disks,
  пакеты → packages, права → permissions, пользователи → users, сертификаты →
  certificates, архивы → archives, проверка → check, статус → status, версия →
  version, по умолчанию → default, поиск → search, сравнение → diff,
  безопасно → safely, без сети → offline, последние N → last N.
- Комментарий может начинаться с `run:…`-директив — их оставить как есть,
  переводится только текст подсказки после них.
