# IDvjPy 的 ssh / scp 手册

标签 **`ssh`**、**`scp`**。运行手册：`schk`（访问）、`ossh`（OpenSSH 版本）、`ocert`（证书有效期）。

基础的 `ssh` / `scp` 已在 linux 标签 `net[5]` / `net[7]` 中 —— 本种子不会覆盖它们。

交互式 shell —— 用 `>` 前缀（`> ssh $REMOTE`）。否则 TUI 会撞上 timeout。

```bash
python3 src/seed_ssh.py --seed
# 或与其余 ops 一起：
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

`$REMOTE` —— `user@host`（同 rsync）。`$HOST` —— 用于 `-G` 和 `keyscan` 的名称。  
`$KEY` —— **私钥**（`id_ed25519`）；`-lf` / `ssh-copy-id -i` 也接受 `.pub`。  
`$CERT` —— OpenSSH **证书**（`*-cert.pub`），不是 X.509。Host cert：`/etc/ssh/ssh_host_ed25519_key-cert.pub`。

---

## ssh (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `ssh -G $HOST` | 有效配置 |
| 2 | `ssh -o BatchMode=yes -o ConnectTimeout=5 $REMOTE true` | 是否存在密钥访问 |
| 3 | `ssh-keyscan -T 5 $HOST` | Host key |
| 4 | `ls -la ~/.ssh` | 密钥目录 |
| 5 | `ssh-add -l` | Agent |
| 6 | `ssh-keygen -lf $KEY` | 指纹 |
| 7 | `ssh -p $PORT … $REMOTE true` | 端口检查 |
| 8 | `ssh $REMOTE $CMD` | 远程命令 |
| 9 | `ssh -v … $REMOTE true` | Debug |
| 10 | `ssh -O check $REMOTE` | ControlMaster |
| 11 | `ssh $REMOTE` | 登录（`> ssh $REMOTE`） |
| 12 | `ssh -t $REMOTE` | 带 TTY 登录（`> …`） |
| 13 | `ssh-copy-id -i $KEY $REMOTE` | 安装 pubkey |
| 14 | `mkdir -p ~/.ssh && chmod 700 ~/.ssh` | `~/.ssh` 目录 |
| 15 | `test ! -e "$KEY" && ssh-keygen -t ed25519 …` | 文件不存在时创建 Ed25519 |
| 16 | `ssh-keygen -t ed25519 -f "$KEY" -C "$COMMENT"` | 带 passphrase 的 Ed25519（`> …`） |
| 17 | `test ! -e "$KEY" && ssh-keygen -t rsa -b 4096 …` | 文件不存在时创建 RSA 4096 |
| 18 | `ssh-keygen -y -f "$KEY"` | 从私钥导出公钥 |
| 19 | `ssh-add "$KEY"` | 加入 agent |
| 20 | `ssh -V` | OpenSSH 版本 |
| 21 | `ssh -Q key` | 密钥类型 |
| 22 | `ssh -Q kex` | KEX |
| 23 | `ssh -Q cipher` | 加密算法 |
| 24 | `ssh -Q mac` | MAC |
| 25 | `ls -l /etc/ssh` | 配置与 host keys |
| 26 | `ls … *cert*` | 证书文件 |
| 27 | `sshd -T \| grep hostkey/cert/…` | 有效 sshd 配置（通常需 root） |
| 28 | `ssh-keygen -L -f "$CERT"` | 完整解析证书 |
| 29 | `ssh-keygen -L … \| grep Type/Valid/…` | CA、Valid、principals |
| 30 | `valid_to=…; days_left=…` | 距到期天数（GNU `date`） |

`ssh-copy-id` 和生成密钥不在运行手册中。tid 15/17 不会覆盖已存在的 `$KEY`。

`ssh-keygen -L` 读取的是 OpenSSH 证书（`-cert.pub`）。如果是普通密钥，命令会报错。`days_left` 根据 `Valid: from … to …` 这一行计算。

---

## scp (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `scp … "$SRC" "$REMOTE:$DEST"` | 到主机 |
| 2 | `scp … "$REMOTE:$SRC" "$DEST"` | 从主机 |
| 3 | `scp -P $PORT …` | 其他端口 |
| 4 | `scp -r …` | 递归 |
| 5 | `scp -p …` | 保留 mtime/mode |
| 6 | `scp -v …` | Verbose |

在 TTY 中输入密码：`> scp …`。对于大型目录树，`!! rchk[1]` / rsync 更方便。

---

## 运行手册

| 标签 | 命令链 |
|-----|---------|
| `schk[1]` | `-G` → BatchMode `true` → keyscan |
| `ossh[1]` | `ssh -V` → `ssh -Q key` → 文件 `*cert*` |
| `ocert[1]` | 证书摘要 → `days_left` |

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
