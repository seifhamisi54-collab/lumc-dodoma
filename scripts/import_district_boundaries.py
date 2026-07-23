#!/usr/bin/env python
"""
Import wilaya (district) boundaries from Tanzania regional shapefiles
into detailed_planning.district_boundaries (PostGIS SRID 32736).

Source: one .shp per mkoa (region), ward-level polygons dissolved by district.

Usage (from tanzania_gis project root):
    .\\venv\\Scripts\\python.exe scripts\\import_district_boundaries.py
    .\\venv\\Scripts\\python.exe scripts\\import_district_boundaries.py --clear
    .\\venv\\Scripts\\python.exe scripts\\import_district_boundaries.py --shapefile-dir "D:\\path\\to\\shp"
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from pathlib import Path

# Django / GDAL setup
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tanzania_gis.settings')
os.environ['PATH'] = r'C:\Program Files\GDAL;' + os.environ.get('PATH', '')
os.environ['PROJ_LIB'] = r'C:\Program Files\GDAL\projlib'

import django

django.setup()

from django.contrib.gis.geos import GEOSGeometry, MultiPolygon, Polygon  # noqa: E402
from django.db import transaction  # noqa: E402
from osgeo import ogr  # noqa: E402

from detailed_planning.models import DistrictPlanningBoundary  # noqa: E402

TARGET_SRID = 32736
DEFAULT_SHAPEFILE_DIR = Path(r'D:\MFUMO LUMC\Tanzania Shapefile')

REGION_FIELD_CANDIDATES = ('reg_name', 'REG_NAME', 'Region', 'REGION', 'Mkoa', 'MKOA')
DISTRICT_FIELD_CANDIDATES = ('dist_name', 'DIST_NAME', 'District', 'DISTRICT', 'Wilaya', 'WILAYA')


def _filename_to_region(stem: str) -> str:
    return stem.replace('_', ' ').strip()


def _pick_field(layer_defn, candidates: tuple[str, ...]) -> str | None:
    names = {layer_defn.GetFieldDefn(i).GetName() for i in range(layer_defn.GetFieldCount())}
    for c in candidates:
        if c in names:
            return c
    lower_map = {n.lower(): n for n in names}
    for c in candidates:
        if c.lower() in lower_map:
            return lower_map[c.lower()]
    return None


def _feature_geom(feat) -> GEOSGeometry | None:
    geom_ref = feat.GetGeometryRef()
    if geom_ref is None or geom_ref.IsEmpty():
        return None
    wkt = geom_ref.ExportToWkt()
    geom = GEOSGeometry(wkt, srid=4326)
    if geom.srid != TARGET_SRID:
        geom.transform(TARGET_SRID)
    if geom.geom_type == 'Polygon':
        return MultiPolygon(geom)
    if geom.geom_type == 'MultiPolygon':
        return geom
    return None


def _dissolve(geoms: list[GEOSGeometry]) -> MultiPolygon | None:
    if not geoms:
        return None
    merged = geoms[0]
    for g in geoms[1:]:
        merged = merged.union(g)
    if merged.geom_type == 'Polygon':
        return MultiPolygon(merged)
    if merged.geom_type == 'MultiPolygon':
        return merged
    if merged.geom_type == 'GeometryCollection':
        polys = [p for p in merged if p.geom_type in ('Polygon', 'MultiPolygon')]
        if not polys:
            return None
        return _dissolve(polys)
    return None


def _area_ha(geom: MultiPolygon) -> float:
    return round(geom.area / 10_000.0, 4)


def collect_districts(shapefile_dir: Path) -> dict[tuple[str, str], dict]:
    """Read all regional shapefiles and group ward polygons by (region, district)."""
    grouped: dict[tuple[str, str], dict] = defaultdict(lambda: {'geoms': [], 'shapefile_name': ''})

    shp_files = sorted(shapefile_dir.glob('*.shp'))
    if not shp_files:
        raise FileNotFoundError(f'Hakuna .shp katika {shapefile_dir}')

    for shp_path in shp_files:
        ds = ogr.Open(str(shp_path))
        if ds is None:
            raise RuntimeError(f'GDAL haikuweza kufungua {shp_path}')
        layer = ds.GetLayer()
        layer_defn = layer.GetLayerDefn()
        reg_field = _pick_field(layer_defn, REGION_FIELD_CANDIDATES)
        dist_field = _pick_field(layer_defn, DISTRICT_FIELD_CANDIDATES)
        fallback_region = _filename_to_region(shp_path.stem)
        shapefile_name = shp_path.name

        for feat in layer:
            region = (feat.GetField(reg_field) if reg_field else None) or fallback_region
            district = feat.GetField(dist_field) if dist_field else None
            if not district:
                continue
            region = str(region).strip()
            district = str(district).strip()
            if not region or not district:
                continue

            geom = _feature_geom(feat)
            if geom is None:
                continue

            key = (region, district)
            grouped[key]['geoms'].append(geom)
            grouped[key]['shapefile_name'] = shapefile_name

        ds = None

    return grouped


@transaction.atomic(using='detailed_planning')
def import_districts(shapefile_dir: Path, *, clear: bool = False) -> dict:
    if clear:
        deleted, _ = DistrictPlanningBoundary.objects.using('detailed_planning').all().delete()
        print(f'Imefutwa rekodi {deleted} za zamani.')

    grouped = collect_districts(shapefile_dir)
    created = updated = skipped = errors = 0
    error_details: list[str] = []

    for (region, district), data in sorted(grouped.items()):
        try:
            geom = _dissolve(data['geoms'])
            if geom is None:
                skipped += 1
                error_details.append(f'{region}/{district}: hakuna geometry halali')
                continue

            area_ha = _area_ha(geom)
            _, was_created = DistrictPlanningBoundary.objects.using('detailed_planning').update_or_create(
                region_name=region,
                district_name=district,
                defaults={
                    'geom': geom,
                    'shapefile_name': data['shapefile_name'],
                    'area_ha': area_ha,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1
        except Exception as exc:
            errors += 1
            error_details.append(f'{region}/{district}: {exc}')

    total = DistrictPlanningBoundary.objects.using('detailed_planning').count()
    return {
        'source_shapefiles': len(list(shapefile_dir.glob('*.shp'))),
        'unique_districts': len(grouped),
        'created': created,
        'updated': updated,
        'skipped': skipped,
        'errors': errors,
        'error_details': error_details,
        'db_total': total,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Import wilaya boundaries into DETAILED PLANNING DB')
    parser.add_argument(
        '--shapefile-dir',
        type=Path,
        default=DEFAULT_SHAPEFILE_DIR,
        help='Folder with regional .shp files (one per mkoa)',
    )
    parser.add_argument(
        '--clear',
        action='store_true',
        help='Delete existing district_boundaries before import',
    )
    args = parser.parse_args()

    if not args.shapefile_dir.is_dir():
        print(f'ERROR: folda haipo: {args.shapefile_dir}', file=sys.stderr)
        return 1

    print(f'Chanzo: {args.shapefile_dir}')
    print(f'Lengo: detailed_planning.district_boundaries (SRID {TARGET_SRID})')
    print('Inaendesha import...')

    result = import_districts(args.shapefile_dir, clear=args.clear)

    print('\n=== MUHTASARI ===')
    print(f"Shapefiles zilizosomwa: {result['source_shapefiles']}")
    print(f"Wilaya za kipekee (kutoka chanzo): {result['unique_districts']}")
    print(f"Imeundwa: {result['created']}")
    print(f"Imesasishwa: {result['updated']}")
    print(f"Imepuuzwa: {result['skipped']}")
    print(f"Makosa: {result['errors']}")
    print(f"Jumla kwenye DB: {result['db_total']}")

    if result['error_details']:
        print('\nMaelezo ya makosa:')
        for line in result['error_details'][:20]:
            print(f'  - {line}')
        if len(result['error_details']) > 20:
            print(f'  ... na {len(result["error_details"]) - 20} zaidi')

    return 1 if result['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
