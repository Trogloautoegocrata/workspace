#!/bin/bash
# Backup automático con timestamp
FILE=$1
if [ -z "$FILE" ]; then
  echo "Uso: bash scripts/backup-version.sh <archivo>"
  exit 1
fi
DIR=$(dirname "$FILE")
NAME=$(basename "$FILE")
BACKUP_DIR="$DIR/.backups"
mkdir -p "$BACKUP_DIR"
cp "$FILE" "$BACKUP_DIR/$NAME.v$(date +%Y%m%d-%H%M%S).bak"
echo "✅ Backup: $BACKUP_DIR/$NAME.v$(date +%Y%m%d-%H%M%S).bak"
