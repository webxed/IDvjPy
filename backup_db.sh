#!/bin/bash
# One-button backup/restore over the CLI: `python3 backup_db.py backup|restore`.
# Usage: ./backup_db.sh [backup | restore <file.json|file.csv>]
#
# Вся логика — в `src/backup_db.py` (`backup` = снимок SQLite + JSON + CSV,
# `restore` = вернуть файл в базу со снимком до операции). Здесь только ярлык.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

action="${1:-backup}"

case "$action" in
    backup)
        exec python3 backup_db.py backup
        ;;
    restore)
        file="${2:-}"
        if [ -z "$file" ]; then
            echo "Usage: $0 restore <file.json|file.csv>" >&2
            echo "Файлы ищутся по имени в backups/ (см. \`python3 backup_db.py backup\`)." >&2
            exit 1
        fi
        exec python3 backup_db.py restore "$file"
        ;;
    *)
        echo "Usage: $0 [backup | restore <file.json|file.csv>]" >&2
        exit 1
        ;;
esac
