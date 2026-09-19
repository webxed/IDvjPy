# HTTP handbook: curl, nginx, traefik

Tags **`curl`**, **`ngx`**, **`trf`**. Playbooks: `hchk`, `ngxstat`, `trfstat`.

The basic `curl -sI` already exists in the linux tag `net[3]` — this seed does not overwrite it.

```bash
python3 src/seed_http.py --seed
```

```text
$URL=https://example.com/
$HOST=app.example.com
$FILE=/etc/nginx/sites-enabled/default
$TRAEFIK_API=http://127.0.0.1:8080
$CTR=traefik
!! cvars[1]
```

---

## curl (tid)

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `curl -sI $URL` | Headers only |
| 2 | `curl -sv $URL` | Verbose (TLS, redirects) |
| 3 | `curl … -w '%{http_code} %{time_total}'` | Code and time |
| 4 | `curl -sS $URL` | Response body |
| 5 | `curl -sS -I -H "Host: $HOST" $URL` | Headers with Host |
| 6 | `curl -sS -H "Host: $HOST" $URL` | Body with Host (vhost) |
| 7 | `curl -sS -L $URL` | Follow redirects |
| 8 | `curl -sS --fail $URL` | Non-zero exit on HTTP ≥400 |
| 9 | `curl … --connect-timeout 3 --max-time 10` | Short timeout |
| 10 | `curl … -w dns/connect/tls/ttfb/total` | Timing breakdown |
| 11 | `curl … -X POST` | POST, code only |
| 12 | `curl -sS -kI $URL` | Headers, no TLS check |

---

## ngx — nginx (tid)

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `nginx -t` | Config check |
| 2 | `nginx -T` | Full config dump |
| 3 | `nginx -V` | Version and modules |
| 4 | `systemctl status nginx --no-pager` | Unit nginx |
| 5 | `journalctl -u nginx -n 80 --no-pager` | Journal unit |
| 6 | `ls -la /etc/nginx …` | Config directories |
| 7 | `cat /etc/nginx/nginx.conf` | Main config |
| 8 | `cat $FILE` | Site file `$FILE` |
| 9 | `ss -tlnp \| grep nginx` | nginx ports |
| 10 | `tail -n 50 /var/log/nginx/error.log` | error.log |
| 11 | `tail -n 50 /var/log/nginx/access.log` | access.log |
| 12 | `nginx -s reload` | Reload after successful `nginx -t` |

---

## trf — traefik (tid)

Default dashboard/API: `$TRAEFIK_API=http://127.0.0.1:8080` (port 8080/8082 depends on the static config).

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `traefik version` | Binary version |
| 2 | `curl -sS $TRAEFIK_API/ping` | Health ping API |
| 3 | `curl -sS $TRAEFIK_API/api/overview` | Overview |
| 4 | `curl -sS $TRAEFIK_API/api/http/routers` | HTTP routers |
| 5 | `curl -sS $TRAEFIK_API/api/http/services` | HTTP services |
| 6 | `curl -sS $TRAEFIK_API/api/http/middlewares` | Middlewares |
| 7 | `curl -sS $TRAEFIK_API/api/tcp/routers` | TCP routers |
| 8 | `ss -tlnp \| grep 80/443/8080` | Typical ports |
| 9 | `journalctl -u traefik -n 80 --no-pager` | Journal unit |
| 10 | `docker logs --tail=80 $CTR` | Logs of traefik container (`$CTR`) |
| 11 | `cat $FILE` | Static config `$FILE` |

---

## Playbooks

| Tag | Chain |
|-----|---------|
| `hchk[1]` | Headers + timings `$URL` |
| `ngxstat[1]` | `nginx -t` → status → error.log |
| `trfstat[1]` | ping → routers → services |

```text
$URL=https://app.example.com/health
!! hchk[1]
!! ngxstat[1]
```
