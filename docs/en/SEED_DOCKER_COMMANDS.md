# docker / compose handbook for IDvjPy

Tags **`dck`** (docker) and **`dcmp`** (compose). Playbooks: `dps`, `dlog`, `dcstat`.

Interactive exec uses the `>` prefix (a real TTY).
Do not put into an auto-chain: `docker system prune`, `rm -f`, `compose down -v`.

```bash
python3 src/seed_docker.py --seed
# or all ops handbooks at once:
python3 src/seed_ops.py --seed
```

Does not touch `proc` / `file` / `net` / `kube` / k8s / git.

```text
$IMAGE=
$CTR=
$SVC=
$COMPOSE_FILE=compose.yaml
!! dvars[1]
```

---

## dck — docker (tid)

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `docker ps` | Running containers |
| 2 | `docker ps -a` | All containers |
| 3 | `docker images` | Images |
| 4 | `docker logs --tail=100 $CTR` | Logs of `$CTR` |
| 5 | `docker inspect $CTR` | Inspect a container |
| 6 | `docker stats --no-stream` | CPU/RAM without follow |
| 7 | `docker top $CTR` | Processes in `$CTR` |
| 8 | `docker exec $CTR sh -c 'ps aux'` | ps inside (no TTY) |
| 9 | `docker pull $IMAGE` | Pull `$IMAGE` |
| 10 | `docker run --rm $IMAGE` | One-off run of `$IMAGE` |
| 11 | `docker stop $CTR` | Stop `$CTR` |
| 12 | `docker start $CTR` | Start `$CTR` |
| 13 | `docker restart $CTR` | Restart `$CTR` |
| 14 | `docker logs … \| grep error` | Errors in logs |
| 15 | `docker network ls` | Networks |
| 16 | `docker volume ls` | Volumes |
| 17 | `docker inspect $IMAGE` | Inspect an image |
| 18 | `docker system df` | Images/volumes disk usage |
| 19 | `docker rm $CTR` | Remove a stopped `$CTR` |
| 20 | `docker rmi $IMAGE` | Remove image `$IMAGE` |
| 21 | `docker exec -it $CTR sh` | Shell in `$CTR` (better: `> docker exec -it $CTR sh`) |

---

## dcmp — compose (tid)

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `docker compose ps` | Compose services (cwd) |
| 2 | `docker compose -f $COMPOSE_FILE ps` | Services, file `$COMPOSE_FILE` |
| 3 | `docker compose config` | Render config |
| 4 | `docker compose logs --tail=100` | Logs of all services |
| 5 | `docker compose logs --tail=100 $SVC` | Logs of service `$SVC` |
| 6 | `docker compose pull` | Update images |
| 7 | `docker compose up -d` | Bring up in background |
| 8 | `docker compose restart $SVC` | Restart `$SVC` |
| 9 | `docker compose down` | Stop and remove containers |
| 10 | `docker compose exec $SVC sh` | Exec in `$SVC` (better: `> docker compose exec $SVC sh`) |
| 11 | `docker-compose ps` | Old docker-compose binary |

---

## Playbooks

| Tag | Chain |
|-----|---------|
| `dps[1]` | ps → stats → images |
| `dlog[1]` | logs `$CTR` → grep for errors |
| `dcstat[1]` | ps → config → logs |

```text
!! dps[1]
$CTR=web
!! dlog[1]
!! dcstat[1]
```
