"""Copy detailed_planning tables from Neon `detailed_planning` DB → `neondb`."""
from __future__ import annotations

import sys
from urllib.parse import parse_qs, unquote, urlparse

import psycopg2
from psycopg2.extras import execute_batch

TABLES = [
    "district_boundaries",
    "ward_boundaries",
    "village_boundaries",
    "village_plans",
    "planning_parcels",
    "planning_reports",
    "planning_shapefiles",
    "migogoro",
]


def parse_url(url: str) -> dict:
    url = url.strip().strip('"').strip("'")
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    p = urlparse(url)
    qs = parse_qs(p.query)
    return {
        "dbname": unquote((p.path or "").lstrip("/").split("?")[0]),
        "user": unquote(p.username or ""),
        "password": unquote(p.password or ""),
        "host": p.hostname,
        "port": p.port or 5432,
        "sslmode": (qs.get("sslmode") or ["require"])[0],
    }


def connect(url: str):
    c = parse_url(url)
    return psycopg2.connect(
        dbname=c["dbname"],
        user=c["user"],
        password=c["password"],
        host=c["host"],
        port=c["port"],
        sslmode=c["sslmode"],
        connect_timeout=60,
    )


def sql_type(udt: str, dtype: str, maxlen) -> str:
    if udt == "geometry":
        return "geometry"
    if dtype == "character varying" and maxlen:
        return f"varchar({maxlen})"
    if dtype == "character" and maxlen:
        return f"char({maxlen})"
    mapping = {
        "uuid": "uuid",
        "int4": "integer",
        "int8": "bigint",
        "float8": "double precision",
        "float4": "real",
        "bool": "boolean",
        "text": "text",
        "bytea": "bytea",
        "timestamptz": "timestamptz",
        "timestamp": "timestamp",
        "date": "date",
        "jsonb": "jsonb",
        "json": "json",
        "numeric": "numeric",
    }
    return mapping.get(udt, udt)


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: copy_planning_to_neondb.py <SOURCE_URL> <DEST_URL>")
        raise SystemExit(2)

    src = connect(sys.argv[1])
    dst = connect(sys.argv[2])
    src.autocommit = True
    dst.autocommit = True

    with dst.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS postgis")
        cur.execute("CREATE SCHEMA IF NOT EXISTS detailed_planning")

    with src.cursor() as sc, dst.cursor() as dc:
        for table in TABLES:
            fq = f'detailed_planning."{table}"'
            sc.execute(
                """
                SELECT EXISTS (
                  SELECT 1 FROM information_schema.tables
                  WHERE table_schema='detailed_planning' AND table_name=%s
                )
                """,
                (table,),
            )
            if not sc.fetchone()[0]:
                print(f"SKIP missing {fq}")
                continue

            sc.execute(
                """
                SELECT column_name, udt_name, data_type, character_maximum_length, is_nullable
                FROM information_schema.columns
                WHERE table_schema='detailed_planning' AND table_name=%s
                ORDER BY ordinal_position
                """,
                (table,),
            )
            cols = sc.fetchall()
            col_defs = []
            for name, udt, dtype, maxlen, nullable in cols:
                typ = sql_type(udt, dtype, maxlen)
                nn = " NOT NULL" if nullable == "NO" else ""
                col_defs.append(f'"{name}" {typ}{nn}')

            dc.execute(f'DROP TABLE IF EXISTS {fq} CASCADE')
            dc.execute(f'CREATE TABLE {fq} ({", ".join(col_defs)})')
            print(f"CREATED {fq}")

            select_exprs = []
            placeholders = []
            quoted = []
            for name, udt, *_rest in cols:
                quoted.append(f'"{name}"')
                if udt == "geometry":
                    select_exprs.append(f'ST_AsEWKB("{name}")')
                    placeholders.append("ST_GeomFromEWKB(%s)")
                else:
                    select_exprs.append(f'"{name}"')
                    placeholders.append("%s")

            sc.execute(f'SELECT {", ".join(select_exprs)} FROM {fq}')
            insert = (
                f'INSERT INTO {fq} ({", ".join(quoted)}) VALUES ({", ".join(placeholders)})'
            )

            total = 0
            batch = []
            while True:
                rows = sc.fetchmany(100)
                if not rows:
                    break
                batch.extend(rows)
                if len(batch) >= 100:
                    execute_batch(dc, insert, batch, page_size=50)
                    total += len(batch)
                    print(f"  ... {total}")
                    batch = []
            if batch:
                execute_batch(dc, insert, batch, page_size=50)
                total += len(batch)
            print(f"COPIED {fq}: {total} rows")

            # helpful indexes for map APIs
            if table == "district_boundaries":
                dc.execute(
                    f'CREATE INDEX IF NOT EXISTS district_boundaries_region_idx ON {fq} (region_name)'
                )
            if table == "ward_boundaries":
                dc.execute(
                    f'CREATE INDEX IF NOT EXISTS ward_boundaries_region_district_idx ON {fq} (region_name, district_name)'
                )

    src.close()
    dst.close()
    print("Done.")


if __name__ == "__main__":
    main()
