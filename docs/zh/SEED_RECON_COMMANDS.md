# DNS 与端口手册：dig、nmap

标签 **`dig`**、**`nmap`**。剧本：`dchk`（DNS）、`nchk`（ping + top 20 TCP）。

命令链中没有：`-p-`、`-A`、`--script`。只扫描你自己的主机。  
本次播种不会覆盖 Linux 标签 `net`。

nmap 设置了 `--host-timeout`，以免 TUI 卡死。

```bash
python3 src/seed_recon.py --seed
# 或与其他 ops 一起：
python3 src/seed_ops.py --seed
```

```text
$HOST=example.com
$PORT=443
$CIDR=192.168.1.0/24
$DNS=1.1.1.1
$IP=1.1.1.1
!! qvars[1]
```

---

## dig (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `dig $HOST` | 完整应答 |
| 2 | `dig +short $HOST` | 简短的 A/AAAA |
| 3 | `dig +short $HOST A` | A |
| 4 | `dig +short $HOST AAAA` | AAAA |
| 5 | `dig $HOST MX` | MX |
| 6 | `dig $HOST NS` | NS |
| 7 | `dig $HOST SOA` | SOA |
| 8 | `dig $HOST TXT` | TXT |
| 9 | `dig $HOST CNAME` | CNAME |
| 10 | `dig @$DNS $HOST` | 经 `$DNS` |
| 11 | `dig -x $IP` | PTR |
| 12 | `dig +trace $HOST` | 委派 |
| 13 | `dig +noall +answer $HOST` | 仅 answer |

---

## nmap (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `nmap -sn $HOST` | Ping 扫描 |
| 2 | `nmap -sT -Pn --top-ports 20 … $HOST` | TCP connect，top 20 |
| 3 | `nmap -sT -Pn -p $PORT $HOST` | 单个端口 |
| 4 | `nmap -sV -Pn -p $PORT $HOST` | 服务版本 |
| 5 | `nmap -sn $CIDR` | 网络 ping |
| 6 | `nmap -sT -Pn --reason -p $PORT $HOST` | 端口 + reason |
| 7 | `nmap -sU -Pn -p $PORT $HOST` | UDP（通常需 root） |
| 8 | `nmap -sS -Pn --top-ports 20 $HOST` | SYN（需 root） |

`-sT` 不需要 raw sockets。`-sS`/`-sU` —— 通常需要 root（若需要 TTY 则用 `> nmap …`）。

---

## 剧本

| 标签 | 命令链 |
|-----|---------|
| `dchk[1]` | `dig +short` → NS |
| `nchk[1]` | `-sn` → top 20 TCP |

```text
$HOST=example.com
!! dchk[1]
!! nchk[1]
$PORT=443
!! nmap[4]
```
