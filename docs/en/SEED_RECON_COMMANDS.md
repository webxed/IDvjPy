# DNS and ports handbook: dig, nmap

Tags **`dig`**, **`nmap`**. Playbooks: `dchk` (DNS), `nchk` (ping + top 20 TCP).

Not in the chains: `-p-`, `-A`, `--script`. Scan only your own hosts.  
This seed does not overwrite the linux tag `net`.

`--host-timeout` is set on nmap so the TUI does not hang.

```bash
python3 src/seed_recon.py --seed
# or together with the other ops:
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

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `dig $HOST` | Full answer |
| 2 | `dig +short $HOST` | Short A/AAAA |
| 3 | `dig +short $HOST A` | A |
| 4 | `dig +short $HOST AAAA` | AAAA |
| 5 | `dig $HOST MX` | MX |
| 6 | `dig $HOST NS` | NS |
| 7 | `dig $HOST SOA` | SOA |
| 8 | `dig $HOST TXT` | TXT |
| 9 | `dig $HOST CNAME` | CNAME |
| 10 | `dig @$DNS $HOST` | Via `$DNS` |
| 11 | `dig -x $IP` | PTR |
| 12 | `dig +trace $HOST` | Delegation |
| 13 | `dig +noall +answer $HOST` | Answer only |

---

## nmap (tid)

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `nmap -sn $HOST` | Ping-scan |
| 2 | `nmap -sT -Pn --top-ports 20 … $HOST` | TCP connect, top 20 |
| 3 | `nmap -sT -Pn -p $PORT $HOST` | Single port |
| 4 | `nmap -sV -Pn -p $PORT $HOST` | Service version |
| 5 | `nmap -sn $CIDR` | Network ping |
| 6 | `nmap -sT -Pn --reason -p $PORT $HOST` | Port + reason |
| 7 | `nmap -sU -Pn -p $PORT $HOST` | UDP (often root) |
| 8 | `nmap -sS -Pn --top-ports 20 $HOST` | SYN (needs root) |

`-sT` does not require raw sockets. `-sS`/`-sU` — usually root (`> nmap …` if a TTY is needed).

---

## Playbooks

| Tag | Chain |
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
