import os
import sys
import django
import json

sys.path.append('C:\\Users\\DELL XPS\\Desktop\\GIS MF 1\\tanzania_gis')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tanzania_gis.settings')
django.setup()

from locations.models import Region, District

def import_geojson_file(file_path, region_name):
    """Ingiza GeoJSON kutoka faili"""
    with open(file_path, 'r', encoding='utf-8') as f:
        geojson = json.load(f)
    
    region = Region.objects.get(name=region_name)
    region.boundary_geojson = geojson
    region.save()
    
    print(f"✅ GeoJSON imported for {region_name}")

# Tumia
import_geojson_file('C:/path/to/your/geojson_file.geojson', 'Dar es Salaam')