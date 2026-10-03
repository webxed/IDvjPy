# План улучшения seed-справочников

## Цель

Справочники IDvjPy — учебная библиотека настоящих DevOps-инструментов, а не набор обёрток приложения. Улучшения должны помогать сначала осмотреть состояние, понять смысл флагов и только затем осознанно выполнять изменение.

Базовый язык контента — русский: встроенные комментарии в `src/seed_*.py` и документы в `docs/`. Английский и китайский слои обновляются, когда это нужно для изменённого пользовательского сценария или требуется соответствующими проверками.

## Общие правила

- Один сид заменяет только принадлежащие ему теги и перед этим создаёт SQLite-снимок непустой базы.
- В плейбуках первым должен быть осмотр: `status`, `get`, `describe`, `--dry-run`, диагностический запрос.
- Не добавлять в автоматические цепочки удаление, установку, изменение прав, бесконечный `follow` или интерактивные TTY-команды.
- Шаг, который меняет состояние, в `:run` всегда отмечать `run:manual`: команда лишь подставляется в строку ввода, а запуск подтверждает пользователь отдельным Enter.
- Команды должны быть реальными и показывать их эффект, параметры и ограничения. Не скрывать их за новыми командами IDvjPy.
- Обновлять соответствующий `docs/SEED_*_COMMANDS.md`, локализованный слой `src/seed_text/<lang>/` при необходимости и точечные тесты.

## Приоритет 1 — безопасность и точность

### 1. Vault: исключить вывод данных секрета из AppRole-плейбука

**Файлы:** `src/seed_vault.py`, `docs/SEED_VAULT_COMMANDS.md`, переводы и тесты при необходимости.

В завершающем автоматическом шаге `vapprole` заменить чтение значения:

```bash
vault read $SECRET
```

на проверку полномочий или метаданных без печати секрета:

```bash
vault token capabilities $SECRET
```

либо для KV-движка:

```bash
vault kv metadata get $SECRET
```

Так цепочка подтверждает работоспособность выданного токена, но не отправляет секретное значение в журнал.

### 2. SSH: связанный сценарий нового ключа

**Состояние:** реализован тег `skey`.

Плейбук проверяет путь ключа, вручную создаёт Ed25519-ключ с passphrase, вручную выполняет `ssh-copy-id` в TTY и затем проверяет вход с `BatchMode=yes`. При дальнейшем изменении сохранять свойства:

- не перезаписывать существующий ключ;
- генерацию и `ssh-copy-id` держать в `run:manual`;
- проверять host key по доверенному каналу, не считать один `ssh-keyscan` доказательством личности сервера.

## Приоритет 2 — безопасные диагностические команды

### 3. Пакетные менеджеры

**Файл:** `src/seed_pkg.py`.

Добавить предварительный просмотр операций вместо немедленной установки/удаления:

```bash
apt-get -s install $PKG
apt-get -s remove $PKG
apt-cache depends $PKG
apt-cache rdepends $PKG

dnf install --assumeno $PKG
dnf remove --assumeno $PKG
dnf repoquery --requires $PKG
dnf repoquery --whatrequires $PKG
```

Пояснить, что `-s` и `--assumeno` показывают предполагаемую транзакцию, но не применяют её.

### 4. PostgreSQL

**Файл:** `src/seed_data.py`.

Добавить только read-only запросы:

- активные запросы с продолжительностью;
- кто блокирует и кого блокируют;
- `pg_stat_user_tables`: dead tuples и признаки autovacuum;
- крупнейшие таблицы по полному размеру relation.

Не добавлять в обычные теги `pg_terminate_backend`, `VACUUM FULL`, `REINDEX` и `DROP`.

### 5. Kafka

**Файл:** `src/seed_data.py`.

Добавить:

```bash
kafka-consumer-groups --bootstrap-server $BROKER --describe --group $GROUP --verbose
kafka-acls --bootstrap-server $BROKER --list
```

Сделать ограничение чтения сообщений через `kcat` явным (`-c 10`). Добавить обзорный `khealth`: metadata → описание топика → lag группы, без чтения payload.

### 6. Kubernetes: DNS и RBAC

**Файл:** `src/seed_k8s_chains.py`.

Добавить read-only теги:

- `kdns`: `dnsPolicy`, `resolv.conf` в pod, Endpoints/EndpointSlices;
- проверки RBAC через `kubectl auth can-i` для pods, deployments, secrets и service account.

Новая переменная `$SA` должна быть добавлена в соответствующий переменный тег. Никаких мутирующих действий в автоматических цепочках.

### 7. Docker / Compose

**Файл:** `src/seed_docker.py`.

Добавить:

```bash
docker inspect --format '{{json .State.Health}}' $CTR
docker events --since 10m --until now
docker container ls --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
docker image inspect $IMAGE
docker compose config --quiet
docker compose ps --all
```

Не добавлять `prune`, `rm`, `down -v` в обзорные цепочки.

### 8. HTTP и TLS

**Файлы:** `src/seed_http.py`, `src/seed_netdbg.py`.

Добавить ограниченные диагностические запросы:

```bash
curl -sS -D - -o /dev/null --max-time 10 $URL
curl -sS --retry 2 --retry-all-errors --connect-timeout 3 --max-time 15 \
  -o /dev/null -w '%{http_code} %{time_total}\n' $URL
curl -sS -o /dev/null -w '%{remote_ip} %{http_version} %{http_code}\n' $URL

echo | timeout 8 openssl s_client -connect $HOST:$PORT \
  -servername $SNI -verify_return_error -brief
```

Отдельно объяснить: `curl -k` приемлем только для диагностики и не исправляет TLS.

### 9. SSH: known_hosts и проверка отпечатков

**Файл:** `src/seed_ssh.py`.

Добавить:

```bash
ssh-keygen -F $HOST
ssh-keyscan -T 5 -H $HOST
ssh-keygen -lf ~/.ssh/known_hosts
```

`ssh-keygen -R $HOST` допустим только как явно помеченная операция, меняющая `known_hosts`; не включать в inspect-плейбук.

### 10. systemd

**Файл:** `src/seed_systemd.py`.

Добавить:

```bash
systemctl show $UNIT -p ActiveState -p SubState -p Result \
  -p ExecMainStatus -p NRestarts
systemctl status $UNIT --no-pager -l
journalctl -u $UNIT --since "$SINCE" --no-pager -o short-iso
systemd-analyze verify $UNIT
```

Явно отмечать `daemon-reload` как изменение состояния менеджера units.

### 11. Ansible

**Файл:** `src/seed_ansible.py`.

Добавить:

```bash
ansible-inventory -i $INV --host $HOST
ansible-playbook -i $INV $PLAY --list-tasks --limit $LIMIT
ansible-galaxy collection list $COLLECTION
ansible-lint $PLAY
```

`ansible-lint` — необязательная внешняя утилита, не зависимость приложения. Уточнить, что `ansible-vault view` и расшифровка в stdout печатают plaintext в журнал.

### 12. SQLite: безопасное обучение записи

**Файл:** `src/seed_sqlite.py`.

Добавить команду явного создания снимка перед ручным SQL:

```bash
cp "$DBFILE" "mytags-before-manual-sqlite-$(date +%Y%m%d-%H%M%S).db"
```

Пометить её как создание файла. Добавить учебный пример транзакции с откатом:

```bash
sqlite3 "$DBFILE" \
  "BEGIN; DELETE FROM commands WHERE tag = '$TAG'; SELECT changes(); ROLLBACK;"
```

Документация должна пояснить, что это обучающий shell/SQL-шаблон, а не пример параметризованного Python-запроса.

## Приоритет 3 — отдельный обзорный справочник

### 13. Возможный handbook `observe`

Создавать только если он формирует самостоятельный сценарий начального разбора инцидента, а не дублирует существующие теги. Возможный состав:

```bash
uptime
free -h
df -hT
vmstat 1 5
ss -s
systemctl --failed --no-pager
journalctl -p err -n 80 --no-pager
```

Итоговый плейбук `otriage` должен быть конечным, read-only и вести от общего состояния хоста к конкретному профильному справочнику (`systemd`, `netfw`, `disk`, `sysstat`).

## Технический рефакторинг — отдельной задачей

### 14. Унифицировать Git и Kubernetes seed entry points

**Файлы:** `src/seed_git.py`, `src/seed_k8s_chains.py`, `src/seed_lib.py`.

`seed_git.py` и `seed_k8s_chains.py` дублируют поиск БД, backup, hard-delete, основной цикл и CLI, тогда как остальные handbooks используют `seed_lib.run_seed()` и `seed_cli()`.

Отдельно мигрировать их на общие функции. Обязательные условия:

- сохранить теги, порядок tid, команды, метки backup и поддержку `--db`;
- не соединять этот рефакторинг с содержательными изменениями команд;
- проверить seed-specific, catalog/group и локализационные тесты до и после.

## Аннотирование каталога метаданными

### 15. Разметить канонические теги через `:tagmeta`

**Файлы:** `src/seed_*.py` (несколько), `docs/SEED_*_COMMANDS.md`, точечные тесты.

**Проблема.** `set_tag_metadata()` вызывается только из ручной команды `:tagmeta` (`src/app.py:_handle_tagmeta_command`). Ни один `seed_*.py` в колонку `tags.metadata` не пишет — она остаётся пустой (`'{}'` из миграции `init_db`). Поэтому `:tagmeta TAG` на любом посеянном теге отвечает «нет метаданных», а фильтр `:tags` (ищет и по JSON метаданных, `_handle_tags_command`) по атрибутам не работает.

**Что сделать.** Разметить часть канонических тегов полями схемы `TAG_METADATA_FIELDS`:

- `risk` — `low` / `medium` / `high` / `critical`;
- `utilities`, `os` — массивы строк;
- `interactive` — bool (нужен ли настоящий TTY, т.е. `> cmd`);
- `topic` — тема (`inspect`, `network`, `secrets`, …);
- `example` — пример вызова.

Тогда `:tags git`, `:tags linux`, `:tags inspect` начнут фильтровать по атрибутам, а `:tagmeta` перестанет выглядеть пустым — справочник сам покажет инструмент, а не спрячет его.

**Ограничения и правила.**

- Писать только через `database.set_tag_metadata()` — это единственная валидирующая точка (схема и лимит 8192 байта). Не заводить второй путь записи в `metadata`.
- `utilities`, `os`, `topic` — стабильные машинные токены, не переводятся: иначе после `:relang` или смены языка `:tags linux` перестанет находить теги, а чужая библиотека при `:import` потеряет срез. `example` — реальная команда, тоже не переводится. Локализуемы только пояснения в комментариях тегов.
- `risk` — описательная пометка, а не механизм безопасности: подтверждение рискованных команд делает `:safe` (`safe_mode.command_risks`), а реальный мутирующий шаг в `:run` держится на `run:manual` в комментарии. Не выдавать `risk` за защиту.
- Разметка не должна затираться: `:relang` (`src/relang.py`) переписывает только комментарии канонических строк, а `seed_*` перезаписывает только свои теги. Проверить, что повторный `--seed` и `:relang` не сбрасывают `metadata` в `'{}'`; если сбрасывают — чинить причину, а не дорисовывать после.
- Начать с малого подмножества (`git`, `k8s`, `linux`, `docker`, `sqlite`, `vault`), а не размечать всю библиотеку сразу.

**Проверки.** Точечные тесты: `:tagmeta TAG` после посева показывает ожидаемые поля; `:tags <атрибут>` находит размеченный тег; повторный `--seed` не теряет метаданные; `:export` / `:import` переносят `tag_metadata` без потерь.

## Порядок реализации

1. Vault: безопасно заменить финальный шаг `vapprole`.
2. Package dry-run.
3. PostgreSQL и Kafka inspection.
4. Kubernetes DNS/RBAC.
5. Docker, HTTP/TLS, systemd, Ansible, SQLite — независимыми небольшими изменениями.
6. Оценить необходимость `observe` после того, как улучшены существующие справочники.
7. Отдельно выполнить refactor Git/Kubernetes seed entry points.
8. Разметить `:tagmeta` у части канонических тегов — независимая задача, но после стабилизации набора команд, чтобы не размечать дважды.

Для каждого небольшого изменения запускать только затронутые тесты, например:

```bash
python3 -m pytest tests/test_seed_ops.py tests/test_seed_i18n.py -q
```

Полный `pytest tests/` не запускать без явного запроса: набор выполняется долго.

## Статус выполнения

- [x] 1. Vault: финальный шаг `vapprole` → `vault token capabilities $SECRET` (значение не печатается).
- [x] 2. Пакеты: dry-run `apt-get -s` / `dnf --assumeno`, `apt-cache depends/rdepends`, `dnf repoquery --requires/--whatrequires`.
- [x] 3. PostgreSQL: активные запросы с длительностью, `pg_blocking_pids`, `pg_stat_user_tables`, крупнейшие таблицы. Kafka: `--verbose`, `kafka-acls --list`, явный `kcat -c 10`, новый обзор `khealth`.
- [x] 4. Kubernetes: `$SA`, теги `kdns` (dnsPolicy/resolv.conf/Endpoints/CoreDNS) и `krbac` (`auth can-i`, impersonation SA).
- [x] 5. Docker (`State.Health`, `events`, `container ls`, `image inspect`, `compose config --quiet`, `compose ps --all`), HTTP (`-D -`, retry/timeouts, `remote_ip/http_version`), TLS (`-verify_return_error`), systemd (`show -p`, `status -l`, `short-iso`, `systemd-analyze verify`), Ansible (`--host`, `--list-tasks --limit`, `collection list $COLLECTION`, `ansible-lint`), SQLite (снимок перед ручным SQL + учебный `ROLLBACK`).
- [x] 6. `observe` — **решили не создавать**: предлагаемые команды уже живут в `hinfo` (uptime/free), `disk` (df), `sysstat` (vmstat), `netfw` (ss), `systemd` (failed/journal), поэтому отдельный handbook дублировал бы существующие теги (см. пункт 13).
- [x] 7. Git/Kubernetes переведены на `seed_lib.run_seed()` / `seed_cli()` (добавлен параметр `label`, метки backup `git` / `k8s` сохранены).
- [x] 8. `:tagmeta`: канонические сиды размечают теги через единственный писатель `database.set_tag_metadata()` (git, gstat, kns, kpod, klog, kdns, krbac, dck, dcmp, sqlite, vault, vapprole, proc, file, net, kube). Машинные токены не переводятся, повторный `--seed` не сбрасывает разметку.
