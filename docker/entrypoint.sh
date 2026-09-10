#!/bin/sh
# Демостенд IDvjPy_term: подготовить data-каталог, один раз наполнить библиотеку
# тегов и запустить TUI. Аргументы пробрасываются в app.py, например:
#   docker compose run --rm idvjpy --demo short --demo-quit
set -eu

APP_DIR="${IDVJPY_APP_DIR:-/app}"
DATA_DIR="${IDVJPY_DATA_DIR:-/data}"

cd "$DATA_DIR"

# Первый запуск в пустом томе: личные файлы создаются из шаблонов — ровно так,
# как приложение делает это в обычном data-каталоге (см. src/settings.example.yml).
if [ ! -f settings.yml ]; then
    cp "$APP_DIR/src/settings.example.yml" settings.yml
    echo "[demo] settings.yml ← src/settings.example.yml"
fi
if [ ! -f llm_providers.yml ]; then
    cp "$APP_DIR/src/llm_providers.example.yml" llm_providers.yml
    echo "[demo] llm_providers.yml ← src/llm_providers.example.yml"
fi

has_live_commands() {
    python3 -c '
import sys
sys.path.insert(0, sys.argv[1])
import database_v2 as db
from seed_lib import get_db_file
try:
    live = db.has_live_commands(get_db_file())
except Exception:  # пустой файл без схемы — считаем, что библиотеки нет
    live = False
raise SystemExit(0 if live else 1)
' "$APP_DIR/src"
}

# Библиотека тегов: сеем один раз, чтобы `?`, `??` и `!tag[tid]` сразу было что
# показать. Повторный запуск ничего не пересобирает (и не плодит бэкапы).
if has_live_commands; then
    :
else
    # Посев сам делает снимки БД перед заменой тегов (защита от потери).
    # В стартовом состоянии демо терять нечего (БД пустая, в снимках — только
    # что залитые нами seed-теги), поэтому если папки снимков до нас не было,
    # убираем её — иначе первый запуск выглядит как «после инцидента».
    if [ -d backups ]; then
        had_backups=yes
    else
        had_backups=no
    fi
    echo "[demo] наполняю библиотеку тегов (linux, k8s, git, ops) — один раз"
    for seed in seed_linux_commands seed_k8s_chains seed_git seed_ops; do
        python3 "$APP_DIR/src/$seed.py" --seed >/dev/null
    done
    if [ "$had_backups" = no ]; then
        rm -rf backups   # backup_dir: backups (settings.yml)
    fi
    live=$(python3 -c '
import sys
sys.path.insert(0, sys.argv[1])
import database_v2 as db
from seed_lib import get_db_file
print(db.usage_stats(get_db_file())["live"])
' "$APP_DIR/src")
    echo "[demo] готово: $live команд. Начните с :?   ?   ??   !tag[tid]   :q"
fi

exec python3 "$APP_DIR/app.py" "$@"
