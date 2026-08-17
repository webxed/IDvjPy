# Справочник данных: PostgreSQL и Kafka

Теги **`pg`**, **`kf`**. Плейбуки: `pgstat`, `kfstat` (осмотр, без DROP/delete topic).

`psql` берёт `$PGHOST` `$PGPORT` `$PGUSER` `$PGDATABASE` (стандарт libpq).
Kafka: `kcat` (он же kafkacat) и скрипты `kafka-topics` / `kafka-topics.sh`.

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

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `pg_isready` | Доступен ли сервер |
| 2 | `psql -c '\conninfo'` | Параметры соединения |
| 3 | `psql -c 'SELECT version();'` | Версия |
| 4 | `psql -c 'SELECT pg_is_in_recovery();'` | Replica? |
| 5 | `psql -c '\l'` | Базы |
| 6 | `psql -c '\dn'` | Схемы |
| 7 | `psql -c '\dt'` | Таблицы |
| 8 | `psql -c '\du'` | Роли |
| 9 | `psql … pg_stat_activity` | Активные запросы |
| 10 | `psql … pg_stat_database` | Нагрузка по БД |
| 11 | `psql -c 'SELECT * FROM pg_stat_replication;'` | Репликация |
| 12 | `psql … pg_database_size` | Размер текущей БД |
| 13 | `psql … wait_event_type = Lock` | Блокировки |
| 14 | `systemctl status postgresql --no-pager` | Unit |
| 15 | `journalctl -u postgresql -n 80 --no-pager` | Журнал |
| 16 | `psql` | Интерактив (`> psql`) |

---

## kf — kafka (tid)

На одних дистрибутивах бинари без `.sh`, на Confluent — `kafka-topics.sh`. Оба варианта в сиде.

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `kcat -b $BROKER -L` | Метаданные |
| 2 | `kcat -b $BROKER -t $TOPIC -C -o -10 -e` | Последние 10 сообщений |
| 3 | `kafka-topics --bootstrap-server $BROKER --list` | Топики |
| 4 | `kafka-topics … --describe --topic $TOPIC` | Описать `$TOPIC` |
| 5 | `kafka-topics … --describe` | Все топики |
| 6 | `kafka-consumer-groups … --list` | Groups |
| 7 | `kafka-consumer-groups … --describe --group $GROUP` | Лаг `$GROUP` |
| 8 | `kafka-configs … --describe` | Конфиг топика |
| 9 | `kafka-broker-api-versions …` | Доступность брокера |
| 10 | `kafka-topics.sh … --list` | Топики (Confluent) |

---

## Плейбуки

| Тег | Цепочка |
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
