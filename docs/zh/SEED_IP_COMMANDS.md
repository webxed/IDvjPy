# 面向 IDvjPy 的 ip / ethtool 手册

标签 **`ip`**、**`eth`**。检查类剧本：`ilink`、`iiface`。  
`ip link set` / `addr add` / `route add` —— 只能手动执行。

不改动 linux 标签 `net`（`ip addr` / `ip route` 仍保留在 linux 内核标签中）。

```bash
python3 src/seed_ip.py --seed
# 或与其他 ops 一起：
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

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `ip -br link` | 接口简表 |
| 2 | `ip -br addr` | 地址简表 |
| 3 | `ip link show $IFACE` | `$IFACE` 的 link |
| 4 | `ip addr show $IFACE` | `$IFACE` 的地址 |
| 5 | `ip -s link show $IFACE` | 计数器 |
| 6 | `ip -s -s link show $IFACE` | 计数器详情 |
| 7 | `ip route` | IPv4 路由 |
| 8 | `ip -6 route` | IPv6 |
| 9 | `ip route show default` | 默认 |
| 10 | `ip neigh` | ARP / NDISC |
| 11 | `ip neigh show dev $IFACE` | `$IFACE` 的 neigh |
| 12 | `ip -4 addr` | IPv4 |
| 13 | `ip -6 addr` | IPv6 |
| 14 | `ip rule` | 策略路由 |
| 15 | `ip netns list` | Netns |
| 16 | `ip link set $IFACE up` | 启用（修改 NIC） |
| 17 | `ip link set $IFACE down` | 停用 |
| 18 | `ip addr add $ADDR dev $IFACE` | 添加地址 |
| 19 | `ip route add default via $GW` | 经 `$GW` 的默认路由 |

剧本中没有 tid 16–19。

---

## eth — ethtool (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `ethtool $IFACE` | Speed / duplex |
| 2 | `ethtool -i $IFACE` | 驱动 |
| 3 | `ethtool -k $IFACE` | Offload |
| 4 | `ethtool -S $IFACE \| head -n 40` | 统计 |
| 5 | `ethtool --show-ring $IFACE` | Ring |

---

## 剧本

| 标签 | 命令链 |
|-----|---------|
| `ilink[1]` | `ip -br link` → `-br addr` → `route` |
| `iiface[1]` | link `$IFACE` → `-s` → `ethtool -i` |

```text
!! ilink[1]
$IFACE=eth0
!! iiface[1]
```
