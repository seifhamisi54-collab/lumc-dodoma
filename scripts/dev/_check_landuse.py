import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tanzania_gis.settings')
django.setup()

from django.db import connection

c = connection.cursor()
c.execute(
    """
    SELECT column_name, data_type, udt_name
    FROM information_schema.columns
    WHERE table_schema='landuse' AND table_name='land_use'
    ORDER BY ordinal_position
    """
)
print('land_use cols:', c.fetchall())
c.execute("SELECT Find_SRID('landuse','land_use','geom')")
print('srid', c.fetchone())
c.execute('SELECT COUNT(*) FROM landuse.land_use')
print('count', c.fetchone())
c.execute(
    """
    SELECT column_name FROM information_schema.columns
    WHERE table_schema='landuse' AND table_name='land_use_data'
    """
)
print('land_use_data cols:', c.fetchall())
c.execute(
    """
    SELECT schemaname, tablename FROM pg_tables
    WHERE schemaname='landuse' ORDER BY 2
    """
)
print('landuse tables:', c.fetchall())
