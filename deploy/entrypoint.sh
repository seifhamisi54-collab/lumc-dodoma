#!/bin/sh
set -e

echo "Waiting for PostGIS..."
python - <<'PY'
import os, time
import psycopg2
from urllib.parse import urlparse, unquote

def connect_once():
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        p = urlparse(url)
        return psycopg2.connect(
            dbname=unquote(p.path.lstrip("/")) or "postgres",
            user=unquote(p.username or ""),
            password=unquote(p.password or ""),
            host=p.hostname,
            port=p.port or 5432,
            sslmode="require" if p.hostname and "localhost" not in p.hostname else "prefer",
        )
    return psycopg2.connect(
        dbname="postgres",
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", "postgres"),
        host=os.environ.get("DB_HOST", "db"),
        port=os.environ.get("DB_PORT", "5432"),
    )

for i in range(60):
    try:
        conn = connect_once()
        conn.close()
        print("PostGIS is ready")
        break
    except Exception as e:
        print(f"  wait ({i+1}/60): {e}")
        time.sleep(2)
else:
    raise SystemExit("PostGIS did not become ready")
PY

echo "Collectstatic..."
python manage.py collectstatic --noinput

echo "Migrate default DB..."
python manage.py migrate --noinput || true

echo "Starting: $*"
exec "$@"
