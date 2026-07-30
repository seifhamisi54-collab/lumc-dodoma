"""Ensure village_plans.financial_year exists after partial Neon migrates."""

from django.db import migrations


def ensure_financial_year(apps, schema_editor):
    conn = schema_editor.connection
    with conn.cursor() as cur:
        cur.execute('CREATE SCHEMA IF NOT EXISTS detailed_planning')
        cur.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'detailed_planning'
              AND table_name = 'village_plans'
              AND column_name = 'financial_year'
            """
        )
        if cur.fetchone():
            return
        cur.execute(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'detailed_planning'
              AND table_name = 'village_plans'
            """
        )
        if not cur.fetchone():
            return
        cur.execute(
            """
            ALTER TABLE detailed_planning.village_plans
            ADD COLUMN IF NOT EXISTS financial_year VARCHAR(32) NOT NULL DEFAULT '2026/2027'
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS village_plans_financial_year_idx
            ON detailed_planning.village_plans (financial_year)
            """
        )


class Migration(migrations.Migration):

    dependencies = [
        ('detailed_planning', '0008_quarter_reports_meeting_minutes'),
    ]

    operations = [
        migrations.RunPython(ensure_financial_year, migrations.RunPython.noop),
    ]
