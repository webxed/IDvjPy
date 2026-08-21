# Справочник ip / ethtool для IDvjPy

Теги **`ip`**, **`eth`**. Плейбуки осмотра: `ilink`, `iiface`.  
`ip link set` / `addr add` / `route add` — только руками.

Не трогает linux-тег `net` (`ip addr` / `ip route` в ядре linux остаются).

```bash
python3 src/seed_ip.py --seed
# или вместе с остальными ops:
python3 src/seed_ops.py --seed
```

```text
$IFACE=eth0
$ADDR=192.168.1.10/24
$GW=192.168.1.1
!! ipvars[1]
```

---

## ip (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `ip -br link` | Интерфейсы кратко |
| 2 | `ip -br addr` | Адреса кратко |
| 3 | `ip link show $IFACE` | Link `$IFACE` |
| 4 | `ip addr show $IFACE` | Адреса `$IFACE` |
| 5 | `ip -s link show $IFACE` | Счётчики |
| 6 | `ip -s -s link show $IFACE` | Счётчики подробно |
| 7 | `ip route` | Маршруты IPv4 |
| 8 | `ip -6 route` | IPv6 |
| 9 | `ip route show default` | Default |
| 10 | `ip neigh` | ARP / NDISC |
| 11 | `ip neigh show dev $IFACE` | Neigh `$IFACE` |
| 12 | `ip -4 addr` | IPv4 |
| 13 | `ip -6 addr` | IPv6 |
| 14 | `ip rule` | Policy routing |
| 15 | `ip netns list` | Netns |
| 16 | `ip link set $IFACE up` | Поднять (меняет NIC) |
| 17 | `ip link set $IFACE down` | Опустить |
| 18 | `ip addr add $ADDR dev $IFACE` | Добавить адрес |
| 19 | `ip route add default via $GW` | Default via `$GW` |

В плейбуках нет tid 16–19.

---

## eth — ethtool (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `ethtool $IFACE` | Speed / duplex |
| 2 | `ethtool -i $IFACE` | Драйвер |
| 3 | `ethtool -k $IFACE` | Offload |
| 4 | `ethtool -S $IFACE \| head -n 40` | Статистика |
| 5 | `ethtool --show-ring $IFACE` | Ring |

---

## Плейбуки

| Тег | Цепочка |
|-----|---------|
| `ilink[1]` | `ip -br link` → `-br addr` → `route` |
| `iiface[1]` | link `$IFACE` → `-s` → `ethtool -i` |

```text
!! ilink[1]
$IFACE=eth0
!! iiface[1]
```
