"""Ensure Joseph.Ndalu exists on live Neon (usable password + DMO role).

Does not need GDAL — uses psycopg2 + Django password hasher.

  python scripts/ensure_joseph_ndalu.py --url "$DATABASE_URL"
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from urllib.parse import parse_qs, unquote, urlparse

DEFAULT_PASSWORD = "Nlupc2026!"
USERNAME = "Joseph.Ndalu"
ROLE_CODE = "data_management_officer"
FIRST_NAME = "Joseph Ndalu"


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
    parser = argparse.ArgumentParser(description="Ensure Joseph.Ndalu on live DB")
    parser.add_argument("--url", default=os.environ.get("DATABASE_URL", "").strip())
    parser.add_argument(
        "--password",
        default=os.environ.get("LIVE_LOGIN_PASSWORD", DEFAULT_PASSWORD),
    )
    args = parser.parse_args()
    if not args.url:
        print("ERROR: pass --url or set DATABASE_URL")
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
        print("ERROR: URL has no hostname")
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
    now = datetime.now(timezone.utc)

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO accounts_userrole (name)
            VALUES (%s)
            ON CONFLICT (name) DO NOTHING
            """,
            (ROLE_CODE,),
        )
        cur.execute(
            "SELECT id FROM accounts_userrole WHERE name = %s",
            (ROLE_CODE,),
        )
        role_row = cur.fetchone()
        if not role_row:
            print("ERROR: could not resolve role", ROLE_CODE)
            raise SystemExit(1)
        role_id = role_row[0]

        cur.execute(
            "SELECT id, username, is_active, is_staff FROM accounts_customuser WHERE username = %s",
            (USERNAME,),
        )
        existing = cur.fetchone()
        if existing:
            cur.execute(
                """
                UPDATE accounts_customuser
                SET password = %s,
                    first_name = %s,
                    is_active = TRUE,
                    is_staff = TRUE,
                    is_superuser = FALSE,
                    role_id = %s
                WHERE username = %s
                RETURNING id, username, is_active, is_staff
                """,
                (hashed, FIRST_NAME, role_id, USERNAME),
            )
            row = cur.fetchone()
            print(f"UPDATED id={row[0]} user={row[1]} active={row[2]} staff={row[3]} role={ROLE_CODE}")
        else:
            cur.execute(
                """
                INSERT INTO accounts_customuser (
                    password, last_login, is_superuser, username, first_name, last_name,
                    email, is_staff, is_active, date_joined, phone, role_id,
                    profile_picture, assigned_region_id, assigned_district_id
                ) VALUES (
                    %s, NULL, FALSE, %s, %s, '',
                    '', TRUE, TRUE, %s, '', %s,
                    NULL, NULL, NULL
                )
                RETURNING id, username, is_active, is_staff
                """,
                (hashed, USERNAME, FIRST_NAME, now, role_id),
            )
            row = cur.fetchone()
            print(f"CREATED id={row[0]} user={row[1]} active={row[2]} staff={row[3]} role={ROLE_CODE}")

    conn.close()
    print("---")
    print(f"Login: {USERNAME} / {args.password}")
    print("Login code: LUMC-LOGIN-2026")
    print("URL: https://lumc-dodoma.onrender.com/login/")


if __name__ == "__main__":
    main()
