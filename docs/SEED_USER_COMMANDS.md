# Справочник пользователей и прав

Теги **`ident`** (id/getent/last/sudo), **`perm`** (stat/chmod/chown).  
Плейбук **`uidchk`**: id → groups → `sudo -n -l`. Нет `userdel`.

```bash
python3 src/seed_user.py --seed
# или вместе с остальными ops:
python3 src/seed_ops.py --seed
```

```text
$USER=
$FILE=/etc/passwd
$MODE=644
$OWNER=root
$GROUP=root
!! uvars[1]
!! uidchk[1]
```

`chmod` / `chown` меняют файлы — только руками. `sudo -l` с паролем: `> sudo -l`.

---

## ident (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `id` | Текущий uid/gid |
| 2 | `id $USER` | Учётка `$USER` |
| 3 | `whoami` | Имя |
| 4 | `groups $USER` | Группы |
| 5 | `getent passwd $USER` | passwd |
| 6 | `getent group $GROUP` | Группа |
| 7 | `last -n 20` | Логины |
| 8 | `lastb -n 20` | Неудачные |
| 9 | `lastlog \| tail` | lastlog |
| 10 | `sudo -n -l` | sudo без пароля |
| 11 | `sudo -l` | sudo (лучше `>`) |
| 12 | `w` | Кто на системе |
| 13 | `who` | Сессии |

---

## perm (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `stat $FILE` | Метаданные |
| 2 | `ls -ld $FILE` | Права |
| 3 | `namei -l $FILE` | Цепочка путей |
| 4 | `getfacl $FILE` | ACL |
| 5 | `umask -S` | umask |
| 6 | `chmod $MODE $FILE` | chmod (меняет файл) |
| 7 | `chmod -R $MODE $FILE` | Рекурсивный chmod |
| 8 | `chown $OWNER $FILE` | Владелец |
| 9 | `chown $OWNER:$GROUP $FILE` | Владелец и группа |
| 10 | `chgrp $GROUP $FILE` | Группа |

Tid 6–10 не в плейбуке.

---

## Плейбуки

| Тег | Цепочка |
|-----|---------|
| `uidchk[1]` | `id` → `groups` → `sudo -n -l` |
