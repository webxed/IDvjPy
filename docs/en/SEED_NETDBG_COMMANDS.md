# Network handbook L4/L7: tcpdump, nc, mtr, TLS

Tags **`pcap`**, **`ncat`**, **`hops`**, **`tls`**. Playbooks: `npath`, `tlschk`.  
Capture is bounded: `timeout 8` and `tcpdump -c $COUNT`. No infinite dump in the playbook.

Does not touch linux `net`, `ss`, nmap/dig.

```bash
python3 src/seed_netdbg.py --seed
# or together with the other ops:
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

tcpdump and part of openssl often need root. `> tcpdump` / `> openssl s_client` / `> mtr` — interactive.

---

## pcap — tcpdump (tid)

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `timeout 8 tcpdump -nn -c $COUNT -i $IFACE` | Up to `$COUNT` packets |
| 2 | `… port $PORT` | Port `$PORT` |
| 3 | `… host $HOST` | Host `$HOST` |
| 4 | `… SYN` | SYN only |
| 5 | `tcpdump -nn -i $IFACE` | Follow (better `>`) |

Tid 5 is not in the playbook.

---

## ncat — nc (tid)

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `nc -vz $HOST $PORT` | TCP connect |
| 2 | `timeout 5 nc -vz -w 3 $HOST $PORT` | With a timeout |
| 3 | `timeout 5 nc -vzu -w 3 $HOST $PORT` | UDP |
| 4 | `nc -vz $HOST 80 443 $PORT` | Several ports |

---

## hops — traceroute / mtr (tid)

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `traceroute -n $HOST` | Without DNS |
| 2 | `traceroute -n -T -p $PORT $HOST` | TCP SYN |
| 3 | `tracepath $HOST` | tracepath |
| 4 | `mtr -c $COUNT -r -n $HOST` | Report, N cycles |
| 5 | `mtr -c $COUNT -r -n -T -P $PORT $HOST` | mtr TCP |
| 6 | `> mtr $HOST` | Interactive |

---

## tls — openssl (tid)

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `openssl s_client … -brief` | Handshake |
| 2 | `… \| openssl x509 -dates` | Dates/subject |
| 3 | `… \| openssl x509 -text \| head` | x509 text |
| 4 | `openssl version` | Version |
| 5 | `> openssl s_client …` | Interactive |

---

## Playbooks

| Tag | Chain |
|-----|---------|
| `npath[1]` | `nc -vz` → traceroute → `mtr -r` |
| `tlschk[1]` | s_client -brief → x509 dates |
