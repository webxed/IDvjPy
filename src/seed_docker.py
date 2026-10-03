#!/usr/bin/env python3
"""
Seed docker / compose handbook tags (see SEED_DOCKER_COMMANDS.md).

Does not touch proc / file / net / kube / k8s / git tags.

Run: python3 src/seed_docker.py --seed
"""
import sys

from seed_lib import run_seed as _run_seed
from seed_lib import seed_cli

SEED_TAGS = {
    "dvars": (
        "переменные docker",
        [
            (
                "echo image=$IMAGE container=$CTR svc=$SVC compose=$COMPOSE_FILE",
                "проверка $IMAGE/$CTR/…",
            ),
        ],
    ),
    "dck": (
        "docker: контейнеры, образы, логи",
        [
            ("docker ps", "запущенные контейнеры"),
            ("docker ps -a", "все контейнеры"),
            ("docker images", "образы"),
            ("docker logs --tail=100 $CTR", "логи $CTR"),
            ("docker inspect $CTR", "inspect контейнера"),
            ("docker stats --no-stream", "CPU/RAM без follow"),
            ("docker top $CTR", "процессы в $CTR"),
            ("docker exec $CTR sh -c 'ps aux'", "ps внутри (без TTY)"),
            ("docker pull $IMAGE", "скачать $IMAGE"),
            ("docker run --rm $IMAGE", "разовый запуск $IMAGE"),
            ("docker stop $CTR", "остановить $CTR"),
            ("docker start $CTR", "запустить $CTR"),
            ("docker restart $CTR", "перезапустить $CTR"),
            ("docker logs --tail=80 $CTR 2>&1 | grep -iE 'error|fatal|panic|oom'", "ошибки в логах"),
            ("docker network ls", "сети"),
            ("docker volume ls", "тома"),
            ("docker inspect $IMAGE", "inspect образа"),
            ("docker system df", "место образов/томов"),
            ("docker rm $CTR", "удалить остановленный $CTR"),
            ("docker rmi $IMAGE", "удалить образ $IMAGE"),
            ("docker exec -it $CTR sh", "shell в $CTR (лучше: > docker exec -it $CTR sh)"),
            (
                "docker inspect --format '{{json .State.Health}}' $CTR",
                "health-статус контейнера (JSON)",
            ),
            ("docker events --since 10m --until now", "события за последние 10 минут"),
            (
                "docker container ls --format 'table {{.Names}}\\t{{.Status}}\\t{{.Ports}}'",
                "таблица контейнеров (names/status/ports)",
            ),
            ("docker image inspect $IMAGE", "inspect образа (image config)"),
        ],
    ),
    "dcmp": (
        "docker compose",
        [
            ("docker compose ps", "сервисы compose (cwd)"),
            ("docker compose -f $COMPOSE_FILE ps", "сервисы, файл $COMPOSE_FILE"),
            ("docker compose config", "рендер конфига"),
            ("docker compose logs --tail=100", "логи всех сервисов"),
            ("docker compose logs --tail=100 $SVC", "логи сервиса $SVC"),
            ("docker compose pull", "обновить образы"),
            ("docker compose up -d", "поднять в фоне"),
            ("docker compose restart $SVC", "рестарт $SVC"),
            ("docker compose down", "остановить и убрать контейнеры"),
            ("docker compose exec $SVC sh", "exec в $SVC (лучше: > docker compose exec $SVC sh)"),
            ("docker-compose ps", "старый бинарь docker-compose"),
            (
                "docker compose config --quiet",
                "проверить конфиг (бесшумно, ошибки в код возврата)",
            ),
            ("docker compose ps --all", "все сервисы (включая остановленные)"),
        ],
    ),
    "dps": (
        "обзор docker",
        [
            (
                "!dck[1] ; echo '--- stats ---' ; !dck[6] ; echo '--- images ---' ; !dck[3]",
                "ps → stats → images",
            ),
        ],
    ),
    "dlog": (
        "логи контейнера",
        [
            (
                "!dck[4] ; echo '--- errors ---' ; !dck[14]",
                "logs + grep ошибок",
            ),
        ],
    ),
    "dcstat": (
        "обзор compose",
        [
            (
                "!dcmp[1] ; echo '--- config ---' ; !dcmp[3] ; echo '--- logs ---' ; !dcmp[4]",
                "ps → config → logs",
            ),
        ],
    ),
}


# Разметка канонических тегов (машинные токены, не переводятся; см. :tagmeta).
SEED_METADATA = {
    "dck": {
        "risk": "medium",
        "utilities": ["docker"],
        "os": ["linux", "macos"],
        "interactive": False,
        "topic": "containers",
        "example": "docker ps -a",
    },
    "dcmp": {
        "risk": "medium",
        "utilities": ["docker", "docker compose"],
        "os": ["linux", "macos"],
        "interactive": False,
        "topic": "compose",
        "example": "docker compose ps --all",
    },
}


def run_seed(db_file: str) -> int:
    return _run_seed(db_file, SEED_TAGS, metadata=SEED_METADATA)


def main() -> None:
    seed_cli(
        description="Seed IDvjPy_term DB with docker/compose handbook (SEED_DOCKER_COMMANDS.md)",
        seed_help="Replace dck/dcmp/dps/… (does not touch proc/file/net/kube/k*/git)",
        seed_tags=SEED_TAGS,
        argv=sys.argv,
    )


if __name__ == "__main__":
    main()
