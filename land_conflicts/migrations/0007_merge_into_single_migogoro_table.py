# Merge lookup tables into one: detailed_planning.migogoro

from django.db import migrations


def forwards_merge(apps, schema_editor):
    with schema_editor.connection.cursor() as cur:
        # Drop FK columns from main table (db_column names)
        for col in (
            'conflict_source_code',
            'conflict_type_code',
            'financial_year_code',
            'resolution_method_code',
        ):
            cur.execute(
                f'ALTER TABLE detailed_planning.land_conflict_cases '
                f'DROP COLUMN IF EXISTS {col} CASCADE'
            )

        # Drop lookup tables
        for table in (
            'migogoro_conflict_sources',
            'migogoro_conflict_types',
            'migogoro_financial_years',
            'migogoro_resolution_methods',
        ):
            cur.execute(f'DROP TABLE IF EXISTS detailed_planning.{table} CASCADE')

        # Rename main table -> migogoro
        cur.execute(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM pg_tables
                    WHERE schemaname = 'detailed_planning'
                      AND tablename = 'land_conflict_cases'
                ) AND NOT EXISTS (
                    SELECT 1 FROM pg_tables
                    WHERE schemaname = 'detailed_planning'
                      AND tablename = 'migogoro'
                ) THEN
                    ALTER TABLE detailed_planning.land_conflict_cases
                    RENAME TO migogoro;
                END IF;
            END $$;
            """
        )


def backwards_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('land_conflicts', '0006_conflict_type_other'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(forwards_merge, backwards_noop),
            ],
            state_operations=[
                migrations.RemoveField(
                    model_name='landconflictcase',
                    name='conflict_source_ref',
                ),
                migrations.RemoveField(
                    model_name='landconflictcase',
                    name='conflict_type_ref',
                ),
                migrations.RemoveField(
                    model_name='landconflictcase',
                    name='financial_year_ref',
                ),
                migrations.RemoveField(
                    model_name='landconflictcase',
                    name='resolution_method_ref',
                ),
                migrations.DeleteModel(
                    name='MigogoroConflictSource',
                ),
                migrations.DeleteModel(
                    name='MigogoroConflictType',
                ),
                migrations.DeleteModel(
                    name='MigogoroFinancialYear',
                ),
                migrations.DeleteModel(
                    name='MigogoroResolutionMethod',
                ),
                migrations.AlterModelOptions(
                    name='landconflictcase',
                    options={
                        'ordering': ['-started_date', '-created_at'],
                        'verbose_name': 'Mgogoro wa Ardhi',
                        'verbose_name_plural': 'Migogoro ya Ardhi',
                    },
                ),
                migrations.AlterModelTable(
                    name='landconflictcase',
                    table='"detailed_planning"."migogoro"',
                ),
            ],
        ),
    ]
