"""Ensure dashboard_systemsetting exists under boundaries (passcode gate)."""

from django.db import migrations


def ensure_systemsetting_table(apps, schema_editor):
    conn = schema_editor.connection
    with conn.cursor() as cur:
        cur.execute('CREATE SCHEMA IF NOT EXISTS boundaries')
        cur.execute(
            """
            SELECT table_schema
            FROM information_schema.tables
            WHERE table_name = 'dashboard_systemsetting'
              AND table_schema IN ('public', 'boundaries')
            """
        )
        schemas = {row[0] for row in cur.fetchall()}
        if 'boundaries' in schemas:
            if 'public' in schemas:
                cur.execute('DROP TABLE IF EXISTS public.dashboard_systemsetting CASCADE')
            return
        if 'public' in schemas:
            cur.execute('ALTER TABLE public.dashboard_systemsetting SET SCHEMA boundaries')
            return
        cur.execute(
            """
            CREATE TABLE boundaries.dashboard_systemsetting (
                id BIGSERIAL PRIMARY KEY,
                key VARCHAR(100) NOT NULL UNIQUE,
                value TEXT NOT NULL DEFAULT '',
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_by_id INTEGER NULL
            )
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS dashboard_systemsetting_key_idx
            ON boundaries.dashboard_systemsetting (key)
            """
        )


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0008_system_admin_boundaries_schema'),
    ]

    operations = [
        migrations.RunPython(ensure_systemsetting_table, migrations.RunPython.noop),
    ]
