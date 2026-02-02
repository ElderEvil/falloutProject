#!/bin/bash
# Fallout Shelter Database Backup Script
# Backs up PostgreSQL database to /mnt/dead-pool/backups/fallout

set -e
umask 077

# Configuration
BACKUP_DIR="/mnt/dead-pool/backups/fallout"
DB_NAME="${POSTGRES_DB:-fallout_db}"
DB_USER="${POSTGRES_USER:-postgres}"
DB_HOST="${POSTGRES_SERVER:-localhost}"
DB_PORT="${POSTGRES_PORT:-5432}"
RETENTION_DAYS=14

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Generate timestamped filename
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/fallout_${TIMESTAMP}.sql"

echo "Starting backup of $DB_NAME..."
echo "Backup file: $BACKUP_FILE"

# Perform backup
# Only use PGPASSWORD if POSTGRES_PASSWORD is set, otherwise rely on .pgpass or peer auth
if [ -n "$POSTGRES_PASSWORD" ]; then
    export PGPASSWORD="$POSTGRES_PASSWORD"
fi

if pg_dump \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    -F p \
    -f "$BACKUP_FILE"; then

    # Compress the backup
    gzip "$BACKUP_FILE"
    echo "Backup completed: ${BACKUP_FILE}.gz"

    # Show backup size
    ls -lh "${BACKUP_FILE}.gz"

    # Clean up old backups (keep only last N days)
    echo "Cleaning up backups older than $RETENTION_DAYS days..."
    find "$BACKUP_DIR" -name "fallout_*.sql.gz" -mtime +$RETENTION_DAYS -delete

    echo "Backup process completed successfully!"
    echo ""
    echo "To restore from this backup:"
    echo "  gunzip ${BACKUP_FILE}.gz"
    echo "  psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME < $BACKUP_FILE"
else
    echo "Backup failed!"
    exit 1
fi
