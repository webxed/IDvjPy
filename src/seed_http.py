#!/usr/bin/env python3
"""
Seed HTTP handbook: curl, nginx, traefik (see SEED_HTTP_COMMANDS.md).

Does not touch the linux `net` tag (basic curl -sI stays there).

Run: python3 src/seed_http.py --seed
"""
import sys

from seed_lib import run_seed as _run_seed
from seed_lib import seed_cli

SEED_TAGS = {
    "cvars": (
        "переменные HTTP",
        [
            (
                "echo url=$URL host=$HOST file=$FILE api=$TRAEFIK_API",
                "проверка $URL/$HOST/…",
            ),
        ],
    ),
    "curl": (
        "curl: заголовки, тайминги, Host",
        [
            ("curl -sI $URL", "только заголовки"),
            ("curl -sv $URL", "verbose (TLS, редиректы)"),
            (
                "curl -sS -o /dev/null -w '%{http_code} %{time_total}\\n' $URL",
                "код и время",
            ),
            ("curl -sS $URL", "тело ответа"),
            ("curl -sS -I -H \"Host: $HOST\" $URL", "заголовки с Host"),
            ("curl -sS -H \"Host: $HOST\" $URL", "тело с Host (vhost)"),
            ("curl -sS -L $URL", "следовать редиректам"),
            ("curl -sS --fail $URL", "ненулевой exit на HTTP ≥400"),
            ("curl -sS --connect-timeout 3 --max-time 10 $URL", "короткий таймаут"),
            (
                "curl -sS -o /dev/null -w "
                "'dns=%{time_namelookup} connect=%{time_connect} "
                "tls=%{time_appconnect} ttfb=%{time_starttransfer} "
                "total=%{time_total} code=%{http_code}\\n' $URL",
                "разбивка таймингов",
            ),
            ("curl -sS -o /dev/null -w '%{http_code}\\n' -X POST $URL", "POST, только код"),
            ("curl -sS -kI $URL", "заголовки, без проверки TLS"),
        ],
    ),
    "ngx": (
        "nginx: конфиг, статус, логи",
        [
            ("nginx -t", "проверка конфига"),
            ("nginx -T", "полный дамп конфига"),
            ("nginx -V", "версия и модули"),
            ("systemctl status nginx --no-pager", "unit nginx"),
            ("journalctl -u nginx -n 80 --no-pager", "журнал unit"),
            ("ls -la /etc/nginx /etc/nginx/conf.d /etc/nginx/sites-enabled", "каталоги конфига"),
            ("cat /etc/nginx/nginx.conf", "главный конфиг"),
            ("cat $FILE", "файл сайта $FILE"),
            ("ss -tlnp | grep nginx", "порты nginx"),
            ("tail -n 50 /var/log/nginx/error.log", "error.log"),
            ("tail -n 50 /var/log/nginx/access.log", "access.log"),
            ("nginx -s reload", "reload после удачного nginx -t"),
        ],
    ),
    "trf": (
        "traefik: API, роутеры, логи",
        [
            ("traefik version", "версия бинаря"),
            ("curl -sS $TRAEFIK_API/ping", "health ping API"),
            ("curl -sS $TRAEFIK_API/api/overview", "overview"),
            ("curl -sS $TRAEFIK_API/api/http/routers", "HTTP routers"),
            ("curl -sS $TRAEFIK_API/api/http/services", "HTTP services"),
            ("curl -sS $TRAEFIK_API/api/http/middlewares", "middlewares"),
            ("curl -sS $TRAEFIK_API/api/tcp/routers", "TCP routers"),
            ("ss -tlnp | grep -E ':80|:443|:8080|:8082'", "типичные порты"),
            ("journalctl -u traefik -n 80 --no-pager", "журнал unit"),
            ("docker logs --tail=80 $CTR", "логи контейнера traefik ($CTR)"),
            ("cat $FILE", "статический конфиг $FILE"),
        ],
    ),
    "hchk": (
        "проверка URL",
        [
            (
                "!curl[1] ; echo '--- timing ---' ; !curl[10]",
                "заголовки + тайминги",
            ),
        ],
    ),
    "ngxstat": (
        "обзор nginx",
        [
            (
                "!ngx[1] ; echo '--- status ---' ; !ngx[4] ; echo '--- errors ---' ; !ngx[10]",
                "nginx -t → status → error.log",
            ),
        ],
    ),
    "trfstat": (
        "обзор traefik",
        [
            (
                "!trf[2] ; echo '--- routers ---' ; !trf[4] ; echo '--- services ---' ; !trf[5]",
                "ping → routers → services",
            ),
        ],
    ),
}


def run_seed(db_file: str) -> int:
    return _run_seed(db_file, SEED_TAGS)


def main() -> None:
    seed_cli(
        description="Seed IDvjPy_term DB with curl/nginx/traefik handbook (SEED_HTTP_COMMANDS.md)",
        seed_help="Replace curl/ngx/trf/… (does not touch net/proc/kube)",
        seed_tags=SEED_TAGS,
        argv=sys.argv,
    )


if __name__ == "__main__":
    main()
