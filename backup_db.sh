#!/bin/bash
# Quick backup/restore script for IDvjPy_term database
# Usage: ./backup_db.sh [backup|restore] [timestamp]
#   backup  - create backups (default)
#   restore - restore from backups
#   timestamp - optional backup timestamp for restore (e.g., 20260130_191855)

# Get current timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Base directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Parse command line arguments
ACTION=${1:-backup}
RESTORE_TIMESTAMP=${2:-$TIMESTAMP}

if [ "$ACTION" = "backup" ]; then
    echo "=== Creating backups ==="
    echo ""

    # Backup to JSON
    echo "Creating JSON backup..."
    python3 backup_db.py export "backup_${TIMESTAMP}.json"

    # Backup to CSV
    echo "Creating CSV backups..."
    python3 backup_db.py export-csv "commands_${TIMESTAMP}.csv"
    python3 backup_db.py export-tags-csv "tags_${TIMESTAMP}.csv"

    echo ""
    echo "=== Backup complete ==="
    echo "Files created in backups/:"
    echo "  - backup_${TIMESTAMP}.json"
    echo "  - commands_${TIMESTAMP}.csv"
    echo "  - tags_${TIMESTAMP}.csv"
    echo ""
    echo "To restore:"
    echo "  ./backup_db.sh restore ${TIMESTAMP}"

elif [ "$ACTION" = "restore" ]; then
    # Find backup files
    JSON_FILE=$(ls backups/backup_${RESTORE_TIMESTAMP}.json 2>/dev/null)
    CSV_FILE=$(ls backups/commands_${RESTORE_TIMESTAMP}.csv 2>/dev/null)
    TAGS_FILE=$(ls backups/tags_${RESTORE_TIMESTAMP}.csv 2>/dev/null)

    if [ -z "$JSON_FILE" ] && [ -z "$CSV_FILE" ]; then
        echo "Error: No backups found for timestamp ${RESTORE_TIMESTAMP}"
        echo ""
        echo "Available backups:"
        ls -1 backups/ | grep -E 'backup_[0-9]{8}_[0-9]{6}\.(json|csv)' | sed 's/backup_//' | sed 's/commands_//' | sed 's/tags_//' | sed 's/\.json$//' | sed 's/\.csv$//' | sort -u
        exit 1
    fi

    echo "=== Restoring from backup ${RESTORE_TIMESTAMP} ==="
    echo ""

    # Restore from CSV if available (prefer CSV for editing workflow)
    if [ -n "$CSV_FILE" ]; then
        echo "Restoring from CSV..."
        python3 backup_db.py import-csv "commands_${RESTORE_TIMESTAMP}.csv"
    fi

    if [ -n "$TAGS_FILE" ]; then
        echo "Restoring tag comments from CSV..."
        python3 backup_db.py import-tags-csv "tags_${RESTORE_TIMESTAMP}.csv"
    fi

    # Fallback to JSON if CSV not available
    if [ -z "$CSV_FILE" ] && [ -n "$JSON_FILE" ]; then
        echo "Restoring from JSON..."
        python3 backup_db.py import "backup_${RESTORE_TIMESTAMP}.json"
    fi

    echo ""
    echo "=== Restore complete ==="

else
    echo "Usage: $0 [backup|restore] [timestamp]"
    echo ""
    echo "Commands:"
    echo "  backup   - Create new backups (default)"
    echo "  restore  - Restore from existing backup"
    echo ""
    echo "Examples:"
    echo "  $0                      # Create backup with current timestamp"
    echo "  $0 backup               # Same as above"
    echo "  $0 restore 20260130_191855  # Restore from specific timestamp"
    echo ""
    echo "Available backups:"
    ls -1 backups/ | grep -E 'backup_[0-9]{8}_[0-9]{6}\.json' | sed 's/backup_//' | sed 's/\.json$//' | sort -u
    exit 1
fi
