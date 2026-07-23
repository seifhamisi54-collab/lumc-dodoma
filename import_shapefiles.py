import os
from django.core.management.base import BaseCommand
from django.contrib.gis.utils import LayerMapping
from dashboard.models import VillageBoundary

class Command(BaseCommand):
    help = 'Import village boundaries from shapefile'
    
    def add_arguments(self, parser):
        parser.add_argument('shapefile_path', type=str, help='Path to shapefile')
    
    def handle(self, *args, **options):
        shapefile_path = options['shapefile_path']
        
        # Mapping - BADILISHA FIELD NAMES kulingana na shapefile yako
        mapping = {
            'name': 'Village_Name',
            'ward_name': 'Ward_Name',
            'district_name': 'District_Name',
            'region_name': 'Region_Name',
            'geom': 'MULTIPOLYGON',
            'area_ha': 'Area_Ha',
            'population': 'Population',
            'households': 'Households',
            'villages_code': 'Village_Code',
        }
        
        self.stdout.write(f'Importing villages from {shapefile_path}...')
        
        try:
            lm = LayerMapping(
                VillageBoundary,
                shapefile_path,
                mapping,
                transform=True,
                encoding='utf-8',
                source_srs=32736,  # UTM zone 36S for Tanzania
            )
            lm.save(strict=True, verbose=True)
            self.stdout.write(self.style.SUCCESS('Successfully imported villages'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {e}'))