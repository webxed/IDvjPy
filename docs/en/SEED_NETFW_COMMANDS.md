# Sockets and firewall handbook: ss, netstat, iptables, nftables, firewalld

Tags **`ss`**, **`nst`** (netstat), **`ipt`**, **`nft`**, **`fwd`** (firewall-cmd).
Playbooks **inspection only**: no `iptables -F`, `nft flush`, `--panic-on`, `policy DROP`.

The linux tag `net` (`ss -tulnp`, `curl -sI`) is not overwritten by this seed.

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

| tid | Command | Purpose |
|-----|---------|---------|
| 1 | `ss -tulnp` | Listen TCP/UDP + processes |
| 2 | `ss -tlnp` | TCP listen |
| 3 | `ss -ulnp` | UDP listen |
| 4 | `ss -s` | Summary |
| 5 | `ss -tnp state established` | Established |
| 6 | `ss -tnp state time-wait` | TIME-WAIT |
| 7 | `ss -tnp sport = :$PORT` | Local `$PORT` |
| 8 | `ss -tnp dport = :$PORT` | Remote `$PORT` |
| 9 | `ss -xlnp` | UNIX listen |
| 10 | `ss -tuln \| grep $PORT` | Port filter |

---

## nst — netstat (tid)

For hosts without `ss` (or with the habit).

| tid | Command | Purpose |
|-----|---------|---------|
| 1 | `netstat -tulnp` | Listen + processes |
| 2 | `netstat -tlnp` | TCP listen |
| 3 | `netstat -s` | Stack statistics |
| 4 | `netstat -i` | Interfaces |
| 5 | `netstat -rn` | Routes |
| 6 | `netstat -tpn` | TCP + PID |

---

## ipt — iptables (tid)

| tid | Command | Purpose |
|-----|---------|---------|
| 1 | `iptables -L -n -v --line-numbers` | filter |
| 2 | `iptables -t nat -L -n -v --line-numbers` | nat |
| 3 | `iptables -t mangle -L -n -v --line-numbers` | mangle |
| 4 | `iptables -S` | filter as `-A` |
| 5 | `iptables -t nat -S` | nat as `-A` |
| 6 | `iptables -L INPUT …` | INPUT |
| 7 | `iptables -L FORWARD …` | FORWARD |
| 8 | `iptables-save` | Full dump |
| 9 | `ip6tables -L -n -v --line-numbers` | IPv6 |
| 10 | `iptables -C INPUT -p tcp --dport $PORT -j ACCEPT` | Is there an ACCEPT |

Adding/removing rules — by hand, not from the playbook.

---

## nft — nftables (tid)

| tid | Command | Purpose |
|-----|---------|---------|
| 1 | `nft list tables` | Tables |
| 2 | `nft list ruleset` | Whole ruleset |
| 3 | `nft -a list ruleset` | With handle |
| 4 | `nft list table inet filter` | inet filter |
| 5 | `nft list table ip nat` | ip nat |
| 6 | `nft list chain inet filter input` | input |

No `flush` / `delete` in the tag.

---

## fwd — firewall-cmd (tid)

| tid | Command | Purpose |
|-----|---------|---------|
| 1 | `firewall-cmd --state` | Running? |
| 2 | `firewall-cmd --get-active-zones` | Zones |
| 3 | `firewall-cmd --get-default-zone` | Default zone |
| 4 | `firewall-cmd --list-all` | Current zone |
| 5 | `firewall-cmd --list-all-zones` | All zones |
| 6 | `firewall-cmd --zone=$ZONE --list-all` | Zone `$ZONE` |
| 7 | `firewall-cmd --zone=$ZONE --list-ports` | Ports |
| 8 | `firewall-cmd --zone=$ZONE --list-services` | Services |
| 9 | `firewall-cmd --query-port=$PORT/tcp` | Is the port open |
| 10 | `firewall-cmd --permanent --list-all` | Permanent |
| 11 | `firewall-cmd --add-port=$PORT/tcp` | Open runtime |
| 12 | `firewall-cmd --permanent --add-port=$PORT/tcp` | Open permanent |
| 13 | `firewall-cmd --reload` | Apply permanent |

`11`–`13` change the firewall — not in the playbook.

---

## Playbooks

| Tag | Chain |
|-----|-------|
| `nstat[1]` | `ss -tulnp` + summary |
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
