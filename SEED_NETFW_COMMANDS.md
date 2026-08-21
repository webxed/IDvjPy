# Справочник сокетов и firewall: ss, netstat, iptables, nftables, firewalld

Теги **`ss`**, **`nst`** (netstat), **`ipt`**, **`nft`**, **`fwd`** (firewall-cmd).
Плейбуки **только осмотр**: нет `iptables -F`, `nft flush`, `--panic-on`, `policy DROP`.

Linux-тег `net` (`ss -tulnp`, `curl -sI`) этот сид не затирает.

```bash
python3 src/seed_netfw.py --seed
```

```text
$PORT=443
$ZONE=public
$PROTO=tcp
!! nvars[1]
```

---

## ss (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `ss -tulnp` | Listen TCP/UDP + процессы |
| 2 | `ss -tlnp` | TCP listen |
| 3 | `ss -ulnp` | UDP listen |
| 4 | `ss -s` | Сводка |
| 5 | `ss -tnp state established` | Established |
| 6 | `ss -tnp state time-wait` | TIME-WAIT |
| 7 | `ss -tnp sport = :$PORT` | Локальный `$PORT` |
| 8 | `ss -tnp dport = :$PORT` | Удалённый `$PORT` |
| 9 | `ss -xlnp` | UNIX listen |
| 10 | `ss -tuln \| grep $PORT` | Фильтр порта |

---

## nst — netstat (tid)

Для хостов без `ss` (или привычки).

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `netstat -tulnp` | Listen + процессы |
| 2 | `netstat -tlnp` | TCP listen |
| 3 | `netstat -s` | Статистика стека |
| 4 | `netstat -i` | Интерфейсы |
| 5 | `netstat -rn` | Маршруты |
| 6 | `netstat -tpn` | TCP + PID |

---

## ipt — iptables (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `iptables -L -n -v --line-numbers` | filter |
| 2 | `iptables -t nat -L -n -v --line-numbers` | nat |
| 3 | `iptables -t mangle -L -n -v --line-numbers` | mangle |
| 4 | `iptables -S` | filter как `-A` |
| 5 | `iptables -t nat -S` | nat как `-A` |
| 6 | `iptables -L INPUT …` | INPUT |
| 7 | `iptables -L FORWARD …` | FORWARD |
| 8 | `iptables-save` | Полный дамп |
| 9 | `ip6tables -L -n -v --line-numbers` | IPv6 |
| 10 | `iptables -C INPUT -p tcp --dport $PORT -j ACCEPT` | Есть ли ACCEPT |

Добавление/удаление правил — руками, не из плейбука.

---

## nft — nftables (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `nft list tables` | Таблицы |
| 2 | `nft list ruleset` | Весь ruleset |
| 3 | `nft -a list ruleset` | С handle |
| 4 | `nft list table inet filter` | inet filter |
| 5 | `nft list table ip nat` | ip nat |
| 6 | `nft list chain inet filter input` | input |

Нет `flush` / `delete` в теге.

---

## fwd — firewall-cmd (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `firewall-cmd --state` | Запущен? |
| 2 | `firewall-cmd --get-active-zones` | Зоны |
| 3 | `firewall-cmd --get-default-zone` | Default zone |
| 4 | `firewall-cmd --list-all` | Текущая зона |
| 5 | `firewall-cmd --list-all-zones` | Все зоны |
| 6 | `firewall-cmd --zone=$ZONE --list-all` | Зона `$ZONE` |
| 7 | `firewall-cmd --zone=$ZONE --list-ports` | Порты |
| 8 | `firewall-cmd --zone=$ZONE --list-services` | Сервисы |
| 9 | `firewall-cmd --query-port=$PORT/tcp` | Открыт ли порт |
| 10 | `firewall-cmd --permanent --list-all` | Permanent |
| 11 | `firewall-cmd --add-port=$PORT/tcp` | Открыть runtime |
| 12 | `firewall-cmd --permanent --add-port=$PORT/tcp` | Открыть permanent |
| 13 | `firewall-cmd --reload` | Применить permanent |

`11`–`13` меняют firewall — не в плейбуке.

---

## Плейбуки

| Тег | Цепочка |
|-----|---------|
| `nstat[1]` | `ss -tulnp` + сводка |
| `iptstat[1]` | filter + nat |
| `nftstat[1]` | tables → list ruleset |
| `fwstat[1]` | state → zones → list-all |

```text
!! nstat[1]
$PORT=22
!! ss[7]
!! nftstat[1]
!! fwstat[1]
```
