# Справочник HTTP: curl, nginx, traefik

Теги **`curl`**, **`ngx`**, **`trf`**. Плейбуки: `hchk`, `ngxstat`, `trfstat`.

Базовый `curl -sI` уже есть в linux-теге `net[3]` — этот сид его не затирает.

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

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `curl -sI $URL` | Заголовки |
| 2 | `curl -sv $URL` | Verbose |
| 3 | `curl … -w '%{http_code} %{time_total}'` | Код и время |
| 4 | `curl -sS $URL` | Тело |
| 5 | `curl -sS -I -H "Host: $HOST" $URL` | Заголовки vhost |
| 6 | `curl -sS -H "Host: $HOST" $URL` | Тело vhost |
| 7 | `curl -sS -L $URL` | Редиректы |
| 8 | `curl -sS --fail $URL` | Fail на ≥400 |
| 9 | `curl … --connect-timeout 3 --max-time 10` | Короткий таймаут |
| 10 | `curl … -w dns/connect/tls/ttfb/total` | Тайминги |
| 11 | `curl … -X POST` | POST, только код |
| 12 | `curl -sS -kI $URL` | Без проверки TLS |

---

## ngx — nginx (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `nginx -t` | Проверка конфига |
| 2 | `nginx -T` | Дамп конфига |
| 3 | `nginx -V` | Версия и модули |
| 4 | `systemctl status nginx --no-pager` | Unit |
| 5 | `journalctl -u nginx -n 80 --no-pager` | Журнал |
| 6 | `ls -la /etc/nginx …` | Каталоги |
| 7 | `cat /etc/nginx/nginx.conf` | Главный конфиг |
| 8 | `cat $FILE` | Файл сайта |
| 9 | `ss -tlnp \| grep nginx` | Порты |
| 10 | `tail -n 50 /var/log/nginx/error.log` | error.log |
| 11 | `tail -n 50 /var/log/nginx/access.log` | access.log |
| 12 | `nginx -s reload` | Reload после `-t` |

---

## trf — traefik (tid)

Dashboard/API по умолчанию: `$TRAEFIK_API=http://127.0.0.1:8080` (порт 8080/8082 зависит от static config).

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `traefik version` | Версия |
| 2 | `curl -sS $TRAEFIK_API/ping` | Ping |
| 3 | `curl -sS $TRAEFIK_API/api/overview` | Overview |
| 4 | `curl -sS $TRAEFIK_API/api/http/routers` | Routers |
| 5 | `curl -sS $TRAEFIK_API/api/http/services` | Services |
| 6 | `curl -sS $TRAEFIK_API/api/http/middlewares` | Middlewares |
| 7 | `curl -sS $TRAEFIK_API/api/tcp/routers` | TCP routers |
| 8 | `ss -tlnp \| grep 80/443/8080` | Порты |
| 9 | `journalctl -u traefik -n 80 --no-pager` | Unit |
| 10 | `docker logs --tail=80 $CTR` | Логи контейнера |
| 11 | `cat $FILE` | Static config |

---

## Плейбуки

| Тег | Цепочка |
|-----|---------|
| `hchk[1]` | заголовки + тайминги `$URL` |
| `ngxstat[1]` | `nginx -t` → status → error.log |
| `trfstat[1]` | ping → routers → services |

```text
$URL=https://app.example.com/health
!! hchk[1]
!! ngxstat[1]
```
