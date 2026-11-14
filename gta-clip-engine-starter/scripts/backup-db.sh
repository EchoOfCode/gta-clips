#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -f .env ]]; then echo "Missing .env" >&2; exit 1; fi
set -a
source .env
set +a
BACKUP_DIR="${BACKUP_DIR:-${MEDIA_ROOT:-/mnt/data/gta-clip-engine}/backups}"
mkdir -p "$BACKUP_DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$BACKUP_DIR/postgres-${STAMP}.dump"
docker compose exec -T db pg_dump -Fc -U "${POSTGRES_USER:-gta_clip}" "${POSTGRES_DB:-gta_clip_engine}" > "$OUT"
echo "Database backup written to: $OUT"
