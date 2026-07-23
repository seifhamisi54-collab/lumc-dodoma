#!/usr/bin/env bash
# Dump both LUMC PostGIS databases from local PC (run on Windows Git Bash / WSL / Linux).
# Adjust HOST/PORT/USER to match your local Postgres (default from settings: port 5433).
set -euo pipefail

HOST="${PGHOST:-localhost}"
PORT="${PGPORT:-5433}"
USER="${PGUSER:-postgres}"
OUT_DIR="${1:-./deploy/db-dumps}"
mkdir -p "$OUT_DIR"
STAMP=$(date +%Y%m%d_%H%M%S)

echo "Dumping tanzania_gis_db ..."
PGPASSWORD="${PGPASSWORD:-1701}" pg_dump -h "$HOST" -p "$PORT" -U "$USER" -Fc -f "$OUT_DIR/tanzania_gis_db_${STAMP}.dump" tanzania_gis_db

echo "Dumping DETAILED PLANNNING  ..."
PGPASSWORD="${PGPASSWORD:-1701}" pg_dump -h "$HOST" -p "$PORT" -U "$USER" -Fc -f "$OUT_DIR/detailed_planning_${STAMP}.dump" "DETAILED PLANNNING "

echo "Done. Files in $OUT_DIR"
ls -lh "$OUT_DIR"/*_"${STAMP}".dump
