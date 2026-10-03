# Справочник ssh / scp для IDvjPy

Теги **`ssh`**, **`scp`**. Плейбуки: `schk` (доступ), `ossh` (версия OpenSSH), `ocert` (срок сертификата), `skey` (новый ключ и `ssh-copy-id`).

Базовые `ssh` / `scp` уже есть в linux-теге `net[5]` / `net[7]` — этот сид их не затирает.

Интерактивный shell — с префиксом `>` (`> ssh $REMOTE`). Иначе TUI упрётся в timeout.

```bash
python3 src/seed_ssh.py --seed
# или вместе с остальными ops:
python3 src/seed_ops.py --seed
```

```text
$REMOTE=user@host
$HOST=host
$PORT=22
$SRC=./file
$DEST=/tmp/
$KEY=~/.ssh/id_ed25519
$CERT=~/.ssh/id_ed25519-cert.pub
$COMMENT=
$CMD=uname -a
!! svars[1]
```

`$REMOTE` — `user@host` (как у rsync). `$HOST` — имя для `-G` и `keyscan`.  
`$KEY` — **приватный** ключ (`id_ed25519`); `-lf` / `ssh-copy-id -i` принимают и `.pub`.  
`$CERT` — OpenSSH **сертификат** (`*-cert.pub`), не X.509. Host cert: `/etc/ssh/ssh_host_ed25519_key-cert.pub`.

---

## ssh (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `ssh -G $HOST` | Эффективный конфиг |
| 2 | `ssh -o BatchMode=yes -o ConnectTimeout=5 $REMOTE true` | Есть ли доступ по ключу |
| 3 | `ssh-keyscan -T 5 $HOST` | Host key |
| 4 | `ls -la ~/.ssh` | Каталог ключей |
| 5 | `ssh-add -l` | Агент |
| 6 | `ssh-keygen -lf $KEY` | Fingerprint |
| 7 | `ssh -p $PORT … $REMOTE true` | Проверка порта |
| 8 | `ssh $REMOTE $CMD` | Удалённая команда |
| 9 | `ssh -v … $REMOTE true` | Debug |
| 10 | `ssh -O check $REMOTE` | ControlMaster |
| 11 | `ssh $REMOTE` | Login (`> ssh $REMOTE`) |
| 12 | `ssh -t $REMOTE` | Login с TTY (`> …`) |
| 13 | `ssh-copy-id -i $KEY $REMOTE` | Поставить pubkey |
| 14 | `mkdir -p ~/.ssh && chmod 700 ~/.ssh` | Каталог `~/.ssh` |
| 15 | `test ! -e "$KEY" && ssh-keygen -t ed25519 …` | Ed25519, если файла нет |
| 16 | `ssh-keygen -t ed25519 -f "$KEY" -C "$COMMENT"` | Ed25519 с passphrase (`> …`) |
| 17 | `test ! -e "$KEY" && ssh-keygen -t rsa -b 4096 …` | RSA 4096, если файла нет |
| 18 | `ssh-keygen -y -f "$KEY"` | Public из private |
| 19 | `ssh-add "$KEY"` | В агент |
| 20 | `ssh -V` | Версия OpenSSH |
| 21 | `ssh -Q key` | Типы ключей |
| 22 | `ssh -Q kex` | KEX |
| 23 | `ssh -Q cipher` | Шифры |
| 24 | `ssh -Q mac` | MAC |
| 25 | `ls -l /etc/ssh` | Конфиг и host keys |
| 26 | `ls … *cert*` | Файлы сертификатов |
| 27 | `sshd -T \| grep hostkey/cert/…` | Эффективный sshd (часто root) |
| 28 | `ssh-keygen -L -f "$CERT"` | Полный разбор сертификата |
| 29 | `ssh-keygen -L … \| grep Type/Valid/…` | CA, Valid, principals |
| 30 | `valid_to=…; days_left=…` | Суток до конца срока (GNU `date`) |

Tid 15/17 не перезаписывают существующий `$KEY`. Для связанного сценария создания защищённого Ed25519-ключа и публикации его на сервере есть `:run skey`.

`ssh-keygen -L` читает OpenSSH-cert (`-cert.pub`). Если это обычный ключ — команда ошибётся. `days_left` считает по строке `Valid: from … to …`.

---

## scp (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `scp … "$SRC" "$REMOTE:$DEST"` | На хост |
| 2 | `scp … "$REMOTE:$SRC" "$DEST"` | С хоста |
| 3 | `scp -P $PORT …` | Другой порт |
| 4 | `scp -r …` | Рекурсивно |
| 5 | `scp -p …` | Сохранить mtime/mode |
| 6 | `scp -v …` | Verbose |

Пароль в TTY: `> scp …`. Для больших деревьев удобнее `!! rchk[1]` / rsync.

---

## Плейбуки

| Тег | Цепочка |
|-----|---------|
| `schk[1]` | `-G` → BatchMode `true` → keyscan |
| `ossh[1]` | `ssh -V` → `ssh -Q key` → файлы `*cert*` |
| `ocert[1]` | сводка сертификата → `days_left` |
| `skey[1]` | проверить `$KEY` → вручную создать ключ → вручную `ssh-copy-id` → BatchMode-проверка |

### Новый ключ и доступ по нему: `:run skey`

```text
$KEY=~/.ssh/id_ed25519_example
$COMMENT="$(whoami)@$(hostname)-example"
$REMOTE=alice@app.example.com
:run skey
```

Первый и последний шаги выполняются автоматически. Создание ключа и `ssh-copy-id` помечены `run:manual`: приложение подставит команду, но запуск подтверждает человек отдельным Enter. Обе команды начинаются с `>`, поэтому работают в настоящем TTY: `ssh-keygen` запросит passphrase, а `ssh-copy-id` при необходимости — пароль **удалённого** пользователя.

Плейбук откажется перезаписывать существующий `$KEY`; выберите новый путь или сначала осмотрите старый ключ через `!! ssh[6]`. Перед `ssh-copy-id` сверяйте host key через доверенный канал: `ssh-keyscan` удобен для диагностики, но сам по себе не подтверждает личность сервера.

```text
$HOST=app.example.com
$REMOTE=alice@app.example.com
!! schk[1]
!! ossh[1]
$CERT=~/.ssh/id_ed25519-cert.pub
!! ocert[1]
$CMD='hostname; uptime'
!! ssh[8]
$SRC=./app.py
$DEST=/tmp/
!! scp[1]
$KEY=~/.ssh/id_ed25519
$COMMENT="$(whoami)@$(hostname)"
!! ssh[14]
!! ssh[15]
!! ssh[6]
```
