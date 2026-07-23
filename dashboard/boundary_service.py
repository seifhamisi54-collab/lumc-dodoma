"""
Mipaka ya utawala — detailed_planning (ward/district boundaries) na fallback PostGIS.
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata
from difflib import SequenceMatcher

from django.db import connection

from detailed_planning.models import DistrictPlanningBoundary, WardPlanningBoundary

logger = logging.getLogger(__name__)

# Wilaya mpya zisizo kwenye shapefile ya zamani (mf. Madaba kutoka Songea).
DISTRICT_ALIASES: dict[str, list[str]] = {
    'madaba': ['songea'],
}

_FUZZY_CUTOFF = 0.82


def _clean_name(value: str | None) -> str:
    if not value:
        return ''
    v = str(value).strip()
    if v.lower() in ('undefined', 'null', 'none', ''):
        return ''
    return v


def _normalize_key(value: str | None) -> str:
    """Normalize for case-insensitive / fuzzy comparison."""
    text = _clean_name(value)
    if not text:
        return ''
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ascii', 'ignore').decode('ascii')
    text = re.sub(r'[^\w\s]', ' ', text.lower())
    return re.sub(r'\s+', ' ', text).strip()


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _fuzzy_pick(query: str, choices: list[str], *, cutoff: float = _FUZZY_CUTOFF) -> str | None:
    """Return best fuzzy match from choices, or None."""
    key = _normalize_key(query)
    if not key or not choices:
        return None

    norm_map: dict[str, list[str]] = {}
    for choice in choices:
        norm = _normalize_key(choice)
        if norm:
            norm_map.setdefault(norm, []).append(choice)

    if key in norm_map:
        return norm_map[key][0]

    best_name = None
    best_score = cutoff
    for norm, originals in norm_map.items():
        score = _similarity(key, norm)
        if score >= best_score:
            best_score = score
            best_name = originals[0]
    return best_name


def _district_search_names(district: str) -> list[str]:
    """District names to try, including known aliases (bidirectional)."""
    names = [_clean_name(district)]
    alias_key = _normalize_key(district)
    for alias in DISTRICT_ALIASES.get(alias_key, []):
        cleaned = _clean_name(alias)
        if cleaned and cleaned not in names:
            names.append(cleaned)
    for master_key, alias_list in DISTRICT_ALIASES.items():
        normalized_aliases = {_normalize_key(a) for a in alias_list}
        if alias_key in normalized_aliases or alias_key == master_key:
            master_display = master_key.title()
            if master_display and master_display not in names:
                names.append(master_display)
            for alias in alias_list:
                cleaned = _clean_name(alias)
                if cleaned and cleaned not in names:
                    names.append(cleaned)
    return [n for n in names if n]


def _is_national_region(region: str) -> bool:
    return not region or region.upper() in ('TANZANIA', 'ALL', 'NATIONAL')


def _geom_to_geojson_dict(geom) -> dict | None:
    if not geom:
        return None
    g = geom
    if g.srid != 4326:
        g = g.clone()
        g.transform(4326)
    return json.loads(g.geojson)


def resolve_region_for_district(district_name: str) -> str | None:
    """Tambua mkoa kutoka jina la wilaya."""
    district = _clean_name(district_name)
    if not district:
        return None

    for dist in _district_search_names(district):
        row = (
            DistrictPlanningBoundary.objects.filter(district_name__iexact=dist)
            .values_list('region_name', flat=True)
            .distinct()
            .first()
        )
        if row:
            return row

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT region_nam
                FROM boundaries.tanzania_administrative
                WHERE UPPER(district_n) = %s
                  AND region_nam IS NOT NULL AND region_nam != ''
                ORDER BY region_nam
                """,
                [district.upper()],
            )
            rows = [r[0] for r in cursor.fetchall() if r and r[0]]
            if rows:
                return rows[0]
    except Exception:
        logger.exception('resolve_region_for_district failed district=%s', district)
    return None


def _effective_region(region_name: str, district_name: str) -> str:
    region = _clean_name(region_name)
    if not _is_national_region(region):
        return region
    resolved = resolve_region_for_district(district_name)
    return resolved or region


def list_wards_for_district(region_name: str, district_name: str, *, limit: int = 40) -> list[str]:
    """Orodha ya kata zilizopo kwa wilaya (kwa ujumbe wa makosa)."""
    region = _clean_name(region_name)
    district = _clean_name(district_name)
    if not region or not district:
        return []

    wards: list[str] = []
    for dist in _district_search_names(district):
        qs = (
            WardPlanningBoundary.objects.filter(
                region_name__iexact=region,
                district_name__iexact=dist,
                ward_name__isnull=False,
            )
            .exclude(ward_name='')
            .values_list('ward_name', flat=True)
            .distinct()
            .order_by('ward_name')
        )
        wards.extend(qs)
        if wards:
            break

    if not wards:
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT DISTINCT ward_name
                    FROM boundaries.tanzania_administrative
                    WHERE UPPER(region_nam) = %s
                      AND UPPER(district_n) = %s
                      AND ward_name IS NOT NULL AND ward_name != ''
                    ORDER BY ward_name
                    LIMIT %s
                    """,
                    [region.upper(), district.upper(), limit],
                )
                wards = [r[0] for r in cursor.fetchall() if r and r[0]]
        except Exception:
            logger.exception(
                'list_wards_for_district fallback failed region=%s district=%s',
                region, district,
            )
    return wards[:limit]


def _find_ward_in_region(region: str, ward: str, district_hint: str | None = None):
    """Tafuta kata kwenye mkoa — kwanza wilaya iliyochaguliwa (na aliases), kisha mkoa mzima."""
    ward_clean = _clean_name(ward)
    if not ward_clean:
        return None

    search_districts = _district_search_names(district_hint) if district_hint else []

    for dist in search_districts:
        obj = WardPlanningBoundary.objects.filter(
            region_name__iexact=region,
            district_name__iexact=dist,
            ward_name__iexact=ward_clean,
            geom__isnull=False,
        ).first()
        if obj:
            return obj

        district_wards = list(
            WardPlanningBoundary.objects.filter(
                region_name__iexact=region,
                district_name__iexact=dist,
                geom__isnull=False,
            ).values_list('ward_name', flat=True).distinct()
        )
        fuzzy = _fuzzy_pick(ward_clean, district_wards)
        if fuzzy:
            obj = WardPlanningBoundary.objects.filter(
                region_name__iexact=region,
                district_name__iexact=dist,
                ward_name__iexact=fuzzy,
                geom__isnull=False,
            ).first()
            if obj:
                return obj

    region_wards = list(
        WardPlanningBoundary.objects.filter(
            region_name__iexact=region,
            geom__isnull=False,
        ).values_list('ward_name', flat=True).distinct()
    )
    fuzzy = _fuzzy_pick(ward_clean, region_wards)
    if fuzzy:
        return WardPlanningBoundary.objects.filter(
            region_name__iexact=region,
            ward_name__iexact=fuzzy,
            geom__isnull=False,
        ).first()

    return None


def _find_district_boundary(region: str, district: str):
    for dist in _district_search_names(district):
        obj = DistrictPlanningBoundary.objects.filter(
            region_name__iexact=region,
            district_name__iexact=dist,
            geom__isnull=False,
        ).first()
        if obj:
            return obj

        district_names = list(
            DistrictPlanningBoundary.objects.filter(
                region_name__iexact=region,
            ).values_list('district_name', flat=True).distinct()
        )
        fuzzy = _fuzzy_pick(dist, district_names)
        if fuzzy:
            obj = DistrictPlanningBoundary.objects.filter(
                region_name__iexact=region,
                district_name__iexact=fuzzy,
                geom__isnull=False,
            ).first()
            if obj:
                return obj
    return None


def resolve_admin_boundary(
    region_name: str,
    district_name: str | None = None,
    ward_name: str | None = None,
) -> dict | None:
    """
    Tafuta mipaka ya AOI na majina yaliyosuluhishwa.
    Rudisha dict: region, district, ward, geometry, source, district_corrected.
    """
    district = _clean_name(district_name)
    ward = _clean_name(ward_name)
    region = _effective_region(region_name, district)

    if not district:
        return None

    district_corrected = False

    if ward:
        ward_obj = _find_ward_in_region(region, ward, district)
        if ward_obj:
            if _normalize_key(ward_obj.district_name) != _normalize_key(district):
                district_corrected = True
            return {
                'region': ward_obj.region_name,
                'district': ward_obj.district_name,
                'ward': ward_obj.ward_name,
                'geometry': _geom_to_geojson_dict(ward_obj.geom),
                'source': 'detailed_planning.ward_boundaries',
                'district_corrected': district_corrected,
            }

        legacy = _legacy_boundary_geometry(region, district, ward)
        if legacy:
            return {
                'region': region,
                'district': district,
                'ward': ward,
                'geometry': legacy,
                'source': 'boundaries.tanzania_administrative',
                'district_corrected': False,
            }
        return None

    dist_obj = _find_district_boundary(region, district)
    if dist_obj:
        return {
            'region': dist_obj.region_name,
            'district': dist_obj.district_name,
            'ward': '',
            'geometry': _geom_to_geojson_dict(dist_obj.geom),
            'source': 'detailed_planning.district_boundaries',
            'district_corrected': False,
        }

    legacy = _legacy_boundary_geometry(region, district, None)
    if legacy:
        return {
            'region': region,
            'district': district,
            'ward': '',
            'geometry': legacy,
            'source': 'boundaries.tanzania_administrative',
            'district_corrected': False,
        }
    return None


def format_boundary_not_found_message(
    region_name: str,
    district_name: str | None = None,
    ward_name: str | None = None,
) -> str:
    """Ujumbe wa makosa wenye kata zinazopatikana kwa wilaya."""
    district = _clean_name(district_name)
    ward = _clean_name(ward_name)
    region = _effective_region(region_name, district)
    label = ward or district

    msg = f'Mipaka ya "{label}" haipatikani. Angalia mkoa/wilaya/kata.'

    if ward and district:
        wards = list_wards_for_district(region, district)
        if wards:
            preview = ', '.join(wards[:25])
            extra = f' (+{len(wards) - 25} zaidi)' if len(wards) > 25 else ''
            msg += f' Kata zinazopatikana kwa wilaya {district}: {preview}{extra}.'
        else:
            region_wards = list(
                WardPlanningBoundary.objects.filter(
                    region_name__iexact=region,
                    ward_name__iexact=ward,
                ).values_list('district_name', 'ward_name')
            )
            if region_wards:
                alt = ', '.join(f'{w} ({d})' for d, w in region_wards[:5])
                msg += f' Kata "{ward}" ipo chini ya wilaya nyingine: {alt}.'

            districts = list(
                DistrictPlanningBoundary.objects.filter(
                    region_name__iexact=region,
                ).values_list('district_name', flat=True).distinct().order_by('district_name')
            )
            if districts:
                msg += f' Wilaya zinazopatikana kwa {region}: {", ".join(districts)}.'

    return msg


def get_admin_boundary_geometry(
    region_name: str,
    district_name: str | None = None,
    ward_name: str | None = None,
) -> dict | None:
    """Rudisha geometry ya AOI (GeoJSON dict)."""
    resolved = resolve_admin_boundary(region_name, district_name, ward_name)
    if resolved:
        return resolved.get('geometry')
    return None


def _legacy_boundary_geometry(
    region_name: str,
    district_name: str,
    ward_name: str | None = None,
) -> dict | None:
    """Fallback: boundaries.tanzania_administrative (data ya zamani)."""
    district = _clean_name(district_name)
    ward = _clean_name(ward_name)
    region = _clean_name(region_name)

    if not district:
        return None

    if _is_national_region(region):
        return _legacy_boundary_by_district_only(district, ward)

    try:
        with connection.cursor() as cursor:
            if ward:
                cursor.execute(
                    """
                    SELECT ST_AsGeoJSON(ST_Union(geom)) AS geojson
                    FROM boundaries.tanzania_administrative
                    WHERE UPPER(region_nam) = %s
                      AND UPPER(district_n) = %s
                      AND UPPER(TRIM(ward_name)) = %s
                      AND ward_name IS NOT NULL AND ward_name != ''
                    """,
                    [region.upper(), district.upper(), ward.upper()],
                )
            else:
                cursor.execute(
                    """
                    SELECT ST_AsGeoJSON(ST_Union(geom)) AS geojson
                    FROM boundaries.tanzania_administrative
                    WHERE UPPER(region_nam) = %s
                      AND UPPER(district_n) = %s
                      AND district_n IS NOT NULL AND district_n != ''
                    """,
                    [region.upper(), district.upper()],
                )
            row = cursor.fetchone()
            if row and row[0]:
                return json.loads(row[0])
            if ward:
                return _legacy_boundary_by_district_only(district, ward)
    except Exception:
        logger.exception(
            '_legacy_boundary_geometry failed region=%s district=%s ward=%s',
            region, district, ward,
        )
    return None


def _legacy_boundary_by_district_only(district_name: str, ward_name: str | None = None) -> dict | None:
    district = _clean_name(district_name)
    ward = _clean_name(ward_name)
    if not district:
        return None
    try:
        with connection.cursor() as cursor:
            if ward:
                cursor.execute(
                    """
                    SELECT ST_AsGeoJSON(ST_Union(geom)) AS geojson
                    FROM boundaries.tanzania_administrative
                    WHERE UPPER(district_n) = %s
                      AND UPPER(TRIM(ward_name)) = %s
                      AND ward_name IS NOT NULL AND ward_name != ''
                    """,
                    [district.upper(), ward.upper()],
                )
            else:
                cursor.execute(
                    """
                    SELECT ST_AsGeoJSON(ST_Union(geom)) AS geojson
                    FROM boundaries.tanzania_administrative
                    WHERE UPPER(district_n) = %s
                      AND district_n IS NOT NULL AND district_n != ''
                    """,
                    [district.upper()],
                )
            row = cursor.fetchone()
            if row and row[0]:
                return json.loads(row[0])
    except Exception:
        logger.exception(
            '_legacy_boundary_by_district_only failed district=%s ward=%s',
            district, ward,
        )
    return None


def get_admin_boundary_feature(
    region_name: str,
    district_name: str | None = None,
    ward_name: str | None = None,
) -> dict | None:
    """Feature ya GeoJSON yenye properties za AOI."""
    resolved = resolve_admin_boundary(region_name, district_name, ward_name)
    if not resolved or not resolved.get('geometry'):
        return None
    ward = resolved.get('ward') or ''
    district = resolved.get('district') or ''
    region = resolved.get('region') or _clean_name(region_name)
    return {
        'type': 'Feature',
        'geometry': resolved['geometry'],
        'properties': {
            'name': ward or district,
            'type': 'ward' if ward else 'district',
            'district': district,
            'region': region,
            'ward': ward,
        },
    }
