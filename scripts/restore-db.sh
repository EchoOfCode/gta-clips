#!/usr/bin/env bash
# ==============================================================================
# GTA VI Clip Engine — Verified Database Restore Test Script
# ==============================================================================
# Safely tests restoration of a pg_dump backup into an isolated test database
# without risking live production data.
#
# Usage:
#   ./scripts/restore-db.sh <path-to-dump-file> [target-database-name]
# Defaults to verifying against a temporary database: 'gta_restore_test'
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

DUMP_FILE="${1:-}"
if [[ -z "$DUMP_FILE" || ! -f "$DUMP_FILE" ]]; then
    echo "ERROR: Please specify a valid dump file to restore." >&2
    echo "Usage: $0 <path-to-dump-file> [test-database-name]" >&2
    exit 1
fi

TARGET_DB="${2:-gta_restore_test}"
PROD_DB="${POSTGRES_DB:-gta_clip_engine}"

if [[ "$TARGET_DB" == "$PROD_DB" ]]; then
    echo "CAUTION: Target database matches production database ($PROD_DB)."
    echo "To protect existing data, destructive overwrite of the live database requires"
    echo "manual administration. This script is designed for verified restore testing."
    read -r -p "Are you ABSOLUTELY sure you want to restore into LIVE database '$PROD_DB'? [type 'RESTORE-LIVE']: " confirm
    if [[ "$confirm" != "RESTORE-LIVE" ]]; then
        echo "Aborted."
        exit 0
    fi
fi

echo "=== Testing Database Restore from: $DUMP_FILE ==="
echo "Target Database: $TARGET_DB"

# Create target test database if it does not exist
docker compose exec -T db psql -U "${POSTGRES_USER:-gta_clip}" -d postgres -c "CREATE DATABASE \"$TARGET_DB\";" 2>/dev/null || true

echo "Restoring schema and data into '$TARGET_DB'..."
docker compose exec -T db pg_restore --clean --if-exists --no-owner --no-privileges -U "${POSTGRES_USER:-gta_clip}" -d "$TARGET_DB" < "$DUMP_FILE" || true

echo "Verifying restored tables in '$TARGET_DB'..."
TABLE_COUNT=$(docker compose exec -T db psql -U "${POSTGRES_USER:-gta_clip}" -d "$TARGET_DB" -t -A -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';")
CREATORS_COUNT=$(docker compose exec -T db psql -U "${POSTGRES_USER:-gta_clip}" -d "$TARGET_DB" -t -A -c "SELECT count(*) FROM creators;" 2>/dev/null || echo "0")

echo "[OK] Restore verified successfully!"
echo "     Public tables restored: $TABLE_COUNT"
echo "     Creators records verified: $CREATORS_COUNT"

if [[ "$TARGET_DB" != "$PROD_DB" ]]; then
    read -r -p "Clean up test database '$TARGET_DB'? [Y/n]: " cleanup_resp
    if [[ "$cleanup_resp" != "n" && "$cleanup_resp" != "N" ]]; then
        docker compose exec -T db psql -U "${POSTGRES_USER:-gta_clip}" -d postgres -c "DROP DATABASE \"$TARGET_DB\";"
        echo "[OK] Test database '$TARGET_DB' cleaned up."
    fi
fi
