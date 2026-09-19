# 套接字与 firewall 手册：ss、netstat、iptables、nftables、firewalld

标签 **`ss`**、**`nst`**（netstat）、**`ipt`**、**`nft`**、**`fwd`**（firewall-cmd）。
运行手册**仅做检查**：没有 `iptables -F`、`nft flush`、`--panic-on`、`policy DROP`。

linux 标签 `net`（`ss -tulnp`、`curl -sI`）本种子不会覆盖。

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

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `ss -tulnp` | Listen TCP/UDP + 进程 |
| 2 | `ss -tlnp` | TCP listen |
| 3 | `ss -ulnp` | UDP listen |
| 4 | `ss -s` | 摘要 |
| 5 | `ss -tnp state established` | Established |
| 6 | `ss -tnp state time-wait` | TIME-WAIT |
| 7 | `ss -tnp sport = :$PORT` | 本地 `$PORT` |
| 8 | `ss -tnp dport = :$PORT` | 远程 `$PORT` |
| 9 | `ss -xlnp` | UNIX listen |
| 10 | `ss -tuln \| grep $PORT` | 端口过滤 |

---

## nst — netstat (tid)

适用于没有 `ss` 的主机（或出于习惯）。

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `netstat -tulnp` | Listen + 进程 |
| 2 | `netstat -tlnp` | TCP listen |
| 3 | `netstat -s` | 协议栈统计 |
| 4 | `netstat -i` | 接口 |
| 5 | `netstat -rn` | 路由 |
| 6 | `netstat -tpn` | TCP + PID |

---

## ipt — iptables (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `iptables -L -n -v --line-numbers` | filter |
| 2 | `iptables -t nat -L -n -v --line-numbers` | nat |
| 3 | `iptables -t mangle -L -n -v --line-numbers` | mangle |
| 4 | `iptables -S` | filter，以 `-A` 形式 |
| 5 | `iptables -t nat -S` | nat，以 `-A` 形式 |
| 6 | `iptables -L INPUT …` | INPUT |
| 7 | `iptables -L FORWARD …` | FORWARD |
| 8 | `iptables-save` | 完整转储 |
| 9 | `ip6tables -L -n -v --line-numbers` | IPv6 |
| 10 | `iptables -C INPUT -p tcp --dport $PORT -j ACCEPT` | 是否存在 ACCEPT |

添加/删除规则 —— 手动进行，不来自运行手册。

---

## nft — nftables (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `nft list tables` | 表 |
| 2 | `nft list ruleset` | 整个 ruleset |
| 3 | `nft -a list ruleset` | 带 handle |
| 4 | `nft list table inet filter` | inet filter |
| 5 | `nft list table ip nat` | ip nat |
| 6 | `nft list chain inet filter input` | input |

标签中没有 `flush` / `delete`。

---

## fwd — firewall-cmd (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `firewall-cmd --state` | 是否运行？ |
| 2 | `firewall-cmd --get-active-zones` | 区域 |
| 3 | `firewall-cmd --get-default-zone` | 默认 zone |
| 4 | `firewall-cmd --list-all` | 当前区域 |
| 5 | `firewall-cmd --list-all-zones` | 所有区域 |
| 6 | `firewall-cmd --zone=$ZONE --list-all` | 区域 `$ZONE` |
| 7 | `firewall-cmd --zone=$ZONE --list-ports` | 端口 |
| 8 | `firewall-cmd --zone=$ZONE --list-services` | 服务 |
| 9 | `firewall-cmd --query-port=$PORT/tcp` | 端口是否开放 |
| 10 | `firewall-cmd --permanent --list-all` | Permanent |
| 11 | `firewall-cmd --add-port=$PORT/tcp` | 开放 runtime |
| 12 | `firewall-cmd --permanent --add-port=$PORT/tcp` | 开放 permanent |
| 13 | `firewall-cmd --reload` | 应用 permanent |

`11`–`13` 会修改防火墙 —— 不在运行手册中。

---

## 运行手册

| 标签 | 命令链 |
|-----|---------|
| `nstat[1]` | `ss -tulnp` + 摘要 |
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
