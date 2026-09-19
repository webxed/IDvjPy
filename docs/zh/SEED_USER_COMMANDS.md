# 用户与权限手册

标签 **`ident`**（id/getent/last/sudo）、**`perm`**（stat/chmod/chown）。  
剧本 **`uidchk`**：id → groups → `sudo -n -l`。没有 `userdel`。

```bash
python3 src/seed_user.py --seed
# 或与其他 ops 一起：
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

`chmod` / `chown` 会修改文件——只能手动执行。需要密码的 `sudo -l`：`> sudo -l`。

---

## ident (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `id` | 当前 uid/gid |
| 2 | `id $USER` | `$USER` 账号 |
| 3 | `whoami` | 名称 |
| 4 | `groups $USER` | 组 |
| 5 | `getent passwd $USER` | passwd |
| 6 | `getent group $GROUP` | 组 |
| 7 | `last -n 20` | 登录记录 |
| 8 | `lastb -n 20` | 失败登录 |
| 9 | `lastlog \| tail` | lastlog |
| 10 | `sudo -n -l` | 免密 sudo |
| 11 | `sudo -l` | sudo（最好用 `>`） |
| 12 | `w` | 谁在系统上 |
| 13 | `who` | 会话 |

---

## perm (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `stat $FILE` | 元数据 |
| 2 | `ls -ld $FILE` | 权限 |
| 3 | `namei -l $FILE` | 路径链 |
| 4 | `getfacl $FILE` | ACL |
| 5 | `umask -S` | umask |
| 6 | `chmod $MODE $FILE` | chmod（修改文件） |
| 7 | `chmod -R $MODE $FILE` | 递归 chmod |
| 8 | `chown $OWNER $FILE` | 所有者 |
| 9 | `chown $OWNER:$GROUP $FILE` | 所有者和组 |
| 10 | `chgrp $GROUP $FILE` | 组 |

Tid 6–10 不放入剧本。

---

## 剧本

| 标签 | 命令链 |
|-----|---------|
| `uidchk[1]` | `id` → `groups` → `sudo -n -l` |
