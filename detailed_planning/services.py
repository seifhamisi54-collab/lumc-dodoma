"""Huduma za detailed planning — namba za viwanja na mipaka."""
from __future__ import annotations

import os
import re
import unicodedata
import uuid
from pathlib import Path

from django.contrib.gis.geos import GEOSGeometry, MultiPolygon
from django.core.files.storage import default_storage
from django.db import transaction

from detailed_planning.models import (
    DistrictPlanningBoundary,
    MeetingMinutes,
    PlanningParcel,
    PlanningReport,
    PlanningShapefile,
    QuarterReport,
    VillageDetailedPlan,
    VillagePlanningBoundary,
    WardPlanningBoundary,
)


def _user_id(user) -> int | None:
    if user and getattr(user, 'is_authenticated', False):
        return user.pk
    return None


def _slug_code(name: str, length: int = 3) -> str:
    if not name:
        return 'XXX'
    normalized = unicodedata.normalize('NFKD', name)
    ascii_name = normalized.encode('ascii', 'ignore').decode('ascii')
    cleaned = re.sub(r'[^A-Za-z0-9]', '', ascii_name).upper()
    return (cleaned[:length] or 'XXX').ljust(length, 'X')


def generate_plot_number(region: str, district: str, ward: str, village: str, sequence: int) -> str:
    """Tengeneza namba ya kiwanja: DP/MKO/WIL/KAT/KIJ/0001"""
    return (
        f'DP/{_slug_code(region)}/{_slug_code(district)}/'
        f'{_slug_code(ward)}/{_slug_code(village)}/{sequence:04d}'
    )


def next_plot_sequence(region: str, district: str, ward: str, village: str) -> int:
    last = (
        PlanningParcel.objects.filter(
            region_name__iexact=region,
            district_name__iexact=district,
            ward_name__iexact=ward,
            village_name__iexact=village,
        )
        .order_by('-plot_sequence')
        .values_list('plot_sequence', flat=True)
        .first()
    )
    return (last or 0) + 1


def _village_plan_group_key(plan: VillageDetailedPlan) -> tuple[str, str, str]:
    """Kitufe cha kikundi — kijiji kimoja kinaweza kuwa na wilaya mbili (mf. Madaba/Songea)."""
    return (
        (plan.region_name or '').strip().lower(),
        (plan.ward_name or '').strip().lower(),
        (plan.village_name or '').strip().lower(),
    )


_PLAN_STATUS_RANK = {'draft': 0, 'prepared': 1, 'approved': 2, 'completed': 3}


def _pick_primary_village_plan(
    plans: list[VillageDetailedPlan],
    *,
    prefer_district: str | None = None,
) -> VillageDetailedPlan:
    """Chagua mpango mmoja kutoka kikundi chenye duplicates."""
    from dashboard.boundary_service import _district_search_names

    if len(plans) == 1:
        return plans[0]

    if prefer_district:
        prefer_clean = prefer_district.strip().lower()
        for plan in plans:
            if (plan.district_name or '').strip().lower() == prefer_clean:
                return plan
        prefer_names = {n.lower() for n in _district_search_names(prefer_district)}
        for plan in plans:
            if (plan.district_name or '').strip().lower() in prefer_names:
                return plan

    for plan in plans:
        if DistrictPlanningBoundary.objects.filter(
            region_name__iexact=plan.region_name,
            district_name__iexact=plan.district_name,
        ).exists():
            return plan

    return max(
        plans,
        key=lambda p: (
            (p.identified_parcels or 0) + (p.unidentified_parcels or 0),
            _PLAN_STATUS_RANK.get(p.plan_status, 0),
            p.updated_at,
        ),
    )


def _merge_village_plan_fields(
    winner: VillageDetailedPlan,
    loser: VillageDetailedPlan,
) -> None:
    """Changanya metadata kutoka rekodi inayofutwa hadi kwenye mpango mkuu."""
    if _PLAN_STATUS_RANK.get(loser.plan_status, 0) > _PLAN_STATUS_RANK.get(winner.plan_status, 0):
        winner.plan_status = loser.plan_status
    for field in (
        'total_landowners', 'female_landowners', 'male_landowners',
        'children_under_18', 'identified_parcels', 'unidentified_parcels',
    ):
        winner_val = getattr(winner, field, 0) or 0
        loser_val = getattr(loser, field, 0) or 0
        setattr(winner, field, max(winner_val, loser_val))
    if not winner.plan_year and loser.plan_year:
        winner.plan_year = loser.plan_year
    if not winner.notes and loser.notes:
        winner.notes = loser.notes


def deduplicate_village_plan_list(
    plans: list[VillageDetailedPlan],
    *,
    prefer_district: str | None = None,
) -> list[VillageDetailedPlan]:
    """Ondoa duplicates za kijiji kimoja (wilaya tofauti kwa sababu ya alias)."""
    groups: dict[tuple[str, str, str], list[VillageDetailedPlan]] = {}
    for plan in plans:
        groups.setdefault(_village_plan_group_key(plan), []).append(plan)

    deduped = [
        _pick_primary_village_plan(group, prefer_district=prefer_district)
        for group in groups.values()
    ]
    return sorted(
        deduped,
        key=lambda p: (
            (p.region_name or '').lower(),
            (p.district_name or '').lower(),
            (p.ward_name or '').lower(),
            (p.village_name or '').lower(),
        ),
    )


@transaction.atomic(using='detailed_planning')
def merge_duplicate_village_plans(
    *,
    region: str | None = None,
    district: str | None = None,
    ward: str | None = None,
    village: str | None = None,
    prefer_district: str | None = None,
) -> int:
    """Unganisha rekodi za village_plans zinazofanana (mf. Mwande Madaba + Songea)."""
    from django.db.models import Q

    from dashboard.boundary_service import _district_search_names

    q = Q()
    if region:
        q &= Q(region_name__iexact=region)
    if district:
        district_q = Q()
        for name in _district_search_names(district):
            district_q |= Q(district_name__iexact=name)
        q &= district_q
    if ward:
        q &= Q(ward_name__iexact=ward)
    if village:
        q &= Q(village_name__iexact=village)

    plans = list(VillageDetailedPlan.objects.filter(q))
    groups: dict[tuple[str, str, str], list[VillageDetailedPlan]] = {}
    for plan in plans:
        groups.setdefault(_village_plan_group_key(plan), []).append(plan)

    merged = 0
    for group in groups.values():
        if len(group) <= 1:
            continue
        winner = _pick_primary_village_plan(group, prefer_district=prefer_district or district)
        for loser in group:
            if loser.pk == winner.pk:
                continue
            PlanningParcel.objects.filter(village_plan=loser).update(village_plan=winner)
            PlanningShapefile.objects.filter(village_plan=loser).update(village_plan=winner)
            PlanningReport.objects.filter(village_plan=loser).update(village_plan=winner)
            _merge_village_plan_fields(winner, loser)
            loser.delete()
            merged += 1
        winner.sync_parcel_counts()
        winner.save()

    return merged


def get_or_create_village_plan(region: str, district: str, ward: str, village: str) -> VillageDetailedPlan:
    from django.db.models import Q

    from dashboard.boundary_service import _district_search_names

    district_q = Q()
    for name in _district_search_names(district):
        district_q |= Q(district_name__iexact=name)
    existing = (
        VillageDetailedPlan.objects.filter(
            Q(region_name__iexact=region)
            & district_q
            & Q(ward_name__iexact=ward)
            & Q(village_name__iexact=village)
        )
        .order_by('-updated_at')
        .first()
    )
    if existing:
        return existing

    plan, _ = VillageDetailedPlan.objects.get_or_create(
        region_name=region,
        district_name=district,
        ward_name=ward,
        village_name=village,
        defaults={'plan_status': 'draft'},
    )
    return plan


@transaction.atomic(using='detailed_planning')
def create_planning_parcel(
    region: str,
    district: str,
    ward: str,
    village: str,
    *,
    geom=None,
    area_ha=None,
    is_identified: bool = False,
    owner_name: str | None = None,
    owner_gender: str | None = None,
    owner_age_category: str | None = None,
    owner_is_landowner: bool = True,
    notes: str | None = None,
    created_by=None,
) -> PlanningParcel:
    plan = get_or_create_village_plan(region, district, ward, village)
    seq = next_plot_sequence(region, district, ward, village)
    parcel_number = generate_plot_number(region, district, ward, village, seq)

    parcel = PlanningParcel.objects.create(
        parcel_number=parcel_number,
        plot_sequence=seq,
        region_name=region,
        district_name=district,
        ward_name=ward,
        village_name=village,
        geom=geom,
        area_ha=area_ha,
        is_identified=is_identified,
        owner_name=owner_name,
        owner_gender=owner_gender,
        owner_age_category=owner_age_category,
        owner_is_landowner=owner_is_landowner,
        notes=notes,
        village_plan=plan,
        created_by_id=_user_id(created_by),
    )
    _refresh_plan_stats(plan)
    return parcel


def _refresh_plan_stats(plan: VillageDetailedPlan) -> None:
    plan.sync_parcel_counts()


def geojson_to_multipolygon(geojson_geom: dict, source_srid: int = 4326) -> MultiPolygon | None:
    """Badilisha GeoJSON geometry → MultiPolygon (SRID 32736). Chanzo cha kawaida ni WGS84."""
    if not geojson_geom:
        return None
    geom = GEOSGeometry(str(geojson_geom), srid=source_srid)
    if geom.srid != 32736:
        geom.transform(32736)
    geom.srid = 32736
    if geom.geom_type == 'Polygon':
        result = MultiPolygon(geom)
    elif geom.geom_type == 'MultiPolygon':
        result = geom
    else:
        return None
    result.srid = 32736
    return result


# Sifa za viwanja kutoka shapefile (GIS Portal / import)
_REGION_FIELDS = ('reg_name', 'REG_NAME', 'Region', 'REGION', 'Mkoa', 'MKOA', 'region_name')
_DISTRICT_FIELDS = ('dist_name', 'DIST_NAME', 'District', 'DISTRICT', 'Wilaya', 'WILAYA', 'district_name')
_WARD_FIELDS = ('ward_name', 'WARD_NAME', 'Ward', 'WARD', 'Kata', 'KATA')
_VILLAGE_FIELDS = (
    'village_name', 'VILLAGE_NAME', 'village_na', 'VILLAGE_NA', 'VILLAGE_N',
    'Village', 'VILLAGE', 'Kijiji', 'KIJIJI', 'jina_kijiji', 'Jina_Kijiji', 'JINA_KIJIJI',
    'vill_name', 'VILL_NAME', 'Vil_Name', 'VIL_NAME', 'village', 'kijiji',
    'Nama_Kijiji', 'nama_kijiji', 'Local_Village', 'VLG_NAME', 'vlg_name',
)
_OWNER_FIELDS = (
    'owner_name', 'OWNER_NAME', 'owner_na', 'OWNER_NA', 'owner', 'OWNER',
    'Owner_Name', 'mmiliki', 'MMILIKI', 'landowner', 'LANDOWNER', 'name', 'NAME',
    'PARTIES', 'parties',
)
_GENDER_FIELDS = ('gender', 'GENDER', 'sex', 'SEX', 'owner_gender', 'OWNER_GENDER', 'jinsia', 'JINSIA')
_AGE_CAT_FIELDS = ('age_category', 'AGE_CATEGORY', 'age_cat', 'AGE_CAT', 'age_group', 'AGE_GROUP')
_AGE_FIELDS = ('age', 'AGE', 'umri', 'UMRI')
_IDENTIFIED_FIELDS = (
    'is_identified', 'IS_IDENTIFIED', 'identified', 'IDENTIFIED', 'tambuliwa', 'TAMBULIWA', 'status', 'STATUS',
)
_PARCEL_NUM_FIELDS = (
    'parcel_number', 'PARCEL_NUMBER', 'parcel_no', 'PARCEL_NO', 'plot_no', 'PLOT_NO',
    'plot_number', 'PLOT_NUMBER', 'kiwanja_no', 'KIWANJA_NO', 'namba', 'NAMBA',
)
_NOTES_FIELDS = ('notes', 'NOTES', 'remarks', 'REMARKS', 'maelezo', 'MAELEZO', 'Toa_maoni_', 'TOA_MAONI_')


def _clean_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip().rstrip(',')
    if text in ('-', '_', '—', '–'):
        return None
    return text or None


def _pick_from_props(props: dict, candidates: tuple[str, ...]) -> str | None:
    if not props:
        return None
    for key in candidates:
        if key in props and props[key] not in (None, ''):
            return _clean_text(props[key])
    lower_map = {k.lower(): k for k in props}
    for key in candidates:
        actual = lower_map.get(key.lower())
        if actual is not None and props[actual] not in (None, ''):
            return _clean_text(props[actual])
    return None


def _infer_village_from_name(name: str | None) -> str | None:
    """Fallback kutoka jina la faili (vijiji maarufu). Priority iko kwenye column ya Kijiji."""
    lower = (name or '').lower()
    if 'igawisenga' in lower or 'igawis' in lower:
        return 'Igawisenga'
    if 'mwande' in lower:
        return 'Mwande'
    if 'maweso' in lower:
        return 'Maweso'
    return None


def _normalize_place_name(name: str) -> str:
    """Safisha jina la kijiji/kata — Title Case bila kubadilisha maana."""
    parts = [p for p in str(name).replace('_', ' ').split() if p]
    return ' '.join(p[:1].upper() + p[1:].lower() if len(p) > 1 else p.upper() for p in parts)


def _pick_village_from_props(props: dict) -> str | None:
    """Soma column ya kijiji kutoka sifa za shapefile (Kijiji / village / …)."""
    val = _pick_from_props(props, _VILLAGE_FIELDS)
    if val:
        return val
    if not props:
        return None
    for key, raw in props.items():
        kl = str(key).lower().replace(' ', '_').replace('-', '_')
        if not any(tok in kl for tok in ('kijiji', 'village', 'vill_name', 'vil_name', 'vlg_name')):
            continue
        if kl.endswith('_id') or kl in ('village_id', 'kijiji_id'):
            continue
        cleaned = _clean_text(raw)
        if cleaned:
            return cleaned
    return None


def _known_villages_in_area(
    region: str | None,
    district: str | None,
    ward: str | None,
) -> list[str]:
    """Orodha ya vijiji vinavyojulikana kwenye eneo (plans, mipaka, parcels)."""
    names: set[str] = set()
    if not region:
        return []

    plan_q = VillageDetailedPlan.objects.filter(region_name__iexact=region)
    bound_q = VillagePlanningBoundary.objects.filter(region_name__iexact=region)
    parcel_q = PlanningParcel.objects.filter(region_name__iexact=region)
    if district:
        plan_q = plan_q.filter(_district_name_q(district))
        bound_q = bound_q.filter(_district_name_q(district))
        parcel_q = parcel_q.filter(_district_name_q(district))
    if ward:
        plan_q = plan_q.filter(ward_name__iexact=ward)
        bound_q = bound_q.filter(ward_name__iexact=ward)
        parcel_q = parcel_q.filter(ward_name__iexact=ward)

    for qs in (plan_q, bound_q, parcel_q):
        for n in qs.values_list('village_name', flat=True).distinct():
            if n and str(n).strip():
                names.add(str(n).strip())
    return sorted(names, key=lambda x: x.lower())


def _match_village_name(raw: str, known: list[str] | None) -> str | None:
    """Linganisha jina la kijiji na orodha ya kata/eneo (case-insensitive)."""
    cleaned = _clean_text(raw)
    if not cleaned:
        return None
    if not known:
        return _normalize_place_name(cleaned)
    key = cleaned.lower()
    for name in known:
        if name.lower() == key:
            return name
    for name in known:
        nl = name.lower()
        if nl.startswith(key) or key.startswith(nl):
            return name
    for name in known:
        if key in name.lower() or name.lower() in key:
            return name
    return _normalize_place_name(cleaned)


def resolve_village_for_feature(
    props: dict | None,
    *,
    ui_village: str | None = None,
    shapefile_name: str | None = None,
    known_villages: list[str] | None = None,
) -> str | None:
    """
    Amua kijiji cha feature:
    1) Column Kijiji/village kwenye shapefile (kipaumbele)
    2) Kijiji kilichochaguliwa kwenye UI
    3) Jina la faili (fallback)
    Kisha linganisha na vijiji vya kata husika.
    """
    props = props or {}
    raw = (
        _pick_village_from_props(props)
        or _clean_text(ui_village)
        or _infer_village_from_name(shapefile_name)
        or _infer_village_from_name(_clean_text(props.get('source_layer')))
    )
    if not raw:
        return None
    return _match_village_name(raw, known_villages)


def _normalize_gender(raw: str | None) -> str | None:
    if not raw:
        return None
    val = raw.strip().upper()
    if val in ('M', 'MALE', 'MWANAUME', 'ME', 'MAN', '1'):
        return 'M'
    if val in ('F', 'FEMALE', 'MWANAMKE', 'KE', 'WOMAN', '2'):
        return 'F'
    if val in ('U', 'UNKNOWN', 'HAIJULIKANI', '0'):
        return 'U'
    if val.startswith('M'):
        return 'M'
    if val.startswith('F'):
        return 'F'
    return 'U'


def _normalize_age_category(raw: str | None, age_value=None) -> str | None:
    if raw:
        val = raw.strip().lower()
        if val in ('child', 'mtoto', 'minor', 'under18', 'under_18', 'c'):
            return 'child'
        if val in ('adult', 'mzima', 'major', 'a'):
            return 'adult'
    if age_value is not None:
        try:
            age = int(float(age_value))
            return 'child' if age < 18 else 'adult'
        except (TypeError, ValueError):
            pass
    return None


# Sifa zinazofanya kiwanja kiwe "kilichotambuliwa" (CCRO / Mpangokinaa)
_IDENTIFICATION_DETAIL_FIELDS = (
    'owner_name', 'parties', 'claim_no', 'pid', 'land_use', 'land_title_name',
    'ownership_type', 'hamlet', 'kitongoji', 'paras', 'neighbor_north',
    'neighbor_south', 'neighbor_west', 'neighbor_east', 'spouse', 'children',
    'others', 'topography', 'season', 'right_of_way', 'witness_1', 'witness_2',
    'remarks', 'claim_date', 'shp_village',
)

_GEOJSON_CCRO_FIELD_MAP: dict[str, tuple[str, ...]] = {
    'pid': ('PID', 'pid'),
    'claim_no': ('CLAIM_NO', 'claim_no', 'CLAIM', 'claim'),
    'claim_date': ('DATE_', 'claim_date', 'CLAIM_DATE'),
    'paras': ('PARAS', 'paras'),
    'hamlet': ('HAMLET', 'hamlet', 'Kitongoji', 'KITONGOJI'),
    'parties': ('PARTIES', 'parties'),
    'neighbor_north': ('Kaskazini', 'kaskazini', 'neighbor_north', 'NEIGHBOR_NORTH'),
    'neighbor_south': ('Kusini', 'kusini', 'neighbor_south', 'NEIGHBOR_SOUTH'),
    'neighbor_west': ('Magharibi', 'magharibi', 'neighbor_west', 'NEIGHBOR_WEST'),
    'neighbor_east': ('Mashariki', 'mashariki', 'neighbor_east', 'NEIGHBOR_EAST'),
    'spouse': ('Wenza', 'WENZA', 'spouse', 'SPOUSE'),
    'children': ('Watoto', 'WATOTO', 'children', 'CHILDREN'),
    'others': ('Wengineo', 'wengineo', 'others', 'OTHERS'),
    'kitongoji': ('Kitongoji', 'KITONGOJI', 'kitongoji'),
    'topography': ('Topolijia', 'topography', 'TOPOGRAPHY'),
    'season': ('Majira_ya_', 'Majira ya', 'season', 'SEASON'),
    'right_of_way': ('Haki_ya_Nj', 'Haki ya Njia', 'right_of_way', 'RIGHT_OF_WAY'),
    'witness_1': ('Shahidi_wa', 'witness_1', 'WITNESS_1'),
    'witness_2': ('Shahidi__1', 'witness_2', 'WITNESS_2'),
    'remarks': ('Toa_maoni_', 'TOA_MAONI_', 'remarks', 'REMARKS'),
    'shp_village': ('VILLAGE', 'village_na', 'VILLAGE_NA', 'Kijiji', 'KIJIJI', 'shp_village'),
    'land_title_name': ('Jina_la_Ta', 'land_title_name', 'LAND_TITLE_NAME'),
    'land_use': ('Matumizi_y', 'MATUMIZI_Y', 'Matumizi_1', 'land_use', 'LAND_USE'),
    'ownership_type': ('Umiliki', 'UMILIKI', 'ownership', 'OWNERSHIP', 'ownership_type'),
}


def _parse_identified_flag(raw) -> bool | None:
    """Thamani ya moja kwa moja kutoka shapefile/GeoJSON; None = haijabainishwa."""
    if raw is None:
        return None
    val = str(raw).strip().lower()
    if val in ('1', 'true', 'yes', 'y', 'imetambuliwa', 'identified', 'tambuliwa'):
        return True
    if val in ('0', 'false', 'no', 'n', 'haijatambuliwa', 'unidentified', 'visivyotambuliwa'):
        return False
    return None


def compute_is_identified(*, raw=None, **fields) -> bool:
    """Imetambuliwa ikiwa kuna maelezo ya CCRO/mmiliki; visivyotambuliwa ikiwa tupu."""
    explicit = _parse_identified_flag(raw)
    if explicit is not None:
        return explicit
    for field in _IDENTIFICATION_DETAIL_FIELDS:
        if _clean_text(fields.get(field)):
            return True
    return False


def _extract_ccro_attrs_from_props(props: dict) -> dict[str, str]:
    """Chukua sifa za CCRO kutoka GeoJSON properties."""
    attrs: dict[str, str] = {}
    if not props:
        return attrs
    for model_field, candidates in _GEOJSON_CCRO_FIELD_MAP.items():
        val = _pick_from_props(props, candidates)
        if val:
            attrs[model_field] = val
    return attrs


def identification_fields_from_parcel(parcel: PlanningParcel) -> dict:
    """Thamani za sifa zinazotumika kuamua is_identified kwa rekodi ya DB."""
    return {field: getattr(parcel, field, None) for field in _IDENTIFICATION_DETAIL_FIELDS}


def apply_identification_to_parcel(parcel: PlanningParcel, *, save: bool = False) -> bool:
    """Hesabu na (hiari) hifadhi is_identified kwa kiwanja kimoja."""
    new_val = compute_is_identified(**identification_fields_from_parcel(parcel))
    if parcel.is_identified != new_val:
        parcel.is_identified = new_val
        if save:
            parcel.save(update_fields=['is_identified', 'updated_at'])
        return True
    return False


def normalize_import_district(feat_district: str | None, upload_district: str | None) -> str | None:
    """Tumia jina la wilaya kutoka upload ikiwa linalingana na alias (mf. Songea ↔ Madaba)."""
    from dashboard.boundary_service import _district_search_names

    feat = _clean_text(feat_district)
    upload = _clean_text(upload_district)
    if not upload:
        return feat
    if not feat:
        return upload
    alias_set = {n.lower() for n in _district_search_names(upload)}
    if feat.lower() in alias_set:
        return upload
    return feat


def _district_name_q(district: str):
    """OR-filter kwa jina la wilaya na aliases (mf. Madaba ↔ Songea)."""
    from dashboard.boundary_service import _district_search_names
    from django.db.models import Q

    names = _district_search_names(district)
    if not names:
        return Q()
    clause = Q()
    for name in names:
        clause |= Q(district_name__iexact=name)
    return clause


def _canonical_import_district(upload_district: str | None, props_district: str | None) -> str | None:
    """Daima tumia wilaya iliyochaguliwa kwenye ramani (upload) kwa ulinganifu na filters."""
    upload = _clean_text(upload_district)
    if upload:
        return upload
    return normalize_import_district(_clean_text(props_district), upload_district)


@transaction.atomic(using='detailed_planning')
def import_parcels_from_geojson(
    feature_collection: dict,
    *,
    region: str,
    district: str,
    ward: str | None = None,
    village: str | None = None,
    shapefile_name: str | None = None,
    created_by=None,
) -> dict:
    """Ingiza viwanja kutoka GeoJSON (WGS84) kwenye planning_parcels baada ya upload ya GIS Portal.

    Kijiji husomwa kutoka column ya shapefile (Kijiji / village / …) kwa kila feature,
    kisha kinalinganishwa na vijiji vya kata husika. UI village ni fallback.
    """
    features = feature_collection.get('features') or []
    filename_hint = _infer_village_from_name(shapefile_name)
    ui_village = _clean_text(village)
    canonical_district = _clean_text(district)
    canonical_ward = _clean_text(ward)
    known_villages = _known_villages_in_area(region, canonical_district, canonical_ward)

    created = updated = skipped = 0
    skipped_no_village = 0
    villages_touched: set[tuple[str, str, str, str]] = set()
    seq_cache: dict[tuple[str, str, str, str], int] = {}
    resolved_villages: set[str] = set()
    villages_from_column: set[str] = set()
    missing_village_column = 0

    for feature in features:
        props = feature.get('properties') or {}
        feat_region = _pick_from_props(props, _REGION_FIELDS) or region
        feat_district = _canonical_import_district(
            district,
            _pick_from_props(props, _DISTRICT_FIELDS) or district,
        )
        feat_ward = (
            _pick_from_props(props, _WARD_FIELDS)
            or canonical_ward
            or ward
        )

        ccro_attrs = _extract_ccro_attrs_from_props(props)
        column_village = _pick_village_from_props(props) or _clean_text(ccro_attrs.get('shp_village'))
        if not column_village:
            missing_village_column += 1

        feat_village = resolve_village_for_feature(
            props,
            ui_village=ui_village,
            shapefile_name=shapefile_name,
            known_villages=known_villages,
        )
        if column_village and feat_village:
            villages_from_column.add(feat_village)

        if not all([feat_region, feat_district, feat_ward]):
            skipped += 1
            continue
        if not feat_village:
            skipped += 1
            skipped_no_village += 1
            continue

        geom = geojson_to_multipolygon(feature.get('geometry'))
        if geom is None:
            skipped += 1
            continue
        if shapefile_name:
            ccro_attrs.setdefault('shapefile_name', shapefile_name)
            ccro_attrs.setdefault('source_layer', Path(shapefile_name).stem if shapefile_name else None)
            ccro_attrs.setdefault('source_path', shapefile_name)
        owner_name = _pick_from_props(props, _OWNER_FIELDS) or ccro_attrs.get('parties')
        owner_gender = _normalize_gender(_pick_from_props(props, _GENDER_FIELDS))
        age_field = _pick_from_props(props, _AGE_FIELDS)
        age_raw = props.get(age_field) if age_field else None
        owner_age_category = _normalize_age_category(
            _pick_from_props(props, _AGE_CAT_FIELDS),
            age_raw,
        )
        is_identified = compute_is_identified(
            raw=_pick_from_props(props, _IDENTIFIED_FIELDS),
            owner_name=owner_name,
            **ccro_attrs,
        )
        notes = _pick_from_props(props, _NOTES_FIELDS)
        shp_parcel_no = _pick_from_props(props, _PARCEL_NUM_FIELDS)
        if shp_parcel_no and not notes:
            notes = f'SHP namba: {shp_parcel_no}'

        area_ha = round(geom.area / 10_000.0, 4)
        loc_key = (feat_region, feat_district, feat_ward, feat_village)
        villages_touched.add(loc_key)
        resolved_villages.add(feat_village)

        if loc_key not in seq_cache:
            seq_cache[loc_key] = next_plot_sequence(
                feat_region, feat_district, feat_ward, feat_village,
            )

        existing = PlanningParcel.objects.filter(
            region_name__iexact=feat_region,
            ward_name__iexact=feat_ward,
            village_name__iexact=feat_village,
            geom=geom,
        ).filter(_district_name_q(feat_district)).first()

        if existing:
            if existing.district_name != feat_district:
                existing.district_name = feat_district
            existing.owner_name = owner_name or existing.owner_name
            existing.owner_gender = owner_gender or existing.owner_gender
            existing.owner_age_category = owner_age_category or existing.owner_age_category
            existing.area_ha = area_ha
            if notes:
                existing.notes = notes
            for field, value in ccro_attrs.items():
                setattr(existing, field, value)
            if shapefile_name:
                existing.shapefile_name = shapefile_name
                if not existing.source_layer:
                    existing.source_layer = Path(shapefile_name).stem
                if not existing.source_path:
                    existing.source_path = shapefile_name
            apply_identification_to_parcel(existing, save=False)
            existing.save()
            updated += 1
            continue

        seq = seq_cache[loc_key]
        seq_cache[loc_key] = seq + 1
        parcel_number = generate_plot_number(feat_region, feat_district, feat_ward, feat_village, seq)
        plan = get_or_create_village_plan(feat_region, feat_district, feat_ward, feat_village)

        create_kwargs = {
            'parcel_number': parcel_number,
            'plot_sequence': seq,
            'region_name': feat_region,
            'district_name': feat_district,
            'ward_name': feat_ward,
            'village_name': feat_village,
            'geom': geom,
            'area_ha': area_ha,
            'is_identified': is_identified,
            'owner_name': owner_name,
            'owner_gender': owner_gender,
            'owner_age_category': owner_age_category,
            'owner_is_landowner': True,
            'notes': notes,
            'village_plan': plan,
            'created_by_id': _user_id(created_by),
            **ccro_attrs,
        }
        if shapefile_name:
            create_kwargs['shapefile_name'] = shapefile_name
        PlanningParcel.objects.create(**create_kwargs)
        created += 1

    for loc in villages_touched:
        plan = VillageDetailedPlan.objects.filter(
            region_name__iexact=loc[0],
            district_name__iexact=loc[1],
            ward_name__iexact=loc[2],
            village_name__iexact=loc[3],
        ).first()
        if plan:
            _refresh_plan_stats(plan)

    village_out = ui_village or filename_hint
    if len(resolved_villages) == 1:
        village_out = next(iter(resolved_villages))
    elif resolved_villages:
        village_out = ', '.join(sorted(resolved_villages))

    warning = None
    if missing_village_column and (created + updated) > 0:
        warning = (
            'Baadhi ya viwanja havikuwa na column Kijiji/village. '
            'Ongeza column "Kijiji" (au village) kwenye shapefile na andika jina la kijiji husika.'
        )
    if skipped_no_village:
        warning = (
            (warning + ' ') if warning else ''
        ) + (
            f'{skipped_no_village} viwanja vimerukwa — hakuna jina la kijiji '
            '(weka column Kijiji au chagua kijiji kwenye UI).'
        )

    return {
        'created': created,
        'updated': updated,
        'skipped': skipped,
        'skipped_no_village': skipped_no_village,
        'missing_village_column': missing_village_column,
        'village': village_out,
        'villages': sorted(resolved_villages),
        'villages_from_column': sorted(villages_from_column),
        'known_villages_in_ward': known_villages,
        'warning': warning,
    }


def save_boundary_from_geojson(
    level: str,
    region: str,
    district: str,
    ward: str | None,
    village: str | None,
    geojson_feature: dict,
    shapefile_name: str | None = None,
    created_by=None,
):
    props = geojson_feature.get('properties') or {}
    geom = geojson_to_multipolygon(geojson_feature.get('geometry'))
    area_ha = props.get('area_ha') or props.get('AREA_HA')

    region = region or props.get('region_name') or props.get('REGION') or ''
    district = district or props.get('district_name') or props.get('DISTRICT') or ''
    ward = ward or props.get('ward_name') or props.get('WARD') or ''
    village = village or props.get('village_name') or props.get('VILLAGE') or ''

    if level == 'district':
        obj, _ = DistrictPlanningBoundary.objects.update_or_create(
            region_name=region,
            district_name=district,
            defaults={
                'geom': geom,
                'shapefile_name': shapefile_name,
                'area_ha': area_ha,
                'created_by_id': _user_id(created_by),
            },
        )
        return obj

    if level == 'ward':
        obj, _ = WardPlanningBoundary.objects.update_or_create(
            region_name=region,
            district_name=district,
            ward_name=ward,
            defaults={
                'geom': geom,
                'shapefile_name': shapefile_name,
                'area_ha': area_ha,
                'created_by_id': _user_id(created_by),
            },
        )
        return obj

    if level == 'village':
        obj, _ = VillagePlanningBoundary.objects.update_or_create(
            region_name=region,
            district_name=district,
            ward_name=ward,
            village_name=village,
            defaults={
                'geom': geom,
                'shapefile_name': shapefile_name,
                'area_ha': area_ha,
                'created_by_id': _user_id(created_by),
            },
        )
        return obj

    raise ValueError(f'Kiwango kisichojulikana: {level}')


BOUNDARY_LEVELS = ('district', 'ward', 'village')

# data_type kutoka GIS Portal → level ya boundary
BOUNDARY_DATA_TYPE_MAP = {
    'district_boundary': 'district',
    'ward_boundary': 'ward',
    'village_boundary': 'village',
    'district': 'district',
    'ward': 'ward',
    'village': 'village',
}


def import_boundaries_from_geojson(
    feature_collection: dict,
    *,
    level: str,
    region: str,
    district: str,
    ward: str | None = None,
    village: str | None = None,
    shapefile_name: str | None = None,
    created_by=None,
) -> dict:
    """Hifadhi mipaka (district/ward/village) kutoka GeoJSON kwenye detailed_planning."""
    level = (level or '').strip().lower()
    if level not in BOUNDARY_LEVELS:
        raise ValueError(f'Kiwango kisichojulikana: {level}. Tumia district, ward au village.')

    region = _clean_text(region) or ''
    district = _clean_text(district) or ''
    ward = _clean_text(ward)
    village = _clean_text(village)
    known_villages = _known_villages_in_area(region, district, ward)

    if level in ('ward', 'village') and not ward:
        raise ValueError('Kata (ward) inahitajika kwa mipaka ya kata/kijiji')
    if not region or not district:
        raise ValueError('Mkoa na wilaya vinahitajika')

    features = feature_collection.get('features') or []
    saved = 0
    skipped = 0
    errors: list[str] = []

    for feature in features:
        try:
            props = feature.get('properties') or {}
            feat_village = None
            if level == 'village':
                feat_village = resolve_village_for_feature(
                    props,
                    ui_village=village,
                    shapefile_name=shapefile_name,
                    known_villages=known_villages,
                )
                if not feat_village:
                    skipped += 1
                    errors.append(
                        'Kijiji hakijulikani — weka column Kijiji/village kwenye shapefile'
                    )
                    continue

            save_boundary_from_geojson(
                level,
                region,
                district,
                ward if level in ('ward', 'village') else None,
                feat_village if level == 'village' else None,
                feature,
                shapefile_name=shapefile_name,
                created_by=created_by,
            )
            saved += 1
            # Sync Locality (Wilaya / Kata) baada ya kuhifadhi mipaka
            if level in ('district', 'ward'):
                try:
                    from dashboard.locality_sync import sync_locality_from_names

                    props = feature.get('properties') or {}
                    dist_name = district or props.get('district_name') or props.get('DISTRICT') or ''
                    ward_name = (ward or props.get('ward_name') or props.get('WARD') or '') if level == 'ward' else None
                    sync_locality_from_names(
                        level=level,
                        region=region,
                        district=str(dist_name).strip(),
                        ward=str(ward_name).strip() if ward_name else None,
                    )
                except Exception:
                    pass
        except Exception as exc:
            skipped += 1
            errors.append(str(exc))

    return {
        'level': level,
        'saved': saved,
        'skipped': skipped,
        'errors': errors[:5],
        'region': region,
        'district': district,
        'ward': ward or '',
        'village': village or '',
    }


def _geom_to_wgs84_dict(geom) -> dict | None:
    import json

    if not geom:
        return None
    g = geom
    if g.srid != 4326:
        g = g.clone()
        g.transform(4326)
    return json.loads(g.geojson)


def boundary_to_geojson(boundary, *, name: str | None = None, feature_type: str | None = None) -> dict | None:
    geometry = _geom_to_wgs84_dict(getattr(boundary, 'geom', None))
    if not boundary or not geometry:
        return None
    props = {
        'region_name': getattr(boundary, 'region_name', ''),
        'district_name': getattr(boundary, 'district_name', ''),
        'ward_name': getattr(boundary, 'ward_name', ''),
        'village_name': getattr(boundary, 'village_name', ''),
    }
    if name:
        props['name'] = name
    elif getattr(boundary, 'village_name', ''):
        props['name'] = boundary.village_name
    elif getattr(boundary, 'ward_name', ''):
        props['name'] = boundary.ward_name
    elif getattr(boundary, 'district_name', ''):
        props['name'] = boundary.district_name
    if feature_type:
        props['type'] = feature_type
    return {
        'type': 'Feature',
        'geometry': geometry,
        'properties': props,
    }


def boundaries_to_feature_collection(queryset, *, name_attr: str, feature_type: str) -> dict:
    features = []
    for obj in queryset:
        name = getattr(obj, name_attr, '') or ''
        feature = boundary_to_geojson(obj, name=name, feature_type=feature_type)
        if feature:
            features.append(feature)
    return {'type': 'FeatureCollection', 'features': features}


def _safe_path_segment(name: str) -> str:
    if not name:
        return 'unknown'
    return re.sub(r'[^A-Za-z0-9_-]', '_', name)[:80]


def save_planning_report_file(
    uploaded_file,
    *,
    report_type: str,
    region: str,
    district: str | None = None,
    ward: str | None = None,
    village: str | None = None,
    title: str | None = None,
    report_year: int | None = None,
    village_plan: VillageDetailedPlan | None = None,
    generated_by=None,
) -> PlanningReport:
    """Hifadhi PDF ya ripoti au ramani kwenye media na rekodi ya DB."""
    ext = os.path.splitext(uploaded_file.name)[1].lower() or '.pdf'
    stored_name = f'{uuid.uuid4().hex}{ext}'
    rel_parts = [
        'planning_reports',
        _safe_path_segment(region),
        _safe_path_segment(district or ''),
        _safe_path_segment(ward or ''),
        _safe_path_segment(village or ''),
    ]
    rel_dir = '/'.join(p for p in rel_parts if p)
    rel_path = f'{rel_dir}/{stored_name}'
    saved_path = default_storage.save(rel_path, uploaded_file)

    if not title:
        if report_type == 'boundary_map':
            title = f'Ramani — {village or ward or district or region}'
        elif report_type == 'quarter_report':
            title = f'Quarter Report — {district or region}'
        elif report_type == 'section_minutes':
            title = f'Minutes za Vikao — {district or region}'
        else:
            title = f'Ripoti — {village or ward or district or region}'

    fmt = 'pdf'
    if ext in ('.doc', '.docx'):
        fmt = 'docx'
    elif ext == '.xlsx':
        fmt = 'xlsx'
    elif ext == '.csv':
        fmt = 'csv'

    return PlanningReport.objects.create(
        title=title,
        report_type=report_type,
        region_name=region,
        district_name=district,
        ward_name=ward,
        village_name=village,
        report_year=report_year,
        original_filename=uploaded_file.name,
        stored_filename=stored_name,
        file_path=saved_path,
        file_format=fmt,
        file_size_bytes=getattr(uploaded_file, 'size', None),
        village_plan=village_plan,
        generated_by_id=_user_id(generated_by),
    )


def parcels_for_location(
    region: str | None = None,
    district: str | None = None,
    ward: str | None = None,
    village: str | None = None,
):
    """Queryset ya viwanja kwa eneo — inaheshimu aliases za wilaya (mf. Madaba/Songea)."""
    from django.db.models import Q

    from dashboard.boundary_service import _district_search_names

    q = Q()
    if region:
        q &= Q(region_name__iexact=region)
    if district:
        district_q = Q()
        for name in _district_search_names(district):
            district_q |= Q(district_name__iexact=name)
        q &= district_q
    if ward:
        q &= Q(ward_name__iexact=ward)
    if village:
        q &= Q(village_name__iexact=village)
    return PlanningParcel.objects.filter(q)


def planning_landowners_queryset(parcels):
    """Viwanja vilivyo na mmiliki au vilivyotambuliwa."""
    from django.db.models import Q

    return parcels.filter(
        Q(is_identified=True)
        | Q(owner_is_landowner=True)
        | (Q(owner_name__isnull=False) & ~Q(owner_name=''))
    )


def parcel_stats_from_queryset(parcels) -> dict:
    """Takwimu za Mpango Kinaa / CCRO kutoka planning_parcels."""
    from django.db.models import Q

    landowners = planning_landowners_queryset(parcels)
    identified = parcels.filter(is_identified=True).count()
    unidentified = parcels.filter(is_identified=False).count()
    male = landowners.filter(owner_gender='M').count()
    female = landowners.filter(owner_gender='F').count()
    gender_unknown = landowners.filter(
        Q(owner_gender='U') | Q(owner_gender__isnull=True) | Q(owner_gender='')
    ).count()
    adult = landowners.filter(owner_age_category='adult').count()
    child = landowners.filter(owner_age_category='child').count()
    age_unknown = landowners.exclude(owner_age_category__in=['adult', 'child']).count()
    total_landowners = landowners.count()

    return {
        'total_landowners': total_landowners,
        'waliomiliki': total_landowners,
        'female_landowners': female,
        'male_landowners': male,
        'gender_unknown': gender_unknown,
        'children_under_18': child,
        'adult_landowners': adult,
        'age_unknown': age_unknown,
        'identified_parcels': identified,
        'unidentified_parcels': unidentified,
        'total_parcels': parcels.count(),
        'by_gender': {
            'male': male,
            'female': female,
            'unknown': gender_unknown,
        },
        'by_age': {
            'adult': adult,
            'child_under_18': child,
            'unknown': age_unknown,
        },
        'special_groups': {
            'children_under_18': child,
            'unidentified_parcels': unidentified,
            'identified_parcels': identified,
            'gender_unknown': gender_unknown,
            'age_unknown': age_unknown,
        },
    }


def serialize_village_plan(
    plan: VillageDetailedPlan,
    *,
    prefer_district: str | None = None,
) -> dict:
    status_labels = dict(VillageDetailedPlan.PLAN_STATUS)
    stats = parcel_stats_from_queryset(
        parcels_for_location(plan.region_name, plan.district_name, plan.ward_name, plan.village_name)
    )
    district_name = plan.district_name
    if prefer_district:
        from dashboard.boundary_service import _district_search_names

        alias_names = {n.lower() for n in _district_search_names(prefer_district)}
        if (district_name or '').strip().lower() in alias_names:
            district_name = prefer_district
    return {
        'id': str(plan.id),
        'region_name': plan.region_name,
        'district_name': district_name,
        'ward_name': plan.ward_name,
        'village_name': plan.village_name,
        **stats,
        'plan_status': plan.plan_status,
        'plan_status_label': status_labels.get(plan.plan_status, plan.plan_status),
        'plan_year': plan.plan_year,
        'financial_year': getattr(plan, 'financial_year', None) or '',
        'notes': plan.notes or '',
        'updated_at': plan.updated_at.isoformat() if plan.updated_at else None,
    }


def serialize_planning_report(report: PlanningReport) -> dict:
    return {
        'id': str(report.id),
        'title': report.title,
        'report_type': report.report_type,
        'region_name': report.region_name,
        'district_name': report.district_name or '',
        'ward_name': report.ward_name or '',
        'village_name': report.village_name or '',
        'report_year': report.report_year,
        'summary': report.summary or '',
        'notes': report.notes or '',
        'original_filename': report.original_filename,
        'file_size_bytes': report.file_size_bytes,
        'file_format': report.file_format,
        'created_at': report.created_at.isoformat() if report.created_at else None,
        'download_url': f'/api/planning/reports/{report.id}/download/',
    }


def _delete_media_file(file_path: str | None) -> bool:
    """Futa faili kutoka media storage au njia ya kabsoluti."""
    if not file_path:
        return False
    try:
        if default_storage.exists(file_path):
            default_storage.delete(file_path)
            return True
        if os.path.isfile(file_path):
            os.remove(file_path)
            return True
    except OSError:
        pass
    return False


def delete_planning_report(report: PlanningReport) -> None:
    """Futa rekodi ya ripoti na faili yake ya PDF."""
    _delete_media_file(report.file_path)
    report.delete()


def _file_format_from_name(filename: str) -> str:
    ext = os.path.splitext(filename or '')[1].lower()
    if ext in ('.doc', '.docx'):
        return 'docx'
    if ext == '.xlsx':
        return 'xlsx'
    if ext == '.csv':
        return 'csv'
    return 'pdf'


def save_quarter_report_file(
    uploaded_file,
    *,
    title: str | None = None,
    financial_year: str,
    quarter: str,
    notes: str = '',
    generated_by=None,
) -> QuarterReport:
    """Hifadhi Quarter Report kwenye jedwali quarter_reports."""
    from dashboard.financial_year import normalize_financial_year

    ext = os.path.splitext(uploaded_file.name)[1].lower() or '.pdf'
    stored_name = f'{uuid.uuid4().hex}{ext}'
    fy = normalize_financial_year(financial_year)
    q = (quarter or '').strip().upper()
    rel_path = f'quarter_reports/{_safe_path_segment(fy)}/{q}/{stored_name}'
    saved_path = default_storage.save(rel_path, uploaded_file)
    if not title:
        title = f'Quarter Report — {fy} {q}'
    return QuarterReport.objects.create(
        title=title,
        financial_year=fy,
        quarter=q,
        notes=notes or '',
        original_filename=uploaded_file.name,
        stored_filename=stored_name,
        file_path=saved_path,
        file_format=_file_format_from_name(uploaded_file.name),
        file_size_bytes=getattr(uploaded_file, 'size', None),
        created_by_id=_user_id(generated_by),
    )


def serialize_quarter_report(obj: QuarterReport) -> dict:
    return {
        'id': str(obj.id),
        'title': obj.title,
        'report_type': 'quarter_report',
        'financial_year': obj.financial_year,
        'quarter': obj.quarter,
        'summary': obj.quarter,
        'notes': obj.notes or '',
        'original_filename': obj.original_filename,
        'file_size_bytes': obj.file_size_bytes,
        'file_format': obj.file_format,
        'created_at': obj.created_at.isoformat() if obj.created_at else None,
        'download_url': f'/api/planning/quarter-reports/{obj.id}/download/',
    }


def delete_quarter_report(obj: QuarterReport) -> None:
    _delete_media_file(obj.file_path)
    obj.delete()


def save_meeting_minutes_file(
    uploaded_file,
    *,
    title: str | None = None,
    financial_year: str = '',
    meeting_date=None,
    notes: str = '',
    generated_by=None,
) -> MeetingMinutes:
    """Hifadhi Minutes za Vikao kwenye jedwali meeting_minutes."""
    from datetime import date as date_cls

    from dashboard.financial_year import normalize_financial_year

    ext = os.path.splitext(uploaded_file.name)[1].lower() or '.pdf'
    stored_name = f'{uuid.uuid4().hex}{ext}'
    fy = normalize_financial_year(financial_year) if (financial_year or '').strip() else ''
    md = meeting_date
    if isinstance(md, str) and md.strip():
        try:
            md = date_cls.fromisoformat(md.strip()[:10])
        except ValueError:
            md = None
    date_seg = md.isoformat() if md else 'undated'
    rel_path = f'meeting_minutes/{_safe_path_segment(fy or "general")}/{date_seg}/{stored_name}'
    saved_path = default_storage.save(rel_path, uploaded_file)
    if not title:
        title = f'Minutes za Vikao — {md.isoformat() if md else "bila tarehe"}'
    return MeetingMinutes.objects.create(
        title=title,
        financial_year=fy,
        meeting_date=md,
        notes=notes or '',
        original_filename=uploaded_file.name,
        stored_filename=stored_name,
        file_path=saved_path,
        file_format=_file_format_from_name(uploaded_file.name),
        file_size_bytes=getattr(uploaded_file, 'size', None),
        created_by_id=_user_id(generated_by),
    )


def serialize_meeting_minutes(obj: MeetingMinutes) -> dict:
    return {
        'id': str(obj.id),
        'title': obj.title,
        'report_type': 'section_minutes',
        'financial_year': obj.financial_year or '',
        'meeting_date': obj.meeting_date.isoformat() if obj.meeting_date else None,
        'summary': obj.meeting_date.isoformat() if obj.meeting_date else '',
        'notes': obj.notes or '',
        'original_filename': obj.original_filename,
        'file_size_bytes': obj.file_size_bytes,
        'file_format': obj.file_format,
        'created_at': obj.created_at.isoformat() if obj.created_at else None,
        'download_url': f'/api/planning/meeting-minutes/{obj.id}/download/',
    }


def delete_meeting_minutes(obj: MeetingMinutes) -> None:
    _delete_media_file(obj.file_path)
    obj.delete()


def delete_planning_shapefile(shapefile: PlanningShapefile) -> None:
    """Futa rekodi ya shapefile na faili iliyohifadhiwa."""
    _delete_media_file(shapefile.file_path)
    shapefile.delete()


def serialize_planning_shapefile(shapefile: PlanningShapefile) -> dict:
    return {
        'id': str(shapefile.id),
        'source': 'stored',
        'title': shapefile.title,
        'original_filename': shapefile.original_filename,
        'boundary_level': shapefile.boundary_level,
        'region_name': shapefile.region_name,
        'district_name': shapefile.district_name or '',
        'ward_name': shapefile.ward_name or '',
        'village_name': shapefile.village_name or '',
        'feature_count': shapefile.feature_count,
        'file_size_bytes': shapefile.file_size_bytes,
        'status': shapefile.status,
        'uploaded_at': shapefile.uploaded_at.isoformat() if shapefile.uploaded_at else None,
    }


def _shapefile_location_filter(
    region: str | None = None,
    district: str | None = None,
    ward: str | None = None,
    village: str | None = None,
):
    from django.db.models import Q

    from dashboard.boundary_service import _district_search_names

    q = Q()
    if region:
        q &= Q(region_name__iexact=region)
    if district:
        district_q = Q()
        for name in _district_search_names(district):
            district_q |= Q(district_name__iexact=name)
        q &= district_q
    if ward:
        q &= Q(ward_name__iexact=ward)
    if village:
        q &= Q(village_name__iexact=village)
    return q


def list_parcel_shapefile_imports(
    region: str | None = None,
    district: str | None = None,
    ward: str | None = None,
    village: str | None = None,
) -> list[dict]:
    """Orodha ya viwanja vilivyoingizwa kutoka shapefile (planning_parcels), kwa jina la faili."""
    from django.db.models import Count, Max

    items: list[dict] = []
    parcel_qs = parcels_for_location(region, district, ward, village)
    for group in (
        parcel_qs.exclude(shapefile_name__isnull=True)
        .exclude(shapefile_name='')
        .values('shapefile_name')
        .annotate(parcel_count=Count('id'), uploaded_at=Max('created_at'))
        .order_by('shapefile_name')
    ):
        uploaded_at = group['uploaded_at']
        items.append({
            'id': f"parcel:{group['shapefile_name']}",
            'source': 'parcels',
            'title': group['shapefile_name'],
            'original_filename': group['shapefile_name'],
            'shapefile_name': group['shapefile_name'],
            'boundary_level': 'parcel',
            'region_name': region or '',
            'district_name': district or '',
            'ward_name': ward or '',
            'village_name': village or '',
            'parcel_count': group['parcel_count'],
            'feature_count': group['parcel_count'],
            'uploaded_at': uploaded_at.isoformat() if uploaded_at else None,
        })
    return items


def list_uploaded_shapefiles(
    region: str | None = None,
    district: str | None = None,
    ward: str | None = None,
    village: str | None = None,
) -> list[dict]:
    """Orodha ya shapefile za mpango: viwanja + mipaka ya kijiji (bila kata/wilaya)."""
    from django.db.models import Q

    items: list[dict] = list_parcel_shapefile_imports(region, district, ward, village)
    loc = _shapefile_location_filter(region, district, ward, village)

    # PlanningShapefile: onyesha kijiji + viwanja / matumizi; ficha kata & wilaya
    for shp in (
        PlanningShapefile.objects.filter(loc)
        .exclude(boundary_level__in=('district', 'ward'))
        .order_by('-uploaded_at')[:200]
    ):
        items.append(serialize_planning_shapefile(shp))

    # Mipaka: kijiji pekee (kata/wilaya hazionyeshwi kwenye Data Portal)
    location_values = {
        'region_name': region,
        'district_name': district,
        'ward_name': ward,
        'village_name': village,
    }
    fields = ('region_name', 'district_name', 'ward_name', 'village_name')
    q = Q()
    for field in fields:
        value = location_values.get(field)
        if not value:
            continue
        if field == 'district_name':
            district_q = Q()
            from dashboard.boundary_service import _district_search_names
            for name in _district_search_names(value):
                district_q |= Q(district_name__iexact=name)
            q &= district_q
        else:
            q &= Q(**{f'{field}__iexact': value})
    qs = (
        VillagePlanningBoundary.objects.filter(q)
        .exclude(shapefile_name__isnull=True)
        .exclude(shapefile_name='')
    )
    for boundary in qs.order_by('-updated_at')[:100]:
        items.append({
            'id': str(boundary.id),
            'source': 'boundary',
            'title': boundary.shapefile_name,
            'original_filename': boundary.shapefile_name,
            'boundary_level': 'village',
            'region_name': boundary.region_name,
            'district_name': boundary.district_name or '',
            'ward_name': getattr(boundary, 'ward_name', '') or '',
            'village_name': getattr(boundary, 'village_name', '') or '',
            'feature_count': 1,
            'uploaded_at': boundary.updated_at.isoformat() if boundary.updated_at else None,
        })

    items.sort(key=lambda x: x.get('uploaded_at') or '', reverse=True)
    return items


@transaction.atomic(using='detailed_planning')
def delete_parcels_by_shapefile_name(
    shapefile_name: str,
    *,
    region: str | None = None,
    district: str | None = None,
    ward: str | None = None,
    village: str | None = None,
) -> int:
    """Futa viwanja vilivyoingizwa kutoka shapefile fulani."""
    qs = parcels_for_location(region, district, ward, village).filter(
        shapefile_name__iexact=shapefile_name,
    )
    affected = list(
        qs.values_list('region_name', 'district_name', 'ward_name', 'village_name').distinct()
    )
    deleted = qs.count()
    qs.delete()

    for reg, dist, w, vill in affected:
        plan = VillageDetailedPlan.objects.filter(
            region_name__iexact=reg,
            district_name__iexact=dist,
            ward_name__iexact=w,
            village_name__iexact=vill,
        ).first()
        if plan:
            plan.sync_parcel_counts()

    return deleted


def clear_boundary_shapefile(boundary_id: str, level: str) -> bool:
    """Ondoa mipaka iliyopakiwa kutoka rekodi ya boundary."""
    model_map = {
        'district': DistrictPlanningBoundary,
        'ward': WardPlanningBoundary,
        'village': VillagePlanningBoundary,
    }
    model = model_map.get(level)
    if not model:
        raise ValueError(f'Kiwango kisichojulikana: {level}')

    boundary = model.objects.filter(pk=boundary_id).first()
    if not boundary:
        return False

    boundary.geom = None
    boundary.shapefile_name = None
    boundary.area_ha = None
    boundary.save(update_fields=['geom', 'shapefile_name', 'area_ha', 'updated_at'])
    return True


GENDER_LABELS = {'M': 'Mwanaume', 'F': 'Mwanamke', 'U': 'Haijulikani'}
AGE_LABELS = {'adult': 'Mtu mzima (18+)', 'child': 'Mtoto (chini ya 18)'}

CCRO_SHAPEFILE_FIELDS = (
    'pid', 'claim_no', 'claim_date', 'paras', 'hamlet', 'parties',
    'neighbor_north', 'neighbor_south', 'neighbor_west', 'neighbor_east',
    'spouse', 'children', 'others', 'kitongoji', 'topography', 'season',
    'right_of_way', 'witness_1', 'witness_2', 'remarks', 'shp_village',
    'land_title_name', 'land_use', 'ownership_type',
    'shapefile_name', 'source_layer', 'source_path',
)

CCRO_SEARCH_FIELDS = (
    'owner_name', 'parcel_number', 'parties', 'claim_no', 'pid',
    'land_title_name', 'hamlet', 'kitongoji', 'land_use', 'remarks',
    'shp_village', 'shapefile_name',
)


def serialize_ccro_shapefile_fields(parcel: PlanningParcel) -> dict:
    return {field: getattr(parcel, field) or '' for field in CCRO_SHAPEFILE_FIELDS}


def parcel_source_summary(parcels) -> dict:
    """Muhtasari wa vyanzo vya shapefile kwa eneo lililochaguliwa."""
    shapefiles = sorted({
        n for n in parcels.exclude(shapefile_name__isnull=True)
        .exclude(shapefile_name='')
        .values_list('shapefile_name', flat=True)
        .distinct()
    })
    layers = sorted({
        n for n in parcels.exclude(source_layer__isnull=True)
        .exclude(source_layer='')
        .values_list('source_layer', flat=True)
        .distinct()
    })
    from django.db.models import Q

    with_source = parcels.filter(
        Q(shapefile_name__isnull=False) & ~Q(shapefile_name='')
        | Q(source_layer__isnull=False) & ~Q(source_layer='')
    ).count()
    return {
        'shapefile_names': shapefiles,
        'source_layers': layers,
        'parcels_with_source': with_source,
    }


def serialize_ccro_landowner(parcel: PlanningParcel) -> dict:
    return {
        'id': str(parcel.id),
        'parcel_number': parcel.parcel_number,
        'owner_name': parcel.owner_name or '—',
        'owner_gender': parcel.owner_gender or '',
        'owner_gender_label': GENDER_LABELS.get(parcel.owner_gender or '', '—'),
        'owner_age_category': parcel.owner_age_category or '',
        'owner_age_label': AGE_LABELS.get(parcel.owner_age_category or '', '—'),
        'is_identified': parcel.is_identified,
        'identified_label': 'Imetambuliwa' if parcel.is_identified else 'Haijatambuliwa',
        'region_name': parcel.region_name,
        'district_name': parcel.district_name,
        'ward_name': parcel.ward_name,
        'village_name': parcel.village_name,
        'area_ha': parcel.area_ha,
        'notes': parcel.notes or '',
        **serialize_ccro_shapefile_fields(parcel),
    }
