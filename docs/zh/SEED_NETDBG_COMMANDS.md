# L4/L7 网络手册：tcpdump、nc、mtr、TLS

标签 **`pcap`**、**`ncat`**、**`hops`**、**`tls`**。剧本：`npath`、`tlschk`。  
抓包有上限：`timeout 8` 和 `tcpdump -c $COUNT`。剧本中不做无限 dump。

不改动 linux 的 `net`、`ss`、nmap/dig。

```bash
python3 src/seed_netdbg.py --seed
# 或与其他 ops 一起：
python3 src/seed_ops.py --seed
```

```text
$HOST=example.com
$PORT=443
$IFACE=any
$SNI=example.com
$COUNT=20
!! ndvars[1]
!! npath[1]
!! tlschk[1]
```

tcpdump 和部分 openssl 通常需要 root。`> tcpdump` / `> openssl s_client` / `> mtr` —— 交互式。

---

## pcap — tcpdump (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `timeout 8 tcpdump -nn -c $COUNT -i $IFACE` | 最多 `$COUNT` 个包 |
| 2 | `… port $PORT` | 端口 `$PORT` |
| 3 | `… host $HOST` | 主机 `$HOST` |
| 4 | `… SYN` | 仅 SYN |
| 5 | `tcpdump -nn -i $IFACE` | Follow（最好用 `>`） |

Tid 5 不放入剧本。

---

## ncat — nc (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `nc -vz $HOST $PORT` | TCP connect |
| 2 | `timeout 5 nc -vz -w 3 $HOST $PORT` | 带超时 |
| 3 | `timeout 5 nc -vzu -w 3 $HOST $PORT` | UDP |
| 4 | `nc -vz $HOST 80 443 $PORT` | 多个端口 |

---

## hops — traceroute / mtr (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `traceroute -n $HOST` | 不解析 DNS |
| 2 | `traceroute -n -T -p $PORT $HOST` | TCP SYN |
| 3 | `tracepath $HOST` | tracepath |
| 4 | `mtr -c $COUNT -r -n $HOST` | Report，N 个循环 |
| 5 | `mtr -c $COUNT -r -n -T -P $PORT $HOST` | mtr TCP |
| 6 | `> mtr $HOST` | 交互式 |

---

## tls — openssl (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `openssl s_client … -brief` | 握手 |
| 2 | `… \| openssl x509 -dates` | 日期/subject |
| 3 | `… \| openssl x509 -text \| head` | x509 text |
| 4 | `openssl version` | 版本 |
| 5 | `> openssl s_client …` | 交互式 |

---

## 剧本

| 标签 | 命令链 |
|-----|---------|
| `npath[1]` | `nc -vz` → traceroute → `mtr -r` |
| `tlschk[1]` | s_client -brief → x509 dates |
