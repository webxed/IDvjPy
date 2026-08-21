# Справочник сети L4/L7: tcpdump, nc, mtr, TLS

Теги **`pcap`**, **`ncat`**, **`hops`**, **`tls`**. Плейбуки: `npath`, `tlschk`.  
Захват ограничен: `timeout 8` и `tcpdump -c $COUNT`. Без бесконечного dump в плейбуке.

Не трогает linux `net`, `ss`, nmap/dig.

```bash
python3 src/seed_netdbg.py --seed
# или вместе с остальными ops:
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

tcpdump и часть openssl часто нужен root. `> tcpdump` / `> openssl s_client` / `> mtr` — интерактив.

---

## pcap — tcpdump (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `timeout 8 tcpdump -nn -c $COUNT -i $IFACE` | До `$COUNT` пакетов |
| 2 | `… port $PORT` | Порт `$PORT` |
| 3 | `… host $HOST` | Хост `$HOST` |
| 4 | `… SYN` | Только SYN |
| 5 | `tcpdump -nn -i $IFACE` | Follow (лучше `>`) |

Tid 5 не в плейбуке.

---

## ncat — nc (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `nc -vz $HOST $PORT` | TCP connect |
| 2 | `timeout 5 nc -vz -w 3 $HOST $PORT` | С таймаутом |
| 3 | `timeout 5 nc -vzu -w 3 $HOST $PORT` | UDP |
| 4 | `nc -vz $HOST 80 443 $PORT` | Несколько портов |

---

## hops — traceroute / mtr (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `traceroute -n $HOST` | Без DNS |
| 2 | `traceroute -n -T -p $PORT $HOST` | TCP SYN |
| 3 | `tracepath $HOST` | tracepath |
| 4 | `mtr -c $COUNT -r -n $HOST` | Report, N циклов |
| 5 | `mtr -c $COUNT -r -n -T -P $PORT $HOST` | mtr TCP |
| 6 | `> mtr $HOST` | Интерактив |

---

## tls — openssl (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `openssl s_client … -brief` | Handshake |
| 2 | `… \| openssl x509 -dates` | Даты/subject |
| 3 | `… \| openssl x509 -text \| head` | x509 text |
| 4 | `openssl version` | Версия |
| 5 | `> openssl s_client …` | Интерактив |

---

## Плейбуки

| Тег | Цепочка |
|-----|---------|
| `npath[1]` | `nc -vz` → traceroute → `mtr -r` |
| `tlschk[1]` | s_client -brief → x509 dates |
