# IDvjPy HTTP 手册：curl、nginx、traefik

**`curl`**、**`ngx`**、**`trf`** 标签。playbook：`hchk`、`ngxstat`、`trfstat`。

基础的 `curl -sI` 已在 Linux 标签 `net[3]` 中 — 此种子不会覆盖它。

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

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `curl -sI $URL` | 仅响应头 |
| 2 | `curl -sv $URL` | 详细（TLS、重定向） |
| 3 | `curl … -w '%{http_code} %{time_total}'` | 状态码和耗时 |
| 4 | `curl -sS $URL` | 响应体 |
| 5 | `curl -sS -I -H "Host: $HOST" $URL` | 带头 Host |
| 6 | `curl -sS -H "Host: $HOST" $URL` | 带 Host 的响应体（vhost） |
| 7 | `curl -sS -L $URL` | 跟随重定向 |
| 8 | `curl -sS --fail $URL` | HTTP ≥400 时非零退出 |
| 9 | `curl … --connect-timeout 3 --max-time 10` | 短超时 |
| 10 | `curl … -w dns/connect/tls/ttfb/total` | 耗时分解 |
| 11 | `curl … -X POST` | POST，仅状态码 |
| 12 | `curl -sS -kI $URL` | 响应头，不校验证书 |

---

## ngx — nginx (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `nginx -t` | 配置检查 |
| 2 | `nginx -T` | 完整配置转储 |
| 3 | `nginx -V` | 版本和模块 |
| 4 | `systemctl status nginx --no-pager` | nginx unit |
| 5 | `journalctl -u nginx -n 80 --no-pager` | journal unit |
| 6 | `ls -la /etc/nginx …` | 配置目录 |
| 7 | `cat /etc/nginx/nginx.conf` | 主配置 |
| 8 | `cat $FILE` | 站点文件 `$FILE` |
| 9 | `ss -tlnp \| grep nginx` | nginx 端口 |
| 10 | `tail -n 50 /var/log/nginx/error.log` | error.log |
| 11 | `tail -n 50 /var/log/nginx/access.log` | access.log |
| 12 | `nginx -s reload` | `-t` 之后 reload |

---

## trf — traefik (tid)

默认 Dashboard/API：`$TRAEFIK_API=http://127.0.0.1:8080`（端口 8080/8082 取决于静态配置）。

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `traefik version` | 二进制版本 |
| 2 | `curl -sS $TRAEFIK_API/ping` | 健康 ping API |
| 3 | `curl -sS $TRAEFIK_API/api/overview` | 概览 |
| 4 | `curl -sS $TRAEFIK_API/api/http/routers` | HTTP 路由 |
| 5 | `curl -sS $TRAEFIK_API/api/http/services` | HTTP 服务 |
| 6 | `curl -sS $TRAEFIK_API/api/http/middlewares` | 中间件 |
| 7 | `curl -sS $TRAEFIK_API/api/tcp/routers` | TCP 路由 |
| 8 | `ss -tlnp \| grep 80/443/8080` | 典型端口 |
| 9 | `journalctl -u traefik -n 80 --no-pager` | journal unit |
| 10 | `docker logs --tail=80 $CTR` | traefik 容器日志（`$CTR`） |
| 11 | `cat $FILE` | 静态配置 `$FILE` |

---

## playbook

| 标签 | 命令链 |
|-----|---------|
| `hchk[1]` | `$URL` 的响应头 + 耗时 |
| `ngxstat[1]` | `nginx -t` → status → error.log |
| `trfstat[1]` | ping → 路由 → 服务 |

```text
$URL=https://app.example.com/health
!! hchk[1]
!! ngxstat[1]
```
