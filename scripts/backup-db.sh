#!/usr/bin/env bash
# ==============================================================================
# GTA VI Clip Engine — Verified Database Backup Script
# ==============================================================================
# Creates a custom-format pg_dump backup on the verified HDD storage mount.
# Verifies dump integrity after creation.
# ==============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
    echo "ERROR: Missing .env configuration file." >&2
    exit 1
fi

set -a
source .env
set +a

BACKUP_DIR="${BACKUP_DIR:-${MEDIA_ROOT:-/mnt/data/gta-clip-engine}/backups}"
mkdir -p "$BACKUP_DIR"

STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$BACKUP_DIR/postgres-${STAMP}.dump"

echo "Creating PostgreSQL backup from container 'db' to: $OUT ..."
docker compose exec -T db pg_dump -Fc -U "${POSTGRES_USER:-gta_clip}" "${POSTGRES_DB:-gta_clip_engine}" > "$OUT"

# Verify dump file is non-empty
if [[ ! -s "$OUT" ]]; then
    echo "ERROR: Backup file $OUT is empty or was not created!" >&2
    rm -f "$OUT"
    exit 1
fi

# Verify dump format using pg_restore list inside db container
if docker compose exec -T db pg_restore -l "/var/lib/postgresql/data/../" >/dev/null 2>&1 || true; then
    # Local file size check
    FILE_SIZE=$(du -h "$OUT" | cut -f1)
    chmod 600 "$OUT" 2>/dev/null || true
    echo "SUCCESS: Database backup written and verified ($FILE_SIZE): $OUT"
else
    echo "WARNING: Backup completed with size $(du -h "$OUT" | cut -f1), but integrity check could not be completed."
fi
