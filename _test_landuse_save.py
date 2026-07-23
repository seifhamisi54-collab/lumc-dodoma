import os
import traceback

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tanzania_gis.settings')
django.setup()

from django.contrib.gis.geos import MultiPolygon, Polygon
from django.db import connection

from dashboard.landuse_service import import_landuse_from_geojson, landuse_queryset_for_location
from dashboard.models import LandUse

cur = connection.cursor()
cur.execute(
    """
    SELECT column_name, data_type, udt_name
    FROM information_schema.columns
    WHERE table_schema='landuse' AND table_name='land_use'
    ORDER BY ordinal_position
    """
)
print('COLUMNS:')
for row in cur.fetchall():
    print(' ', row)

print('COUNT before', LandUse.objects.count())

poly = Polygon(((35.0, -6.0), (35.01, -6.0), (35.01, -5.99), (35.0, -5.99), (35.0, -6.0)), srid=4326)
mp = MultiPolygon(poly, srid=4326)
mp.transform(32736)

try:
    obj = LandUse.objects.create(
        geom=mp,
        tumiz='Kilimo',
        kijiji='TestKijiji',
        kata='TestKata',
        wilaya='Songea',
        objectid=999999,
    )
    print('CREATE OK id=', obj.pk)
except Exception:
    traceback.print_exc()

fc = {
    'type': 'FeatureCollection',
    'features': [
        {
            'type': 'Feature',
            'properties': {'tumiz': 'Makazi', 'matumizi': 'Makazi'},
            'geometry': {
                'type': 'Polygon',
                'coordinates': [
                    [
                        [35.02, -6.0],
                        [35.03, -6.0],
                        [35.03, -5.99],
                        [35.02, -5.99],
                        [35.02, -6.0],
                    ]
                ],
            },
        }
    ],
}

try:
    result = import_landuse_from_geojson(
        fc, district='Songea', ward='Matetereka', village='Mwande', shapefile_name='test.shp'
    )
    print('IMPORT', result)
except Exception:
    traceback.print_exc()

print('COUNT after', LandUse.objects.count())
qs = landuse_queryset_for_location(district='Songea')
print('QS Songea', qs.count())
# cleanup test rows
LandUse.objects.filter(objectid=999999).delete()
LandUse.objects.filter(kijiji='Mwande', tumiz='Makazi').delete()
print('cleaned')
