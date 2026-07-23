from django.core.management.base import BaseCommand
from django.db import connection
from dashboard.models import LandUseReport

class Command(BaseCommand):
    help = 'Calculate land use statistics from shapefile data'
    
    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            # Calculate statistics per village
            cursor.execute("""
                INSERT INTO landuse.land_use_reports 
                (village_name, ward_name, district_name, region_name, 
                 agriculture_area_ha, forest_area_ha, urban_area_ha, 
                 water_area_ha, total_area_ha, has_landuse_plan)
                SELECT 
                    COALESCE(vil_mtaa_n, 'Unknown') as village_name,
                    ward_name,
                    district_n,
                    region_nam,
                    SUM(CASE WHEN landuse_type = 'Kilimo' THEN area_ha ELSE 0 END) as agri_area,
                    SUM(CASE WHEN landuse_type = 'Misitu' THEN area_ha ELSE 0 END) as forest_area,
                    SUM(CASE WHEN landuse_type IN ('Miji', 'Makazi', 'Urban') THEN area_ha ELSE 0 END) as urban_area,
                    SUM(CASE WHEN landuse_type = 'Maji' THEN area_ha ELSE 0 END) as water_area,
                    SUM(area_ha) as total_area,
                    CASE WHEN COUNT(*) > 0 THEN TRUE ELSE FALSE END as has_plan
                FROM landuse.land_use_data
                GROUP BY vil_mtaa_n, ward_name, district_n, region_nam
                ON CONFLICT (village_name, ward_name, district_name, region_name)
                DO UPDATE SET 
                    agriculture_area_ha = EXCLUDED.agriculture_area_ha,
                    forest_area_ha = EXCLUDED.forest_area_ha,
                    urban_area_ha = EXCLUDED.urban_area_ha,
                    water_area_ha = EXCLUDED.water_area_ha,
                    total_area_ha = EXCLUDED.total_area_ha,
                    updated_at = NOW()
            """)
            
            self.stdout.write(self.style.SUCCESS('Statistics calculated successfully!'))