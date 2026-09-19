# Data handbook: PostgreSQL and Kafka

Tags **`pg`**, **`kf`**. Playbooks: `pgstat`, `kfstat` (inspect, no DROP/delete topic).

`psql` takes `$PGHOST` `$PGPORT` `$PGUSER` `$PGDATABASE` (libpq standard).
Kafka: `kcat` (also known as kafkacat) and the `kafka-topics` / `kafka-topics.sh` scripts.

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

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `pg_isready` | Server availability |
| 2 | `psql -c '\conninfo'` | Connection parameters |
| 3 | `psql -c 'SELECT version();'` | Version |
| 4 | `psql -c 'SELECT pg_is_in_recovery();'` | Replica? |
| 5 | `psql -c '\l'` | Databases |
| 6 | `psql -c '\dn'` | Schemas |
| 7 | `psql -c '\dt'` | Tables |
| 8 | `psql -c '\du'` | Roles |
| 9 | `psql … pg_stat_activity` | Active queries |
| 10 | `psql … pg_stat_database` | Load per database |
| 11 | `psql -c 'SELECT * FROM pg_stat_replication;'` | Replication |
| 12 | `psql … pg_database_size` | Current DB size |
| 13 | `psql … wait_event_type = Lock` | Lock waits |
| 14 | `systemctl status postgresql --no-pager` | postgresql unit |
| 15 | `journalctl -u postgresql -n 80 --no-pager` | unit journal |
| 16 | `psql` | Interactive (`> psql`) |

---

## kf — kafka (tid)

On some distributions the binaries have no `.sh`, on Confluent it is `kafka-topics.sh`. Both variants are in the seed.

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `kcat -b $BROKER -L` | Cluster metadata (kcat/kafkacat) |
| 2 | `kcat -b $BROKER -t $TOPIC -C -o -10 -e` | Last 10 messages |
| 3 | `kafka-topics --bootstrap-server $BROKER --list` | Topics |
| 4 | `kafka-topics … --describe --topic $TOPIC` | Describe `$TOPIC` |
| 5 | `kafka-topics … --describe` | All topics |
| 6 | `kafka-consumer-groups … --list` | Groups |
| 7 | `kafka-consumer-groups … --describe --group $GROUP` | Lag of `$GROUP` |
| 8 | `kafka-configs … --describe` | Topic config |
| 9 | `kafka-broker-api-versions …` | Broker availability |
| 10 | `kafka-topics.sh … --list` | Topics (Confluent) |

---

## Playbooks

| Tag | Chain |
|-----|---------|
| `pgstat[1]` | ready → version → recovery → activity |
| `kfstat[1]` | kcat `-L` → list topics |

```text
!! pgstat[1]
$TOPIC=events
!! kf[4]
$GROUP=workers
!! kf[7]
```
