import os
import django
import sys

sys.path.append('C:\\Users\\DELL XPS\\Desktop\\GIS MF 1\\tanzania_gis')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tanzania_gis.settings')
django.setup()

from locations.models import Region, District
import json

# Data ya Mikoa yote 31 ya Tanzania
regions_data = [
    ("Arusha", "01", -3.3869, 36.6830),
    ("Dar es Salaam", "02", -6.7924, 39.2083),
    ("Dodoma", "03", -6.1629, 35.7516),
    ("Geita", "04", -2.8667, 32.1667),
    ("Iringa", "05", -7.7667, 35.7000),
    ("Kagera", "06", -1.9167, 31.2500),
    ("Katavi", "07", -6.8500, 31.2500),
    ("Kigoma", "08", -4.8833, 29.6333),
    ("Kilimanjaro", "09", -3.0678, 37.3556),
    ("Lindi", "10", -9.5000, 38.5000),
    ("Manyara", "11", -4.3150, 36.9544),
    ("Mara", "12", -1.7500, 34.0000),
    ("Mbeya", "13", -8.9000, 33.4500),
    ("Morogoro", "14", -6.8167, 37.6667),
    ("Mtwara", "15", -10.2833, 40.1833),
    ("Mwanza", "16", -2.5167, 32.9000),
    ("Njombe", "17", -9.3333, 34.7667),
    ("Pemba Kaskazini", "18", -5.0333, 39.7667),
    ("Pemba Kusini", "19", -5.3333, 39.7500),
    ("Rukwa", "20", -7.0000, 31.0000),
    ("Ruvuma", "21", -10.6667, 36.0000),
    ("Shinyanga", "22", -3.6667, 33.4167),
    ("Simiyu", "23", -2.8000, 34.5000),
    ("Singida", "24", -4.8167, 34.7500),
    ("Songwe", "25", -8.5500, 33.3500),
    ("Tabora", "26", -5.0167, 32.8167),
    ("Tanga", "27", -5.0667, 39.1000),
    ("Unguja Kaskazini", "28", -5.9167, 39.3000),
    ("Unguja Kusini", "29", -6.2500, 39.3833),
    ("Unguja Mjini Magharibi", "30", -6.1667, 39.2000),
]

print("=" * 60)
print("🌍 TANZANIA GIS - SEED DATA")
print("=" * 60)

print("\n📌 INGIZA MIKOA:")
for name, code, lat, lon in regions_data:
    region, created = Region.objects.get_or_create(
        name=name,
        defaults={
            'code': code,
            'center_lat': lat,
            'center_lon': lon
        }
    )
    status = "✅" if created else "🔄"
    print(f"   {status} {name}")

# Wilaya za Dar es Salaam
districts_dar = [
    ("Ilala", "02.01", -6.8200, 39.2700),
    ("Kinondoni", "02.02", -6.7800, 39.2300),
    ("Temeke", "02.03", -6.8500, 39.3000),
    ("Ubungo", "02.04", -6.7500, 39.2000),
    ("Kigamboni", "02.05", -6.8800, 39.3500),
]

print("\n📌 INGIZA WILAYA ZA DAR ES SALAAM:")
try:
    dar_region = Region.objects.get(name="Dar es Salaam")
    for name, code, lat, lon in districts_dar:
        district, created = District.objects.get_or_create(
            name=name,
            region=dar_region,
            defaults={
                'code': code,
                'center_lat': lat,
                'center_lon': lon
            }
        )
        status = "✅" if created else "🔄"
        print(f"   {status} {name}")
except Region.DoesNotExist:
    print("   ❌ Dar es Salaam region not found!")

# Wilaya za Arusha
districts_arusha = [
    ("Arusha City", "01.01", -3.3667, 36.6833),
    ("Arusha", "01.02", -3.3667, 36.6833),
    ("Karatu", "01.03", -3.3333, 35.6667),
    ("Longido", "01.04", -2.7333, 36.6833),
    ("Meru", "01.05", -3.2667, 36.8000),
    ("Monduli", "01.06", -3.3000, 36.4500),
    ("Ngorongoro", "01.07", -3.2500, 35.5000),
]

print("\n📌 INGIZA WILAYA ZA ARUSHA:")
try:
    arusha_region = Region.objects.get(name="Arusha")
    for name, code, lat, lon in districts_arusha:
        district, created = District.objects.get_or_create(
            name=name,
            region=arusha_region,
            defaults={
                'code': code,
                'center_lat': lat,
                'center_lon': lon
            }
        )
        status = "✅" if created else "🔄"
        print(f"   {status} {name}")
except Region.DoesNotExist:
    print("   ❌ Arusha region not found!")

print("\n" + "=" * 60)
print("📊 DATABASE SUMMARY")
print("=" * 60)
print(f"   ✅ Regions: {Region.objects.count()} / 31")
print(f"   ✅ Districts: {District.objects.count()}")
print("=" * 60)
print("\n🎉 Data imeingizwa kikamilifu!")