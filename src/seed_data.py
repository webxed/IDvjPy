#!/usr/bin/env python3
"""
Seed postgres + kafka handbook tags (see SEED_DATA_COMMANDS.md).

Run: python3 src/seed_data.py --seed
"""
import sys

from seed_lib import run_seed as _run_seed
from seed_lib import seed_cli

SEED_TAGS = {
    "pgvars": (
        "переменные postgres (libpq)",
        [
            (
                "echo pghost=$PGHOST pgport=$PGPORT pguser=$PGUSER db=$PGDATABASE",
                "проверка libpq-переменных",
            ),
        ],
    ),
    "pg": (
        "postgres: статус, сессии, размер",
        [
            ("pg_isready", "доступен ли сервер"),
            ("psql -c '\\conninfo'", "параметры соединения"),
            ("psql -c 'SELECT version();'", "версия"),
            ("psql -c 'SELECT pg_is_in_recovery();'", "replica?"),
            ("psql -c '\\l'", "базы"),
            ("psql -c '\\dn'", "схемы"),
            ("psql -c '\\dt'", "таблицы"),
            ("psql -c '\\du'", "роли"),
            (
                "psql -c \"SELECT pid, usename, state, wait_event_type, left(query,80) "
                "AS query FROM pg_stat_activity WHERE state <> 'idle' "
                "ORDER BY query_start;\"",
                "активные запросы",
            ),
            (
                "psql -c \"SELECT datname, numbackends, xact_commit, blks_hit, blks_read "
                "FROM pg_stat_database ORDER BY numbackends DESC;\"",
                "нагрузка по базам",
            ),
            ("psql -c 'SELECT * FROM pg_stat_replication;'", "репликация"),
            (
                "psql -c \"SELECT pg_size_pretty(pg_database_size(current_database())) "
                "AS db_size;\"",
                "размер текущей БД",
            ),
            (
                "psql -c \"SELECT pid, usename, wait_event_type, wait_event, left(query,80) "
                "FROM pg_stat_activity WHERE wait_event_type = 'Lock';\"",
                "ожидание блокировок",
            ),
            ("systemctl status postgresql --no-pager", "unit postgresql"),
            ("journalctl -u postgresql -n 80 --no-pager", "журнал unit"),
            ("psql", "интерактивный psql (лучше: > psql)"),
        ],
    ),
    "kfvars": (
        "переменные kafka",
        [
            (
                "echo broker=$BROKER topic=$TOPIC group=$GROUP",
                "проверка $BROKER/$TOPIC/…",
            ),
        ],
    ),
    "kf": (
        "kafka: топики, группы, kcat",
        [
            ("kcat -b $BROKER -L", "метаданные кластера (kcat/kafkacat)"),
            (
                "kcat -b $BROKER -t $TOPIC -C -o -10 -e",
                "последние 10 сообщений $TOPIC и выход",
            ),
            ("kafka-topics --bootstrap-server $BROKER --list", "список топиков"),
            (
                "kafka-topics --bootstrap-server $BROKER --describe --topic $TOPIC",
                "описать $TOPIC",
            ),
            ("kafka-topics --bootstrap-server $BROKER --describe", "все топики подробно"),
            ("kafka-consumer-groups --bootstrap-server $BROKER --list", "consumer groups"),
            (
                "kafka-consumer-groups --bootstrap-server $BROKER --describe --group $GROUP",
                "лаг группы $GROUP",
            ),
            (
                "kafka-configs --bootstrap-server $BROKER --entity-type topics "
                "--entity-name $TOPIC --describe",
                "конфиг топика $TOPIC",
            ),
            (
                "kafka-broker-api-versions --bootstrap-server $BROKER",
                "API брокера (доступность)",
            ),
            (
                "kafka-topics.sh --bootstrap-server $BROKER --list",
                "топики (скрипт Confluent .sh)",
            ),
        ],
    ),
    "pgstat": (
        "обзор postgres",
        [
            (
                "!pg[1] ; echo '--- version ---' ; !pg[3] ; echo '--- recovery ---' ; "
                "!pg[4] ; echo '--- activity ---' ; !pg[9]",
                "ready → version → replica? → activity",
            ),
        ],
    ),
    "kfstat": (
        "обзор kafka",
        [
            (
                "!kf[1] ; echo '--- topics ---' ; !kf[3]",
                "kcat metadata → list topics",
            ),
        ],
    ),
}


def run_seed(db_file: str) -> int:
    return _run_seed(db_file, SEED_TAGS)


def main() -> None:
    seed_cli(
        description="Seed IDvjPy_term DB with postgres/kafka handbook (SEED_DATA_COMMANDS.md)",
        seed_help="Replace pg/kf/pgstat/… (does not touch proc/net/kube)",
        seed_tags=SEED_TAGS,
        argv=sys.argv,
    )


if __name__ == "__main__":
    main()
