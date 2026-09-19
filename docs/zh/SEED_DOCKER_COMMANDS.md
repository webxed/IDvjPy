# 面向 IDvjPy 的 docker / compose 手册

标签 **`dck`**（docker）和 **`dcmp`**（compose）。剧本：`dps`、`dlog`、`dcstat`。

交互式 exec —— 需加 `>` 前缀（真正的 TTY）。
不要放入自动命令链：`docker system prune`、`rm -f`、`compose down -v`。

```bash
python3 src/seed_docker.py --seed
# 或一次性播种所有 ops 手册：
python3 src/seed_ops.py --seed
```

不改动 `proc` / `file` / `net` / `kube` / k8s / git。

```text
$IMAGE=
$CTR=
$SVC=
$COMPOSE_FILE=compose.yaml
!! dvars[1]
```

---

## dck — docker (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `docker ps` | 运行中 |
| 2 | `docker ps -a` | 所有容器 |
| 3 | `docker images` | 镜像 |
| 4 | `docker logs --tail=100 $CTR` | `$CTR` 的日志 |
| 5 | `docker inspect $CTR` | 检查容器 |
| 6 | `docker stats --no-stream` | CPU/RAM |
| 7 | `docker top $CTR` | 进程 |
| 8 | `docker exec $CTR sh -c 'ps aux'` | 容器内的 ps |
| 9 | `docker pull $IMAGE` | 拉取 |
| 10 | `docker run --rm $IMAGE` | 一次性运行 |
| 11 | `docker stop $CTR` | 停止 |
| 12 | `docker start $CTR` | 启动 |
| 13 | `docker restart $CTR` | 重启 |
| 14 | `docker logs … \| grep error` | 日志中的错误 |
| 15 | `docker network ls` | 网络 |
| 16 | `docker volume ls` | 数据卷 |
| 17 | `docker inspect $IMAGE` | 检查镜像 |
| 18 | `docker system df` | 占用空间 |
| 19 | `docker rm $CTR` | 删除容器 |
| 20 | `docker rmi $IMAGE` | 删除镜像 |
| 21 | `docker exec -it $CTR sh` | Shell（`> docker exec -it $CTR sh`） |

---

## dcmp — compose (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `docker compose ps` | 服务（cwd） |
| 2 | `docker compose -f $COMPOSE_FILE ps` | 文件 `$COMPOSE_FILE` |
| 3 | `docker compose config` | 渲染配置 |
| 4 | `docker compose logs --tail=100` | 全部日志 |
| 5 | `docker compose logs --tail=100 $SVC` | `$SVC` 的日志 |
| 6 | `docker compose pull` | 更新镜像 |
| 7 | `docker compose up -d` | 启动 |
| 8 | `docker compose restart $SVC` | 重启 `$SVC` |
| 9 | `docker compose down` | 停止（不带 `-v`） |
| 10 | `docker compose exec $SVC sh` | Exec（`> …`） |
| 11 | `docker-compose ps` | 旧版二进制 |

---

## 剧本

| 标签 | 命令链 |
|-----|---------|
| `dps[1]` | ps → stats → images |
| `dlog[1]` | logs `$CTR` → grep 错误 |
| `dcstat[1]` | compose ps → config → logs |

```text
!! dps[1]
$CTR=web
!! dlog[1]
!! dcstat[1]
```
