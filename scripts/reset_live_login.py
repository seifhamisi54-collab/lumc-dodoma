"""Weka upya password za login kwenye database ya live (Neon).

Haihitaji GDAL/PostGIS — inatumia psycopg2 + Django password hasher pekee.

Matumizi:

  .\deploy\scripts\reset-live-login.ps1

  # au:
  python scripts/reset_live_login.py --url "postgresql://..." --password "Nlupc2026!"
"""
from __future__ import annotations

import argparse
import os
import sys
from urllib.parse import parse_qs, unquote, urlparse

DEFAULT_PASSWORD = "Nlupc2026!"
DEFAULT_USERS = [
    "seif17",
    "Seif17",
    "seif01",
    "gisadmin",
    "seif.hamisi",
    "afisa.wilaya",
    "mtazamaji",
    "1701",
]


def parse_url(url: str) -> dict:
    url = url.strip().strip('"').strip("'")
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    p = urlparse(url)
    qs = parse_qs(p.query)
    sslmode = (qs.get("sslmode") or ["require"])[0]
    return {
        "dbname": unquote((p.path or "").lstrip("/").split("?")[0]) or "postgres",
        "user": unquote(p.username or ""),
        "password": unquote(p.password or ""),
        "host": p.hostname,
        "port": p.port or 5432,
        "sslmode": sslmode,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset live GIS Portal login passwords")
    parser.add_argument("--url", default=os.environ.get("DATABASE_URL", "").strip())
    parser.add_argument("--password", default=os.environ.get("LIVE_LOGIN_PASSWORD", DEFAULT_PASSWORD))
    parser.add_argument("--users", nargs="*", default=DEFAULT_USERS)
    args = parser.parse_args()

    if not args.url:
        print("ERROR: weka --url au DATABASE_URL")
        raise SystemExit(2)
    if len(args.password) < 6:
        print("ERROR: password lazima iwe angalau herufi 6")
        raise SystemExit(2)

    import django
    from django.conf import settings

    if not settings.configured:
        settings.configure(
            PASSWORD_HASHERS=["django.contrib.auth.hashers.PBKDF2PasswordHasher"],
        )
    django.setup()
    from django.contrib.auth.hashers import make_password

    import psycopg2

    cfg = parse_url(args.url)
    if not cfg["host"]:
        print("ERROR: URL haina hostname")
        raise SystemExit(2)

    print(f"Connecting to {cfg['host']} / {cfg['dbname']} ...")
    conn = psycopg2.connect(
        dbname=cfg["dbname"],
        user=cfg["user"],
        password=cfg["password"],
        host=cfg["host"],
        port=cfg["port"],
        sslmode=cfg["sslmode"],
        connect_timeout=30,
    )
    conn.autocommit = True
    hashed = make_password(args.password)

    ok = 0
    missing = []
    with conn.cursor() as cur:
        for username in args.users:
            cur.execute(
                """
                UPDATE accounts_customuser
                SET password = %s, is_active = TRUE
                WHERE username = %s
                RETURNING username
                """,
                (hashed, username),
            )
            row = cur.fetchone()
            if row:
                print(f"OK  {row[0]}")
                ok += 1
            else:
                missing.append(username)

    conn.close()
    print("---")
    print(f"Updated: {ok}")
    if missing:
        print("Not found:", ", ".join(missing))
    print("Login URL: https://lumc-dodoma.onrender.com/login/")
    print(f"Password:  {args.password}")
    print("Jaribu: seif17  au  gisadmin  au  seif.hamisi")


if __name__ == "__main__":
    main()
