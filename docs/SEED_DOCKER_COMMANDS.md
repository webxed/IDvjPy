# Справочник docker / compose для IDvjPy

Теги **`dck`** (docker) и **`dcmp`** (compose). Плейбуки: `dps`, `dlog`, `dcstat`.

Интерактивный exec — с префиксом `>` (настоящий TTY).
Не класть в автоцепочку: `docker system prune`, `rm -f`, `compose down -v`.  
`docker events --since 10m --until now` — конечный срез событий (без `--follow`).

```bash
python3 src/seed_docker.py --seed
# или сразу все ops-справочники:
python3 src/seed_ops.py --seed
```

Не трогает `proc` / `file` / `net` / `kube` / k8s / git.

```text
$IMAGE=
$CTR=
$SVC=
$COMPOSE_FILE=compose.yaml
!! dvars[1]
```

---

## dck — docker (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `docker ps` | Запущенные |
| 2 | `docker ps -a` | Все контейнеры |
| 3 | `docker images` | Образы |
| 4 | `docker logs --tail=100 $CTR` | Логи `$CTR` |
| 5 | `docker inspect $CTR` | Inspect контейнера |
| 6 | `docker stats --no-stream` | CPU/RAM |
| 7 | `docker top $CTR` | Процессы |
| 8 | `docker exec $CTR sh -c 'ps aux'` | ps внутри |
| 9 | `docker pull $IMAGE` | Pull |
| 10 | `docker run --rm $IMAGE` | Разовый запуск |
| 11 | `docker stop $CTR` | Stop |
| 12 | `docker start $CTR` | Start |
| 13 | `docker restart $CTR` | Restart |
| 14 | `docker logs … \| grep error` | Ошибки в логах |
| 15 | `docker network ls` | Сети |
| 16 | `docker volume ls` | Тома |
| 17 | `docker inspect $IMAGE` | Inspect образа |
| 18 | `docker system df` | Место |
| 19 | `docker rm $CTR` | Удалить контейнер |
| 20 | `docker rmi $IMAGE` | Удалить образ |
| 21 | `docker exec -it $CTR sh` | Shell (`> docker exec -it $CTR sh`) |
| 22 | `docker inspect --format '{{json .State.Health}}' $CTR` | Health-статус (JSON) |
| 23 | `docker events --since 10m --until now` | События за 10 минут |
| 24 | `docker container ls --format 'table …'` | Таблица names/status/ports |
| 25 | `docker image inspect $IMAGE` | Inspect образа (config) |

---

## dcmp — compose (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `docker compose ps` | Сервисы (cwd) |
| 2 | `docker compose -f $COMPOSE_FILE ps` | Файл `$COMPOSE_FILE` |
| 3 | `docker compose config` | Рендер конфига |
| 4 | `docker compose logs --tail=100` | Логи всех |
| 5 | `docker compose logs --tail=100 $SVC` | Логи `$SVC` |
| 6 | `docker compose pull` | Обновить образы |
| 7 | `docker compose up -d` | Up |
| 8 | `docker compose restart $SVC` | Restart `$SVC` |
| 9 | `docker compose down` | Down (без `-v`) |
| 10 | `docker compose exec $SVC sh` | Exec (`> …`) |
| 11 | `docker-compose ps` | Старый бинарь |
| 12 | `docker compose config --quiet` | Проверка конфига (код возврата) |
| 13 | `docker compose ps --all` | Все сервисы (включая остановленные) |

---

## Плейбуки

| Тег | Цепочка |
|-----|---------|
| `dps[1]` | ps → stats → images |
| `dlog[1]` | logs `$CTR` → grep ошибок |
| `dcstat[1]` | compose ps → config → logs |

```text
!! dps[1]
$CTR=web
!! dlog[1]
!! dcstat[1]
```
