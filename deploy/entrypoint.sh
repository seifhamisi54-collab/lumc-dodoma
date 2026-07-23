#!/bin/sh
set -e

# Resolve GDAL/GEOS paths on Debian (versions vary)
if [ -z "$GDAL_LIBRARY_PATH" ] || [ ! -e "$GDAL_LIBRARY_PATH" ]; then
  GDAL_SO=$(ldconfig -p 2>/dev/null | awk '/libgdal.so/{print $NF; exit}')
  if [ -n "$GDAL_SO" ]; then
    export GDAL_LIBRARY_PATH="$GDAL_SO"
  fi
fi
if [ -z "$GEOS_LIBRARY_PATH" ] || [ ! -e "$GEOS_LIBRARY_PATH" ]; then
  GEOS_SO=$(ldconfig -p 2>/dev/null | awk '/libgeos_c.so/{print $NF; exit}')
  if [ -n "$GEOS_SO" ]; then
    export GEOS_LIBRARY_PATH="$GEOS_SO"
  fi
fi
echo "GDAL_LIBRARY_PATH=${GDAL_LIBRARY_PATH:-unset}"
echo "GEOS_LIBRARY_PATH=${GEOS_LIBRARY_PATH:-unset}"

if [ -z "${DATABASE_URL:-}" ] && [ -z "${DB_HOST:-}" ]; then
  echo "ERROR: DATABASE_URL is not set. Add Neon connection string in Render → Environment."
  exit 1
fi

echo "Waiting for PostGIS..."
python - <<'PY'
import os, time
import psycopg2
from urllib.parse import urlparse, unquote, parse_qs

def connect_once():
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        p = urlparse(url)
        qs = parse_qs(p.query)
        sslmode = (qs.get("sslmode") or ["require"])[0]
        return psycopg2.connect(
            dbname=unquote(p.path.lstrip("/").split("?")[0]) or "postgres",
            user=unquote(p.username or ""),
            password=unquote(p.password or ""),
            host=p.hostname,
            port=p.port or 5432,
            sslmode=sslmode,
            connect_timeout=10,
        )
    return psycopg2.connect(
        dbname=os.environ.get("DB_NAME", "postgres"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", "postgres"),
        host=os.environ.get("DB_HOST", "db"),
        port=os.environ.get("DB_PORT", "5432"),
        connect_timeout=10,
    )

for i in range(30):
    try:
        conn = connect_once()
        conn.close()
        print("PostGIS is ready")
        break
    except Exception as e:
        print(f"  wait ({i+1}/30): {e}")
        time.sleep(2)
else:
    raise SystemExit(
        "PostGIS did not become ready. Check DATABASE_URL (Neon URI with ?sslmode=require)."
    )
PY

echo "Collectstatic..."
python manage.py collectstatic --noinput || echo "WARN: collectstatic failed (continuing)"

echo "Migrate default DB..."
python manage.py migrate --noinput || echo "WARN: migrate failed (continuing)"

echo "Starting: $*"
exec "$@"
