#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
    echo "ERROR: Missing .env configuration file." >&2
    exit 1
fi

echo "=== GTA VI Clip Engine: Database Migration & Baseline Adoption ==="

# Check that db container is healthy
if ! docker compose ps db | grep -q "healthy"; then
    echo "Waiting for database service to become healthy..."
    sleep 3
fi

echo "[1/3] Checking existing database tables..."
# Check if creators table exists in PostgreSQL
HAS_CREATORS=$(docker compose exec -T db psql -U "${POSTGRES_USER:-gta_clip}" -d "${POSTGRES_DB:-gta_clip_engine}" -t -A -c "SELECT to_regclass('public.creators');" 2>/dev/null || echo "")

# Check if alembic_version table exists
HAS_ALEMBIC=$(docker compose exec -T db psql -U "${POSTGRES_USER:-gta_clip}" -d "${POSTGRES_DB:-gta_clip_engine}" -t -A -c "SELECT to_regclass('public.alembic_version');" 2>/dev/null || echo "")

if [[ "$HAS_CREATORS" == "creators" && "$HAS_ALEMBIC" != "alembic_version" ]]; then
    echo "[2/3] Existing starter schema detected without Alembic tracking."
    echo "       Safely stamping baseline revision '0001_baseline' (preserving all tables and data)..."
    docker compose exec -T api alembic stamp 0001_baseline
else
    echo "[2/3] Baseline state verified."
fi

echo "[3/3] Applying pending migrations up to head..."
docker compose exec -T api alembic upgrade head

CURRENT_REV=$(docker compose exec -T api alembic current || true)
echo "=== Migrations completed successfully. Current version: $CURRENT_REV ==="
