# Users and permissions handbook

Tags **`ident`** (id/getent/last/sudo), **`perm`** (stat/chmod/chown).  
Playbook **`uidchk`**: id → groups → `sudo -n -l`. No `userdel`.

```bash
python3 src/seed_user.py --seed
# or together with the other ops:
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

`chmod` / `chown` change files — manual only. `sudo -l` with a password: `> sudo -l`.

---

## ident (tid)

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `id` | Current uid/gid |
| 2 | `id $USER` | Account `$USER` |
| 3 | `whoami` | Name |
| 4 | `groups $USER` | Groups of `$USER` |
| 5 | `getent passwd $USER` | passwd `$USER` |
| 6 | `getent group $GROUP` | Group `$GROUP` |
| 7 | `last -n 20` | Last logins |
| 8 | `lastb -n 20` | Failed logins (often root) |
| 9 | `lastlog \| tail` | lastlog, tail |
| 10 | `sudo -n -l` | sudo -l without a password (may fail) |
| 11 | `sudo -l` | `sudo -l` (better: `> sudo -l`) |
| 12 | `w` | Who is on the system |
| 13 | `who` | Sessions |

---

## perm (tid)

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `stat $FILE` | Metadata of `$FILE` |
| 2 | `ls -ld $FILE` | Permissions and owner |
| 3 | `namei -l $FILE` | Path chain |
| 4 | `getfacl $FILE` | ACL (if present) |
| 5 | `umask -S` | Current umask |
| 6 | `chmod $MODE $FILE` | chmod `$MODE` (changes the file) |
| 7 | `chmod -R $MODE $FILE` | Recursive chmod |
| 8 | `chown $OWNER $FILE` | Owner `$OWNER` |
| 9 | `chown $OWNER:$GROUP $FILE` | Owner and group |
| 10 | `chgrp $GROUP $FILE` | Group `$GROUP` |

Tid 6–10 are not in the playbook.

---

## Playbooks

| Tag | Chain |
|-----|---------|
| `uidchk[1]` | `id` → `groups` → `sudo -n -l` |
