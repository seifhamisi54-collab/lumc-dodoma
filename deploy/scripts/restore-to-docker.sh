#!/usr/bin/env bash
# Restore dumps into Docker PostGIS on the VM.
# Usage (on VM, from project root):
#   ./deploy/scripts/restore-to-docker.sh ./deploy/db-dumps/tanzania_gis_db_XXXX.dump ./deploy/db-dumps/detailed_planning_XXXX.dump
set -euo pipefail

MAIN_DUMP="${1:?main dump path required}"
DETAIL_DUMP="${2:?detailed planning dump path required}"

echo "Restoring tanzania_gis_db from $MAIN_DUMP ..."
docker compose exec -T db pg_restore -U postgres -d tanzania_gis_db --clean --if-exists --no-owner < "$MAIN_DUMP" || true

echo "Restoring DETAILED PLANNNING  from $DETAIL_DUMP ..."
docker compose exec -T db pg_restore -U postgres -d "DETAILED PLANNNING " --clean --if-exists --no-owner < "$DETAIL_DUMP" || true

echo "Ensure PostGIS extensions..."
docker compose exec -T db psql -U postgres -d tanzania_gis_db -c "CREATE EXTENSION IF NOT EXISTS postgis;"
docker compose exec -T db psql -U postgres -d "DETAILED PLANNNING " -c "CREATE EXTENSION IF NOT EXISTS postgis;"

echo "Restore finished."
