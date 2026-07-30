"""Ensure System Admin tables are schema-qualified (boundaries).

Unqualified names break on Neon pooler when search_path is public-only;
GIS models already use schema-qualified db_table for the same reason.
"""

from django.db import migrations

ADMIN_TABLES = (
    'dashboard_currency',
    'dashboard_locality',
    'dashboard_designation',
    'dashboard_systemformtemplate',
    'dashboard_ccroconfigoption',
    'dashboard_systemsetting',
)


def ensure_boundaries_admin_tables(apps, schema_editor):
    conn = schema_editor.connection
    with conn.cursor() as cur:
        cur.execute('CREATE SCHEMA IF NOT EXISTS boundaries')
        for table in ADMIN_TABLES:
            cur.execute(
                """
                SELECT table_schema
                FROM information_schema.tables
                WHERE table_name = %s
                  AND table_schema IN ('public', 'boundaries')
                ORDER BY CASE table_schema WHEN 'boundaries' THEN 0 ELSE 1 END
                """,
                [table],
            )
            rows = cur.fetchall()
            schemas = {r[0] for r in rows}
            if 'boundaries' in schemas:
                # Prefer boundaries; drop accidental public duplicate if both exist
                if 'public' in schemas:
                    cur.execute(f'DROP TABLE IF EXISTS public."{table}" CASCADE')
                continue
            if 'public' in schemas:
                cur.execute(f'ALTER TABLE public."{table}" SET SCHEMA boundaries')


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0007_system_setting_passcode'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(ensure_boundaries_admin_tables, migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.AlterModelTable(
                    name='currency',
                    table='"boundaries"."dashboard_currency"',
                ),
                migrations.AlterModelTable(
                    name='locality',
                    table='"boundaries"."dashboard_locality"',
                ),
                migrations.AlterModelTable(
                    name='designation',
                    table='"boundaries"."dashboard_designation"',
                ),
                migrations.AlterModelTable(
                    name='systemformtemplate',
                    table='"boundaries"."dashboard_systemformtemplate"',
                ),
                migrations.AlterModelTable(
                    name='ccroconfigoption',
                    table='"boundaries"."dashboard_ccroconfigoption"',
                ),
                migrations.AlterModelTable(
                    name='systemsetting',
                    table='"boundaries"."dashboard_systemsetting"',
                ),
            ],
        ),
    ]
