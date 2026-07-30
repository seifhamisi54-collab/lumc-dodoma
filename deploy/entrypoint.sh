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

echo "Waiting for PostGIS..."
python - <<'PY'
import os, time, sys
import psycopg2
from urllib.parse import urlparse, unquote, parse_qs

def parse_database_url(url: str):
    url = url.strip().strip('"').strip("'")
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    p = urlparse(url)
    qs = parse_qs(p.query)
    sslmode = (qs.get("sslmode") or ["require"])[0]
    dbname = unquote((p.path or "").lstrip("/").split("?")[0]) or "postgres"
    return {
        "dbname": dbname,
        "user": unquote(p.username or ""),
        "password": unquote(p.password or ""),
        "host": p.hostname,
        "port": p.port or 5432,
        "sslmode": sslmode,
    }

def connect_params():
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        cfg = parse_database_url(url)
        print(
            f"DATABASE_URL parsed: host={cfg['host']!r} port={cfg['port']} "
            f"dbname={cfg['dbname']!r} user={cfg['user']!r} sslmode={cfg['sslmode']}"
        )
        if not cfg["host"]:
            print(
                "ERROR: DATABASE_URL has no hostname.\n"
                "Use full Neon URI, example:\n"
                "  postgresql://USER:PASSWORD@ep-xxxx.region.aws.neon.tech/tanzania_gis_db?sslmode=require\n"
                "Dashboard â†’ Neon â†’ Connection details â†’ copy URI (not only database name).",
                file=sys.stderr,
            )
            raise SystemExit(2)
        return cfg

    host = os.environ.get("DB_HOST", "").strip()
    if not host:
        print(
            "ERROR: DATABASE_URL is not set.\n"
            "In Render â†’ Environment, paste Neon connection string as DATABASE_URL.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    return {
        "dbname": os.environ.get("DB_NAME", "postgres"),
        "user": os.environ.get("DB_USER", "postgres"),
        "password": os.environ.get("DB_PASSWORD", "postgres"),
        "host": host,
        "port": int(os.environ.get("DB_PORT", "5432")),
        "sslmode": os.environ.get("DB_SSLMODE", "prefer"),
    }

cfg = connect_params()

for i in range(30):
    try:
        conn = psycopg2.connect(
            dbname=cfg["dbname"],
            user=cfg["user"],
            password=cfg["password"],
            host=cfg["host"],
            port=cfg["port"],
            sslmode=cfg["sslmode"],
            connect_timeout=10,
        )
        conn.close()
        print("PostGIS is ready")
        break
    except Exception as e:
        print(f"  wait ({i+1}/30): {e}")
        time.sleep(2)
else:
    raise SystemExit(
        "PostGIS did not become ready. Check DATABASE_URL (Neon URI with host + ?sslmode=require)."
    )
PY

echo "Collectstatic..."
python manage.py collectstatic --noinput || echo "WARN: collectstatic failed (continuing)"

echo "Migrate default DB..."
# Fail boot if default migrate fails — missing tables cause 500 on System Admin / Organizations
python manage.py migrate --noinput
python manage.py migrate sessions --noinput || echo "WARN: sessions migrate failed (continuing)"
python manage.py migrate dashboard accounts wadau --noinput || echo "WARN: app migrate re-check failed (continuing)"

echo "Migrate detailed_planning DB..."
python manage.py migrate --database=detailed_planning --noinput || echo "WARN: detailed_planning migrate failed (continuing)"

echo "Ensure village_plans.financial_year..."
python - <<'PY' || echo "WARN: village_plans schema ensure failed (continuing)"
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tanzania_gis.settings')
django.setup()
from detailed_planning.schema_ensure import ensure_village_plans_schema
ok = ensure_village_plans_schema(force=True)
print('village_plans.financial_year OK' if ok else 'village_plans.financial_year SKIP')
PY

# Keep section login/registration codes in sync with env (LUMC_LOGIN_CODE / LUMC_REGISTRATION_CODE)
echo "Ensuring SectionAccessConfig codes from settings..."
python manage.py ensure_section_access_config || echo "WARN: ensure_section_access_config failed (continuing)"

# Create default login accounts on every deploy (passwords only reset if SETUP_USERS_RESET=1)
if [ "${SETUP_DEFAULT_USERS:-1}" = "1" ]; then
  echo "Ensuring default user accounts..."
  if [ "${SETUP_USERS_RESET:-0}" = "1" ]; then
    python manage.py setup_users --reset-passwords || echo "WARN: setup_users failed (continuing)"
  else
    python manage.py setup_users || echo "WARN: setup_users failed (continuing)"
  fi
fi

echo "Starting: $*"
exec "$@"
