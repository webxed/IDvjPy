# ssh / scp handbook for IDvjPy

Tags **`ssh`**, **`scp`**. Playbooks: `schk` (access), `ossh` (OpenSSH version), `ocert` (certificate expiry).

Basic `ssh` / `scp` are already in the linux tag `net[5]` / `net[7]` — this seed does not overwrite them.

Interactive shell — with the `>` prefix (`> ssh $REMOTE`). Otherwise the TUI will hit a timeout.

```bash
python3 src/seed_ssh.py --seed
# or together with the rest of ops:
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

`$REMOTE` — `user@host` (same as rsync). `$HOST` — name for `-G` and `keyscan`.  
`$KEY` — **private** key (`id_ed25519`); `-lf` / `ssh-copy-id -i` also accept `.pub`.  
`$CERT` — OpenSSH **certificate** (`*-cert.pub`), not X.509. Host cert: `/etc/ssh/ssh_host_ed25519_key-cert.pub`.

---

## ssh (tid)

| tid | Command | Purpose |
|-----|---------|---------|
| 1 | `ssh -G $HOST` | Effective config |
| 2 | `ssh -o BatchMode=yes -o ConnectTimeout=5 $REMOTE true` | Is there access by key |
| 3 | `ssh-keyscan -T 5 $HOST` | Host key |
| 4 | `ls -la ~/.ssh` | Keys directory |
| 5 | `ssh-add -l` | Agent |
| 6 | `ssh-keygen -lf $KEY` | Fingerprint |
| 7 | `ssh -p $PORT … $REMOTE true` | Port check |
| 8 | `ssh $REMOTE $CMD` | Remote command |
| 9 | `ssh -v … $REMOTE true` | Debug |
| 10 | `ssh -O check $REMOTE` | ControlMaster |
| 11 | `ssh $REMOTE` | Login (`> ssh $REMOTE`) |
| 12 | `ssh -t $REMOTE` | Login with TTY (`> …`) |
| 13 | `ssh-copy-id -i $KEY $REMOTE` | Install pubkey |
| 14 | `mkdir -p ~/.ssh && chmod 700 ~/.ssh` | `~/.ssh` directory |
| 15 | `test ! -e "$KEY" && ssh-keygen -t ed25519 …` | Ed25519 if the file does not exist |
| 16 | `ssh-keygen -t ed25519 -f "$KEY" -C "$COMMENT"` | Ed25519 with passphrase (`> …`) |
| 17 | `test ! -e "$KEY" && ssh-keygen -t rsa -b 4096 …` | RSA 4096 if the file does not exist |
| 18 | `ssh-keygen -y -f "$KEY"` | Public from private |
| 19 | `ssh-add "$KEY"` | To the agent |
| 20 | `ssh -V` | OpenSSH version |
| 21 | `ssh -Q key` | Key types |
| 22 | `ssh -Q kex` | KEX |
| 23 | `ssh -Q cipher` | Ciphers |
| 24 | `ssh -Q mac` | MAC |
| 25 | `ls -l /etc/ssh` | Config and host keys |
| 26 | `ls … *cert*` | Certificate files |
| 27 | `sshd -T \| grep hostkey/cert/…` | Effective sshd (often root) |
| 28 | `ssh-keygen -L -f "$CERT"` | Full certificate parse |
| 29 | `ssh-keygen -L … \| grep Type/Valid/…` | CA, Valid, principals |
| 30 | `valid_to=…; days_left=…` | Days until expiry (GNU `date`) |

`ssh-copy-id` and key generation are not in the playbook. Tids 15/17 do not overwrite an existing `$KEY`.

`ssh-keygen -L` reads an OpenSSH cert (`-cert.pub`). If it is a regular key, the command will fail. `days_left` is computed from the `Valid: from … to …` line.

---

## scp (tid)

| tid | Command | Purpose |
|-----|---------|---------|
| 1 | `scp … "$SRC" "$REMOTE:$DEST"` | To the host |
| 2 | `scp … "$REMOTE:$SRC" "$DEST"` | From the host |
| 3 | `scp -P $PORT …` | Different port |
| 4 | `scp -r …` | Recursive |
| 5 | `scp -p …` | Preserve mtime/mode |
| 6 | `scp -v …` | Verbose |

Password in a TTY: `> scp …`. For large trees `!! rchk[1]` / rsync is more convenient.

---

## Playbooks

| Tag | Chain |
|-----|-------|
| `schk[1]` | `-G` → BatchMode `true` → keyscan |
| `ossh[1]` | `ssh -V` → `ssh -Q key` → files `*cert*` |
| `ocert[1]` | certificate summary → `days_left` |

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
