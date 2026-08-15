#!/usr/bin/env python3
"""
Seed the IDvjPy_term database with a canonical set of Linux commands.

Command order and tid mapping are defined in LINUX_COMMANDS.md.
Run:
  python3 seed_linux_commands.py --seed       # replace proc/file/net/kube
  python3 seed_linux_commands.py --comments   # fill empty command comments in place

Uses database_tags_file from settings.yml (same as app.py).
"""
import argparse
import os
import sys

try:
    import yaml
    import database_v2 as database
except ImportError as e:
    print(f"Error: {e}", file=sys.stderr)
    print("Install dependencies: pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)

FILE_SETTINGS = "settings.yml"
ENCODING = "utf-8"
DEFAULT_DB = "mytags.db"

# Порядок тегов: процессы → файлы → сеть → kubectl
TAG_COMMENTS = {
    "proc": "Процессы",
    "file": "Файлы и каталоги",
    "net": "Сеть",
    "kube": "Kubernetes (kubectl + tsh)",
    "logs": "Работа с логами",
}

# Команды по тегам (tid = 1, 2, 3…). Пара: (команда, комментарий).
SEED_COMMANDS = {
    "proc": [
        ("ps aux", "Список процессов"),
        ("top", "Интерактивный монитор процессов"),
        ("htop", "Удобный монитор (если установлен)"),
        ("kill", "Завершить процесс по PID"),
        ("killall", "Завершить по имени"),
        ("pkill", "Завершить по шаблону имени"),
        ("nohup", "Запуск, устойчивый к разрыву сессии"),
        ("jobs", "Список фоновых заданий оболочки"),
        ("fg", "Вернуть задание на передний план"),
        ("bg", "Продолжить в фоне"),
    ],
    "file": [
        ("ls -la", "Список файлов с деталями"),
        ("cp -r src dest", "Копирование рекурсивно"),
        ("mv src dest", "Перемещение или переименование"),
        ("rm -i", "Удаление с подтверждением"),
        ("mkdir -p", "Создать каталог и родителей"),
        ("rmdir", "Удалить пустой каталог"),
        ("touch", "Создать пустой файл / обновить время"),
        ("cat", "Вывести содержимое файла"),
        ("less", "Постраничный просмотр"),
        ("head", "Первые строки вывода"),
        ("tail -f", "Последние строки, следить за файлом"),
    ],
    "net": [
        ("ss -tulnp", "Сокеты (порты) TCP/UDP"),
        ("ping -c 3", "Проверка доступности хоста"),
        ("curl -sI", "HTTP-запрос, только заголовки"),
        ("wget -qO-", "Скачать в stdout"),
        ("ssh", "Подключение по SSH"),
        ("rsync -avz", "Синхронизация по сети"),
        ("scp", "Копирование через SSH"),
        ("ip addr", "Адреса интерфейсов"),
        ("ip route", "Таблица маршрутизации"),
    ],
    "kube": [
        ("tsh kube login CLUSTER", "Авторизация Teleport в Kubernetes-кластере"),
        ("kubectl config get-contexts", "Список kube context"),
        ("kubectl config current-context", "Текущий context"),
        ("kubectl cluster-info", "Информация о кластере"),
        ("kubectl get ns", "Список namespace"),
        ("kubectl get all -n $NS", "Все ресурсы в namespace $NS"),
        ("kubectl get pods -n $NS", "Поды в namespace $NS"),
        ("kubectl describe pod POD -n $NS", "Детали по pod"),
        ("kubectl logs POD -n $NS", "Логи pod"),
        ("kubectl logs -f POD -n $NS", "Логи pod (follow, лучше: > cmd)"),
        ("kubectl exec -it POD -n $NS -- sh", "Exec внутрь pod (лучше: > cmd)"),
        ("kubectl get deploy -n $NS", "Deployments в namespace $NS"),
        ("kubectl describe deploy DEPLOY -n $NS", "Детали по deployment"),
        ("kubectl rollout status deploy/DEPLOY -n $NS", "Статус rollout"),
        ("kubectl rollout restart deploy/DEPLOY -n $NS", "Рестарт rollout"),
        ("kubectl get svc -n $NS", "Services в namespace $NS"),
        ("kubectl port-forward svc/SVC 8080:80 -n $NS", "Port-forward на service"),
        ("kubectl apply -f FILE.yaml -n $NS", "Применить манифест в namespace $NS"),
        ("kubectl delete -f FILE.yaml -n $NS", "Удалить манифест в namespace $NS"),
    ],
}

# Комментарии к пользовательским tid, которых нет в каноническом сиде.
# (tag, tid) → comment. Не удаляются при --seed только если не входят в SEED_COMMANDS tags...
# --seed всё равно сотрёт file/net целиком; --comments обновляет на месте.
EXTRA_COMMENTS = {
    ("file", 12): "Все json-файлы текущего каталога",
    ("logs", 1): "Список файлов в /var/log",
    ("logs", 2): "Фильтр по *.log",
    ("logs", 3): "Последняя строка",
    ("logs", 4): "Печать / разделитель",
    ("logs", 5): "Число строк",
    ("logs", 6): "Пайп: ll /var/log → grep *.log → tail -n 1",
    ("net", 10): "Заглушка test",
    ("net", 11): "Заглушка test3",
}


def get_db_file():
    """Read database path from settings.yml, same logic as app.py."""
    if not os.path.exists(FILE_SETTINGS):
        return DEFAULT_DB
    try:
        with open(FILE_SETTINGS, "r", encoding=ENCODING) as f:
            settings = yaml.safe_load(f)
        if settings:
            return settings.get("database_tags_file", DEFAULT_DB)
    except Exception:
        pass
    return DEFAULT_DB


def hard_delete_commands_by_tag(db_file: str, tag: str) -> None:
    """Remove all rows for tag so new inserts get tid 1, 2, 3..."""
    conn = database.get_db_connection(db_file)
    conn.execute("DELETE FROM commands WHERE tag = ?", (tag,))
    conn.commit()
    conn.close()


def _seed_items(tag: str):
    for item in SEED_COMMANDS[tag]:
        if isinstance(item, tuple):
            yield item[0], item[1]
        else:
            yield item, ""


def run_seed(db_file: str) -> int:
    """(Re)seed seed tags: hard-delete then add commands in order."""
    database.init_db(db_file)
    n = 0
    for tag in SEED_COMMANDS:
        hard_delete_commands_by_tag(db_file, tag)
        for cmd, cmd_comment in _seed_items(tag):
            tid = database.add_command(db_file, cmd, tag)
            if cmd_comment:
                database.set_command_comment(db_file, tag, tid, cmd_comment)
            n += 1
        comment = TAG_COMMENTS.get(tag, "")
        if comment:
            database.set_tag_comment(db_file, tag, comment)
    return n


def apply_comments(db_file: str, only_empty: bool = True) -> int:
    """Set comments on existing rows; do not delete or insert commands."""
    database.init_db(db_file)
    updated = 0
    by_text = {}
    for tag in SEED_COMMANDS:
        for cmd, cmd_comment in _seed_items(tag):
            if cmd_comment:
                by_text[(tag, cmd)] = cmd_comment
        tag_comment = TAG_COMMENTS.get(tag, "")
        if tag_comment and (
            not only_empty or not database.get_tag_comment(db_file, tag)
        ):
            database.set_tag_comment(db_file, tag, tag_comment)
    logs_comment = TAG_COMMENTS.get("logs", "")
    if logs_comment and (
        not only_empty or not database.get_tag_comment(db_file, "logs")
    ):
        if database.get_commands_by_tag(db_file, "logs"):
            database.set_tag_comment(db_file, "logs", logs_comment)

    conn = database.get_db_connection(db_file)
    rows = conn.execute(
        "SELECT id, tag, tid, command, comment FROM commands WHERE deleted = 0"
    ).fetchall()
    conn.close()
    for row in rows:
        current = (row["comment"] or "").strip()
        if only_empty and current:
            continue
        wanted = by_text.get((row["tag"], row["command"])) or EXTRA_COMMENTS.get(
            (row["tag"], int(row["tid"]))
        )
        if not wanted or wanted == current:
            continue
        database.set_command_comment(db_file, row["tag"], int(row["tid"]), wanted)
        updated += 1
    return updated


def main():
    parser = argparse.ArgumentParser(
        description="Seed IDvjPy_term DB with Linux commands (see LINUX_COMMANDS.md)"
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Replace proc/file/net/kube with the canonical set (destroys extra tids)",
    )
    parser.add_argument(
        "--comments",
        action="store_true",
        help="Fill empty comments in place (keeps extra commands like logs/file[12])",
    )
    parser.add_argument(
        "--db",
        default="",
        help="SQLite file (default: settings.yml database_tags_file)",
    )
    args = parser.parse_args()
    if not args.seed and not args.comments:
        print("Run with --seed and/or --comments.", file=sys.stderr)
        sys.exit(0)
    db_file = args.db or get_db_file()
    if args.seed:
        n = run_seed(db_file)
        print(f"Seeded {len(SEED_COMMANDS)} tags ({n} commands) into {db_file}")
    if args.comments:
        n = apply_comments(db_file)
        print(f"Updated {n} command comment(s) in {db_file}")


if __name__ == "__main__":
    main()
