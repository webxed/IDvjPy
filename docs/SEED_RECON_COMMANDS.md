# Справочник DNS и портов: dig, nmap

Теги **`dig`**, **`nmap`**. Плейбуки: `dchk` (DNS), `nchk` (ping + top 20 TCP).

Нет в цепочках: `-p-`, `-A`, `--script`. Сканируйте только свои хосты.  
Linux-тег `net` этот сид не затирает.

`--host-timeout` стоит у nmap, чтобы TUI не завис.

```bash
python3 src/seed_recon.py --seed
# или вместе с остальными ops:
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

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `dig $HOST` | Полный ответ |
| 2 | `dig +short $HOST` | Короткий A/AAAA |
| 3 | `dig +short $HOST A` | A |
| 4 | `dig +short $HOST AAAA` | AAAA |
| 5 | `dig $HOST MX` | MX |
| 6 | `dig $HOST NS` | NS |
| 7 | `dig $HOST SOA` | SOA |
| 8 | `dig $HOST TXT` | TXT |
| 9 | `dig $HOST CNAME` | CNAME |
| 10 | `dig @$DNS $HOST` | Через `$DNS` |
| 11 | `dig -x $IP` | PTR |
| 12 | `dig +trace $HOST` | Делегирование |
| 13 | `dig +noall +answer $HOST` | Только answer |

---

## nmap (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `nmap -sn $HOST` | Ping-scan |
| 2 | `nmap -sT -Pn --top-ports 20 … $HOST` | TCP connect, top 20 |
| 3 | `nmap -sT -Pn -p $PORT $HOST` | Один порт |
| 4 | `nmap -sV -Pn -p $PORT $HOST` | Версия сервиса |
| 5 | `nmap -sn $CIDR` | Ping сети |
| 6 | `nmap -sT -Pn --reason -p $PORT $HOST` | Порт + reason |
| 7 | `nmap -sU -Pn -p $PORT $HOST` | UDP (часто root) |
| 8 | `nmap -sS -Pn --top-ports 20 $HOST` | SYN (нужен root) |

`-sT` не требует raw sockets. `-sS`/`-sU` — обычно root (`> nmap …` если нужен TTY).

---

## Плейбуки

| Тег | Цепочка |
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
