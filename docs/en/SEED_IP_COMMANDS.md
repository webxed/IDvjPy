# ip / ethtool handbook for IDvjPy

Tags **`ip`**, **`eth`**. Inspect playbooks: `ilink`, `iiface`.  
`ip link set` / `addr add` / `route add` — manual only.

Does not touch the linux tag `net` (`ip addr` / `ip route` remain in the linux core).

```bash
python3 src/seed_ip.py --seed
# or together with the other ops:
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

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `ip -br link` | Interfaces, brief |
| 2 | `ip -br addr` | Addresses, brief |
| 3 | `ip link show $IFACE` | Link `$IFACE` |
| 4 | `ip addr show $IFACE` | Addresses of `$IFACE` |
| 5 | `ip -s link show $IFACE` | Counters |
| 6 | `ip -s -s link show $IFACE` | Counters, detailed |
| 7 | `ip route` | IPv4 routes |
| 8 | `ip -6 route` | IPv6 |
| 9 | `ip route show default` | Default |
| 10 | `ip neigh` | ARP / NDISC |
| 11 | `ip neigh show dev $IFACE` | Neigh `$IFACE` |
| 12 | `ip -4 addr` | IPv4 |
| 13 | `ip -6 addr` | IPv6 |
| 14 | `ip rule` | Policy routing |
| 15 | `ip netns list` | Netns |
| 16 | `ip link set $IFACE up` | Bring up (changes NIC) |
| 17 | `ip link set $IFACE down` | Bring down |
| 18 | `ip addr add $ADDR dev $IFACE` | Add address |
| 19 | `ip route add default via $GW` | Default via `$GW` |

Tid 16–19 are not in the playbooks.

---

## eth — ethtool (tid)

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `ethtool $IFACE` | Speed / duplex |
| 2 | `ethtool -i $IFACE` | Driver |
| 3 | `ethtool -k $IFACE` | Offload |
| 4 | `ethtool -S $IFACE \| head -n 40` | Statistics |
| 5 | `ethtool --show-ring $IFACE` | Ring |

---

## Playbooks

| Tag | Chain |
|-----|---------|
| `ilink[1]` | `ip -br link` → `-br addr` → `route` |
| `iiface[1]` | link `$IFACE` → `-s` → `ethtool -i` |

```text
!! ilink[1]
$IFACE=eth0
!! iiface[1]
```
