"""Huduma za matumizi ya ardhi — hifadhi na GeoJSON kutoka landuse.land_use."""
from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation

from django.contrib.gis.geos import GEOSGeometry
from django.db import transaction

from dashboard.models import LandUse
from detailed_planning.services import (
    _clean_text,
    _pick_from_props,
    geojson_to_multipolygon,
)

_TUMIZ_FIELDS = (
    'tumiz', 'Tumiz', 'TUMIZ', 'tumizi', 'Tumizi', 'TUMIZI',
    'matumizi', 'Matumizi', 'MATUMIZI', 'Matumizi_y', 'MATUMIZI_Y', 'Matumizi_1',
    'land_use', 'LAND_USE', 'Land_Use', 'LandUse',
    'landuse', 'LANDUSE', 'Landuse', 'landuse_type',
    'LU_CODE', 'lu_code', 'ainat', 'AINAT', 'AINA', 'aina',
)
_TUMIZI2_FIELDS = (
    'tumizi_2', 'Tumizi_2', 'TUMIZI_2', 'tumizi2', 'Tumizi2',
    'descr', 'DESCR', 'description', 'DESCRIPTION',
)
_JINA_FIELDS = ('jina', 'JINA', 'Jina', 'name', 'NAME', 'Name', 'lu_name')
_KIJIJI_FIELDS = (
    'kijiji', 'Kijiji', 'KIJIJI', 'village', 'Village', 'VILLAGE',
    'village_name', 'VILLAGE_NAME',
)
_KATA_FIELDS = ('kata', 'Kata', 'KATA', 'ward', 'Ward', 'WARD', 'ward_name', 'WARD_NAME')
_WILAYA_FIELDS = (
    'wilaya', 'Wilaya', 'WILAYA', 'district', 'District', 'DISTRICT',
    'district_name', 'DIST_NAME', 'dist_name',
)
_OBJECTID_FIELDS = ('objectid', 'OBJECTID', 'ObjectID', 'FID', 'fid', 'id', 'ID')
_AREA_FIELDS = ('area_ha', 'AREA_Ha', 'AREA_HA', 'Area_Ha', 'ha', 'HA', 'Ha_1', 'ha_1')
_ACRES_FIELDS = ('acres_1', 'Acres_1', 'ACRES_1', 'acres', 'ACRES')


def _pick_number(props: dict, candidates: tuple[str, ...]) -> Decimal | None:
    if not props:
        return None
    for key in candidates:
        if key not in props or props[key] in (None, ''):
            continue
        try:
            return Decimal(str(props[key]).replace(',', ''))
        except (InvalidOperation, ValueError, TypeError):
            continue
    return None


def _pick_int(props: dict, candidates: tuple[str, ...]) -> int | None:
    num = _pick_number(props, candidates)
    if num is None:
        return None
    try:
        return int(num)
    except (ValueError, TypeError, OverflowError):
        return None


def import_landuse_from_geojson(
    feature_collection: dict,
    *,
    district: str | None = None,
    ward: str | None = None,
    village: str | None = None,
    shapefile_name: str | None = None,
) -> dict:
    """Ingiza polygoni za matumizi kutoka GeoJSON (WGS84) kwenye landuse.land_use."""
    features = feature_collection.get('features') or []
    created = updated = skipped = 0
    ui_district = _clean_text(district)
    ui_ward = _clean_text(ward)
    ui_village = _clean_text(village)

    with transaction.atomic():
        next_oid = (
            LandUse.objects.order_by('-objectid')
            .values_list('objectid', flat=True)
            .first()
        )
        next_oid = (next_oid or 0) + 1

        for feature in features:
            props = feature.get('properties') or {}
            geom = geojson_to_multipolygon(feature.get('geometry'))
            if geom is None:
                skipped += 1
                continue

            tumiz = _pick_from_props(props, _TUMIZ_FIELDS)
            tumizi_2 = _pick_from_props(props, _TUMIZI2_FIELDS)
            jina = _pick_from_props(props, _JINA_FIELDS)
            kijiji = _pick_from_props(props, _KIJIJI_FIELDS) or ui_village
            kata = _pick_from_props(props, _KATA_FIELDS) or ui_ward
            wilaya = _pick_from_props(props, _WILAYA_FIELDS) or ui_district
            objectid = _pick_int(props, _OBJECTID_FIELDS)
            area_prop = _pick_number(props, _AREA_FIELDS)
            acres = _pick_number(props, _ACRES_FIELDS)
            area_ha = area_prop
            if area_ha is None:
                try:
                    area_ha = Decimal(str(round(geom.area / 10_000.0, 4)))
                except Exception:
                    area_ha = None

            if objectid is None:
                objectid = next_oid
                next_oid += 1

            existing = LandUse.objects.filter(geom=geom).first()
            if existing:
                existing.objectid = objectid or existing.objectid
                existing.area_ha = area_ha if area_ha is not None else existing.area_ha
                existing.jina = jina or existing.jina
                existing.tumiz = tumiz or existing.tumiz
                existing.tumizi_2 = tumizi_2 or existing.tumizi_2
                existing.ha_1 = area_ha if area_ha is not None else existing.ha_1
                existing.acres_1 = acres if acres is not None else existing.acres_1
                existing.kijiji = kijiji or existing.kijiji
                existing.kata = kata or existing.kata
                existing.wilaya = wilaya or existing.wilaya
                existing.save()
                updated += 1
                continue

            LandUse.objects.create(
                geom=geom,
                objectid=objectid,
                area_ha=area_ha,
                jina=jina,
                tumiz=tumiz,
                tumizi_2=tumizi_2,
                ha_1=area_ha,
                acres_1=acres,
                kijiji=kijiji,
                kata=kata,
                wilaya=wilaya,
            )
            created += 1

    return {
        'created': created,
        'updated': updated,
        'skipped': skipped,
        'total': created + updated,
        'shapefile_name': shapefile_name,
        'district': ui_district,
        'ward': ui_ward,
        'village': ui_village,
    }


def landuse_queryset_for_location(
    *,
    district: str | None = None,
    ward: str | None = None,
    village: str | None = None,
):
    qs = LandUse.objects.exclude(geom__isnull=True)
    district = _clean_text(district)
    ward = _clean_text(ward)
    village = _clean_text(village)
    if district:
        qs = qs.filter(wilaya__iexact=district)
    if ward:
        qs = qs.filter(kata__iexact=ward)
    if village:
        qs = qs.filter(kijiji__iexact=village)
    return qs


def list_landuse_imports(
    *,
    district: str | None = None,
    ward: str | None = None,
    village: str | None = None,
) -> list[dict]:
    """Orodha ya matumizi yaliyopakiwa, yaliyopangwa kwa wilaya/kata/kijiji."""
    from django.db.models import Count

    district = _clean_text(district)
    if not district:
        return []

    qs = landuse_queryset_for_location(district=district, ward=ward, village=village)
    items: list[dict] = []
    for group in (
        qs.values('wilaya', 'kata', 'kijiji')
        .annotate(feature_count=Count('id'))
        .order_by('kijiji', 'kata')
    ):
        wilaya = group.get('wilaya') or district
        kata = group.get('kata') or ''
        kijiji = group.get('kijiji') or ''
        place = kijiji or kata or wilaya
        items.append({
            'id': f"landuse:{wilaya}:{kata}:{kijiji}",
            'source': 'landuse',
            'title': f'Matumizi — {place}',
            'shapefile_name': f'Matumizi — {place}',
            'original_filename': f'Matumizi — {place}',
            'boundary_level': 'landuse',
            'district_name': wilaya,
            'ward_name': kata,
            'village_name': kijiji,
            'feature_count': group['feature_count'],
            'parcel_count': group['feature_count'],
            'uploaded_at': None,
        })
    return items


def delete_landuse_for_location(
    *,
    district: str | None = None,
    ward: str | None = None,
    village: str | None = None,
) -> int:
    """Futa polygoni za matumizi kwa eneo lililochaguliwa."""
    district = _clean_text(district)
    if not district:
        return 0
    qs = landuse_queryset_for_location(district=district, ward=ward, village=village)
    deleted, _ = qs.delete()
    return deleted


def landuse_to_geojson(qs) -> dict:
    """Badilisha queryset → FeatureCollection (WGS84) kwa ramani."""
    features = []
    for row in qs.iterator():
        if not row.geom:
            continue
        try:
            geom = row.geom.clone()
            if geom.srid != 4326:
                geom.transform(4326)
            geometry = json.loads(geom.geojson)
        except Exception:
            continue

        tumiz = row.tumiz or ''
        tumizi_2 = row.tumizi_2 or ''
        # Attribute kuu ya rangi: tumiz (kutoka Shapefile) — mf. Makazi, Kilimo
        matumizi_attr = tumiz or tumizi_2 or (row.jina or '')
        props = {
            'id': row.id,
            'objectid': row.objectid,
            'jina': row.jina,
            'tumiz': tumiz,
            'tumizi': tumiz,
            'tumizi_2': tumizi_2,
            'area_ha': float(row.area_ha) if row.area_ha is not None else None,
            'kijiji': row.kijiji,
            'kata': row.kata,
            'wilaya': row.wilaya,
            'landuse_type': matumizi_attr,
            'matumizi': matumizi_attr,
            'land_use': matumizi_attr,
        }
        features.append({
            'type': 'Feature',
            'properties': props,
            'geometry': geometry,
        })
    return {'type': 'FeatureCollection', 'features': features}
