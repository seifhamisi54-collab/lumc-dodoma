#!/usr/bin/env python
"""
Import kata (ward) boundaries from Tanzania regional shapefiles
into detailed_planning.ward_boundaries (PostGIS SRID 32736).

Source: one .shp per mkoa (region), one polygon per ward (kata).
Duplicate polygons for the same ward are dissolved before insert.

Usage (from tanzania_gis project root):
    .\\venv\\Scripts\\python.exe scripts\\import_ward_boundaries.py
    .\\venv\\Scripts\\python.exe scripts\\import_ward_boundaries.py --clear
    .\\venv\\Scripts\\python.exe scripts\\import_ward_boundaries.py --shapefile-dir "D:\\path\\to\\shp"
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

from detailed_planning.models import WardPlanningBoundary  # noqa: E402

TARGET_SRID = 32736
DEFAULT_SHAPEFILE_DIR = Path(r'D:\MFUMO LUMC\Tanzania Shapefile')

REGION_FIELD_CANDIDATES = ('reg_name', 'REG_NAME', 'Region', 'REGION', 'Mkoa', 'MKOA')
DISTRICT_FIELD_CANDIDATES = ('dist_name', 'DIST_NAME', 'District', 'DISTRICT', 'Wilaya', 'WILAYA')
WARD_FIELD_CANDIDATES = ('ward_name', 'WARD_NAME', 'Ward', 'WARD', 'Kata', 'KATA')


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
    if len(geoms) == 1:
        geom = geoms[0]
        if geom.geom_type == 'Polygon':
            return MultiPolygon(geom)
        return geom
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


def collect_wards(shapefile_dir: Path) -> dict[tuple[str, str, str], dict]:
    """Read all regional shapefiles and group ward polygons by (region, district, ward)."""
    grouped: dict[tuple[str, str, str], dict] = defaultdict(
        lambda: {'geoms': [], 'shapefile_name': '', 'source_features': 0}
    )

    shp_files = sorted(shapefile_dir.glob('*.shp'))
    if not shp_files:
        raise FileNotFoundError(f'Hakuna .shp katika {shapefile_dir}')

    source_features = 0
    for shp_path in shp_files:
        ds = ogr.Open(str(shp_path))
        if ds is None:
            raise RuntimeError(f'GDAL haikuweza kufungua {shp_path}')
        layer = ds.GetLayer()
        layer_defn = layer.GetLayerDefn()
        reg_field = _pick_field(layer_defn, REGION_FIELD_CANDIDATES)
        dist_field = _pick_field(layer_defn, DISTRICT_FIELD_CANDIDATES)
        ward_field = _pick_field(layer_defn, WARD_FIELD_CANDIDATES)
        fallback_region = _filename_to_region(shp_path.stem)
        shapefile_name = shp_path.name

        for feat in layer:
            source_features += 1
            region = (feat.GetField(reg_field) if reg_field else None) or fallback_region
            district = feat.GetField(dist_field) if dist_field else None
            ward = feat.GetField(ward_field) if ward_field else None
            if not district or not ward:
                continue
            region = str(region).strip()
            district = str(district).strip()
            ward = str(ward).strip()
            if not region or not district or not ward:
                continue

            geom = _feature_geom(feat)
            if geom is None:
                continue

            key = (region, district, ward)
            grouped[key]['geoms'].append(geom)
            grouped[key]['shapefile_name'] = shapefile_name
            grouped[key]['source_features'] += 1

        ds = None

    return grouped, source_features


@transaction.atomic(using='detailed_planning')
def import_wards(shapefile_dir: Path, *, clear: bool = False) -> dict:
    if clear:
        deleted, _ = WardPlanningBoundary.objects.using('detailed_planning').all().delete()
        print(f'Imefutwa rekodi {deleted} za zamani.')

    grouped, source_features = collect_wards(shapefile_dir)
    created = updated = skipped = errors = dissolved = 0
    error_details: list[str] = []

    for (region, district, ward), data in sorted(grouped.items()):
        try:
            if data['source_features'] > 1:
                dissolved += 1
            geom = _dissolve(data['geoms'])
            if geom is None:
                skipped += 1
                error_details.append(f'{region}/{district}/{ward}: hakuna geometry halali')
                continue

            area_ha = _area_ha(geom)
            _, was_created = WardPlanningBoundary.objects.using('detailed_planning').update_or_create(
                region_name=region,
                district_name=district,
                ward_name=ward,
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
            error_details.append(f'{region}/{district}/{ward}: {exc}')

    total = WardPlanningBoundary.objects.using('detailed_planning').count()
    return {
        'source_shapefiles': len(list(shapefile_dir.glob('*.shp'))),
        'source_features': source_features,
        'unique_wards': len(grouped),
        'dissolved_wards': dissolved,
        'created': created,
        'updated': updated,
        'skipped': skipped,
        'errors': errors,
        'error_details': error_details,
        'db_total': total,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Import kata (ward) boundaries into DETAILED PLANNING DB')
    parser.add_argument(
        '--shapefile-dir',
        type=Path,
        default=DEFAULT_SHAPEFILE_DIR,
        help='Folder with regional .shp files (one per mkoa)',
    )
    parser.add_argument(
        '--clear',
        action='store_true',
        help='Delete existing ward_boundaries before import',
    )
    args = parser.parse_args()

    if not args.shapefile_dir.is_dir():
        print(f'ERROR: folda haipo: {args.shapefile_dir}', file=sys.stderr)
        return 1

    print(f'Chanzo: {args.shapefile_dir}')
    print(f'Lengo: detailed_planning.ward_boundaries (SRID {TARGET_SRID})')
    print('Inaendesha import...')

    result = import_wards(args.shapefile_dir, clear=args.clear)

    print('\n=== MUHTASARI ===')
    print(f"Shapefiles zilizosomwa: {result['source_shapefiles']}")
    print(f"Poligoni za chanzo (features): {result['source_features']}")
    print(f"Kata za kipekee (kutoka chanzo): {result['unique_wards']}")
    print(f"Kata zilizounganishwa (dissolve): {result['dissolved_wards']}")
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
