"""Align landuse.import_logs.imported_by with ForeignKey(User) / bigint PK.

The unmanaged table still had varchar(150) from the original CharField schema.
Django SET_NULL on CustomUser delete generates ``imported_by IN (<int>)``,
which PostgreSQL rejects: character varying = integer.
"""

from django.db import migrations


FORWARD_SQL = """
DO $$
DECLARE
    col_type text;
BEGIN
    SELECT data_type INTO col_type
    FROM information_schema.columns
    WHERE table_schema = 'landuse'
      AND table_name = 'import_logs'
      AND column_name = 'imported_by';

    IF col_type IS NULL THEN
        RETURN;
    END IF;

    IF col_type IN ('character varying', 'text', 'character') THEN
        ALTER TABLE landuse.import_logs
            ALTER COLUMN imported_by TYPE bigint
            USING (
                CASE
                    WHEN imported_by IS NULL OR btrim(imported_by::text) = '' THEN NULL
                    WHEN btrim(imported_by::text) ~ '^[0-9]+$' THEN btrim(imported_by::text)::bigint
                    ELSE NULL
                END
            );
    ELSIF col_type IN ('integer', 'bigint', 'smallint') THEN
        -- Already numeric; ensure bigint for CustomUser PK
        IF col_type <> 'bigint' THEN
            ALTER TABLE landuse.import_logs
                ALTER COLUMN imported_by TYPE bigint
                USING imported_by::bigint;
        END IF;
    END IF;

    -- Drop dangling values that do not match an existing user
    UPDATE landuse.import_logs il
    SET imported_by = NULL
    WHERE imported_by IS NOT NULL
      AND NOT EXISTS (
          SELECT 1 FROM accounts_customuser u WHERE u.id = il.imported_by
      );

    -- Optional FK (idempotent): helps DB-level SET NULL if present
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_schema = 'landuse'
          AND table_name = 'import_logs'
          AND constraint_name = 'import_logs_imported_by_fk'
    ) THEN
        ALTER TABLE landuse.import_logs
            ADD CONSTRAINT import_logs_imported_by_fk
            FOREIGN KEY (imported_by)
            REFERENCES accounts_customuser (id)
            ON DELETE SET NULL;
    END IF;
END $$;
"""


REVERSE_SQL = """
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_schema = 'landuse'
          AND table_name = 'import_logs'
          AND constraint_name = 'import_logs_imported_by_fk'
    ) THEN
        ALTER TABLE landuse.import_logs
            DROP CONSTRAINT import_logs_imported_by_fk;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'landuse'
          AND table_name = 'import_logs'
          AND column_name = 'imported_by'
          AND data_type IN ('bigint', 'integer', 'smallint')
    ) THEN
        ALTER TABLE landuse.import_logs
            ALTER COLUMN imported_by TYPE varchar(150)
            USING imported_by::text;
    END IF;
END $$;
"""


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0009_ensure_systemsetting_table'),
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(FORWARD_SQL, REVERSE_SQL),
    ]
