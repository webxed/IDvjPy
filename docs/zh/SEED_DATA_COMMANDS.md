# IDvjPy 数据手册：PostgreSQL 和 Kafka

**`pg`**、**`kf`** 标签。playbook：`pgstat`、`kfstat`（检查，不做 DROP/delete topic）。

`psql` 读取 `$PGHOST` `$PGPORT` `$PGUSER` `$PGDATABASE`（libpq 标准）。
Kafka：`kcat`（即 kafkacat）和脚本 `kafka-topics` / `kafka-topics.sh`。

```bash
python3 src/seed_data.py --seed
```

```text
$PGHOST=127.0.0.1
$PGPORT=5432
$PGUSER=postgres
$PGDATABASE=postgres
$BROKER=127.0.0.1:9092
$TOPIC=
$GROUP=
!! pgvars[1]
!! kfvars[1]
```

---

## pg — postgres (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `pg_isready` | 服务器可用性 |
| 2 | `psql -c '\conninfo'` | 连接参数 |
| 3 | `psql -c 'SELECT version();'` | 版本 |
| 4 | `psql -c 'SELECT pg_is_in_recovery();'` | 是否副本? |
| 5 | `psql -c '\l'` | 数据库 |
| 6 | `psql -c '\dn'` | schema |
| 7 | `psql -c '\dt'` | 表 |
| 8 | `psql -c '\du'` | 角色 |
| 9 | `psql … pg_stat_activity` | 活动查询 |
| 10 | `psql … pg_stat_database` | 每个数据库的负载 |
| 11 | `psql -c 'SELECT * FROM pg_stat_replication;'` | 复制 |
| 12 | `psql … pg_database_size` | 当前 DB 大小 |
| 13 | `psql … wait_event_type = Lock` | 锁等待 |
| 14 | `systemctl status postgresql --no-pager` | unit postgresql |
| 15 | `journalctl -u postgresql -n 80 --no-pager` | unit 日志 |
| 16 | `psql` | 交互式 psql（更好: `> psql`） |

---

## kf — kafka (tid)

有些发行版的可执行文件不带 `.sh`，Confluent 上则是 `kafka-topics.sh`。种子里两种都有。

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `kcat -b $BROKER -L` | 集群元数据（kcat/kafkacat） |
| 2 | `kcat -b $BROKER -t $TOPIC -C -o -10 -e` | `$TOPIC` 的最近 10 条消息，然后退出 |
| 3 | `kafka-topics --bootstrap-server $BROKER --list` | 列出 topic |
| 4 | `kafka-topics … --describe --topic $TOPIC` | 描述 `$TOPIC` |
| 5 | `kafka-topics … --describe` | 所有 topic 详情 |
| 6 | `kafka-consumer-groups … --list` | 消费者组 |
| 7 | `kafka-consumer-groups … --describe --group $GROUP` | 组 `$GROUP` 的延迟 |
| 8 | `kafka-configs … --describe` | topic `$TOPIC` 的配置 |
| 9 | `kafka-broker-api-versions …` | broker API（可用性） |
| 10 | `kafka-topics.sh … --list` | topic（Confluent .sh 脚本） |

---

## playbook

| 标签 | 命令链 |
|-----|---------|
| `pgstat[1]` | ready → 版本 → 是否副本? → 活动 |
| `kfstat[1]` | kcat `-L` → 列出 topic |

```text
!! pgstat[1]
$TOPIC=events
!! kf[4]
$GROUP=workers
!! kf[7]
```
