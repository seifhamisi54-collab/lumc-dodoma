#!/usr/bin/env python
"""Sasisha is_identified na hesabu za kijiji kwa viwanja vilivyopo."""
from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tanzania_gis.settings')

import django  # noqa: E402

django.setup()

from django.db.models import Q  # noqa: E402

from dashboard.boundary_service import _district_search_names  # noqa: E402
from detailed_planning.models import PlanningParcel, VillageDetailedPlan  # noqa: E402
from detailed_planning.services import (  # noqa: E402
    _infer_village_from_name,
    apply_identification_to_parcel,
)


def backfill_shapefile_sources(
    *,
    shapefile_name: str = 'Mpangokinaa1_mwande.shp',
    source_layer: str | None = None,
    dry_run: bool = False,
) -> dict:
    """Weka shapefile_name/source_layer kwa viwanja vilivyokuwepo bila metadata."""
    layer = source_layer or Path(shapefile_name).stem
    qs = PlanningParcel.objects.filter(
        Q(shapefile_name__isnull=True) | Q(shapefile_name=''),
    ).filter(
        Q(pid__isnull=False) & ~Q(pid='')
        | Q(parties__isnull=False) & ~Q(parties='')
        | Q(claim_no__isnull=False) & ~Q(claim_no='')
    )
    count = qs.count()
    if not dry_run and count:
        qs.update(
            shapefile_name=shapefile_name,
            source_layer=layer,
        )
    return {'updated': count, 'shapefile_name': shapefile_name, 'source_layer': layer}


def _parcels_qs(region: str, district: str, ward: str, village: str):
    qs = PlanningParcel.objects.filter(
        region_name__iexact=region,
        ward_name__iexact=ward,
        village_name__iexact=village,
    )
    district_names = _district_search_names(district)
    if district_names:
        district_q = Q()
        for name in district_names:
            district_q |= Q(district_name__iexact=name)
        qs = qs.filter(district_q)
    return qs


def backfill_imported_villages(*, dry_run: bool = False) -> dict:
    """Badilisha village_name='Imported' kutoka metadata ya shapefile au jina la faili."""
    qs = PlanningParcel.objects.filter(village_name__iexact='Imported')
    updated = 0
    for parcel in qs.iterator():
        new_village = (
            _infer_village_from_name(parcel.shapefile_name)
            or _infer_village_from_name(parcel.source_layer)
            or _infer_village_from_name(parcel.source_path)
            or _clean_shp_village(getattr(parcel, 'shp_village', None))
        )
        if not new_village:
            continue
        if not dry_run:
            parcel.village_name = new_village
            parcel.save(update_fields=['village_name', 'updated_at'])
        updated += 1
    return {'updated': updated, 'remaining_imported': qs.count() if dry_run else PlanningParcel.objects.filter(village_name__iexact='Imported').count()}


def _clean_shp_village(value: str | None) -> str | None:
    if not value or str(value).strip().lower() in ('imported', '-', ''):
        return None
    return str(value).strip()


def sync_village(region: str, district: str, ward: str, village: str) -> dict:
    plans = list(
        VillageDetailedPlan.objects.filter(
            region_name__iexact=region,
            ward_name__iexact=ward,
            village_name__iexact=village,
        )
    )
    if not plans:
        plans = [
            VillageDetailedPlan.objects.create(
                region_name=region,
                district_name=district,
                ward_name=ward,
                village_name=village,
                plan_status='draft',
            )
        ]

    for plan in plans:
        plan.sync_parcel_counts(recalculate_identification=True)

    parcels = _parcels_qs(region, district, ward, village)
    return {
        'village': village,
        'total': parcels.count(),
        'identified': parcels.filter(is_identified=True).count(),
        'unidentified': parcels.filter(is_identified=False).count(),
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Sync parcel identification counts')
    parser.add_argument('--region', default='Ruvuma')
    parser.add_argument('--district', default='Madaba')
    parser.add_argument('--ward', default='Matetereka')
    parser.add_argument('--village', default='Mwande')
    parser.add_argument('--backfill-villages', action='store_true', help='Badilisha village_name Imported kutoka metadata')
    parser.add_argument('--backfill-source', action='store_true', help='Weka shapefile_name kwa viwanja vilivyokuwepo')
    parser.add_argument('--shapefile-name', default='Mpangokinaa1_mwande.shp')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    if args.backfill_villages:
        result = backfill_imported_villages(dry_run=args.dry_run)
        print(f"Backfill villages: {result['updated']} updated, {result['remaining_imported']} Imported remaining")
        if args.dry_run:
            return

    if args.backfill_source:
        result = backfill_shapefile_sources(
            shapefile_name=args.shapefile_name,
            dry_run=args.dry_run,
        )
        print(f"Backfill: {result['updated']} viwanja -> {result['shapefile_name']} (layer: {result['source_layer']})")
        if args.dry_run:
            return

    result = sync_village(args.region, args.district, args.ward, args.village)
    print(
        f"{result['village']}: jumla {result['total']}, "
        f"vilivyotambuliwa {result['identified']}, "
        f"visivyotambuliwa {result['unidentified']}"
    )


if __name__ == '__main__':
    main()
