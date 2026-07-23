#!/usr/bin/env python
"""
Import viwanja (parcel) shapefiles into detailed_planning.planning_parcels (PostGIS SRID 32736).

Auto-discovers parcel/CCRO shapefiles under common folders, maps owner/location attributes,
generates parcel numbers (DP/MKO/WIL/KAT/KIJ/0001), and links each parcel to village_plans.

Usage (from tanzania_gis project root):
    .\\venv\\Scripts\\python.exe scripts\\import_parcel_shapefiles.py --inspect
    .\\venv\\Scripts\\python.exe scripts\\import_parcel_shapefiles.py
    .\\venv\\Scripts\\python.exe scripts\\import_parcel_shapefiles.py --shapefile-dir "D:\\path\\to\\viwanja"
    .\\venv\\Scripts\\python.exe scripts\\import_parcel_shapefiles.py --file "D:\\path\\to\\kijiji_viwanja.shp"
    .\\venv\\Scripts\\python.exe scripts\\import_parcel_shapefiles.py --clear
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tanzania_gis.settings')
os.environ['PATH'] = r'C:\Program Files\GDAL;' + os.environ.get('PATH', '')
os.environ['PROJ_LIB'] = r'C:\Program Files\GDAL\projlib'

import django

django.setup()

from django.contrib.gis.geos import GEOSGeometry, MultiPolygon  # noqa: E402
from django.db import transaction  # noqa: E402
from osgeo import ogr  # noqa: E402

from detailed_planning.models import PlanningParcel, VillageDetailedPlan  # noqa: E402
from detailed_planning.services import (  # noqa: E402
    _district_name_q,
    apply_identification_to_parcel,
    compute_is_identified,
    generate_plot_number,
    get_or_create_village_plan,
    next_plot_sequence,
    normalize_import_district,
)

TARGET_SRID = 32736

DEFAULT_SEARCH_DIRS = [
    Path(r'D:\MFUMO LUMC\Viwanja Shapefile'),
    Path(r'D:\MFUMO LUMC\Viwanja'),
    Path(r'D:\MFUMO LUMC\Parcels'),
    Path(r'D:\MFUMO LUMC\CCRO'),
    Path(r'D:\MFUMO LUMC\Tanzania Shapefile\viwanja'),
    Path(r'D:\MFUMO LUMC\Tanzania Shapefile\parcels'),
    Path(r'D:\MFUMO LUMC\LUMC\tanzania_gis\data\viwanja'),
    Path(r'D:\MFUMO LUMC\LUMC\tanzania_gis\media\shapefiles'),
]

PARCEL_NAME_PATTERNS = re.compile(
    r'(viwanja|viwanj|parcel|parcels|kiwanja|kiwanj|ccro|plot|plots|cadastr)',
    re.IGNORECASE,
)

# Regional kata boundary shapefiles (31 mkoa) — si viwanja
EXCLUDED_STEMS = {
    'Arusha', 'Dar_es_Salaam', 'Dodoma', 'Geita', 'Iringa', 'Kagera',
    'Kaskazini_Pemba', 'Kaskazini_Unguja', 'Katavi', 'Kigoma', 'Kilimanjaro',
    'Kusini_Pemba', 'Kusini_Unguja', 'Lindi', 'Manyara', 'Mara', 'Mbeya',
    'Mjini_Magharibi', 'Morogoro', 'Mtwara', 'Mwanza', 'Njombe', 'Pwani',
    'Rukwa', 'Ruvuma', 'Shinyanga', 'Simiyu', 'Singida', 'Songwe', 'Tabora', 'Tanga',
}

REGION_FIELD_CANDIDATES = (
    'reg_name', 'REG_NAME', 'Region', 'REGION', 'Mkoa', 'MKOA', 'region_name',
)
DISTRICT_FIELD_CANDIDATES = (
    'dist_name', 'DIST_NAME', 'District', 'DISTRICT', 'Wilaya', 'WILAYA', 'district_name',
)
WARD_FIELD_CANDIDATES = (
    'ward_name', 'WARD_NAME', 'Ward', 'WARD', 'Kata', 'KATA', 'ward_name',
)
VILLAGE_FIELD_CANDIDATES = (
    'village_name', 'VILLAGE_NAME', 'village_na', 'VILLAGE_NA',  # SHP 10-char limit
    'Village', 'VILLAGE', 'Kijiji', 'KIJIJI', 'vill_name', 'VILL_NAME', 'village', 'kijiji',
)
OWNER_FIELD_CANDIDATES = (
    'owner_name', 'OWNER_NAME', 'owner_na', 'OWNER_NA',  # SHP 10-char limit
    'owner', 'OWNER', 'Owner_Name', 'mmiliki', 'MMILIKI',
    'landowner', 'LANDOWNER', 'name', 'NAME', 'jina', 'JINA', 'holder', 'HOLDER',
    'PARTIES', 'parties',  # CCRO / Madaba VLUP
)
HAMLET_FIELD_CANDIDATES = ('HAMLET', 'hamlet', 'Kitongoji', 'KITONGOJI', 'kitongoji')
CLAIM_FIELD_CANDIDATES = ('CLAIM_NO', 'claim_no', 'CLAIM', 'claim')
LANDUSE_FIELD_CANDIDATES = ('Matumizi_y', 'MATUMIZI_Y', 'Matumizi_1', 'land_use', 'LAND_USE')
OWNERSHIP_FIELD_CANDIDATES = ('Umiliki', 'UMILIKI', 'ownership', 'OWNERSHIP')
SPOUSE_FIELD_CANDIDATES = ('Wenza', 'WENZA', 'spouse', 'SPOUSE')
CHILDREN_FIELD_CANDIDATES = ('Watoto', 'WATOTO', 'children', 'CHILDREN')
REMARKS_FIELD_CANDIDATES = ('Toa_maoni_', 'TOA_MAONI_', 'remarks', 'REMARKS')
GENDER_FIELD_CANDIDATES = (
    'gender', 'GENDER', 'sex', 'SEX', 'owner_gender', 'OWNER_GENDER', 'jinsia', 'JINSIA',
)
AGE_CAT_FIELD_CANDIDATES = (
    'age_category', 'AGE_CATEGORY', 'age_cat', 'AGE_CAT', 'age_group', 'AGE_GROUP',
)
AGE_FIELD_CANDIDATES = ('age', 'AGE', 'umri', 'UMRI')
IDENTIFIED_FIELD_CANDIDATES = (
    'is_identified', 'IS_IDENTIFIED', 'identified', 'IDENTIFIED', 'tambuliwa', 'TAMBULIWA',
    'status', 'STATUS',
)
PARCEL_NUM_FIELD_CANDIDATES = (
    'parcel_number', 'PARCEL_NUMBER', 'parcel_no', 'PARCEL_NO', 'plot_no', 'PLOT_NO',
    'plot_number', 'PLOT_NUMBER', 'kiwanja_no', 'KIWANJA_NO', 'namba', 'NAMBA',
)
NOTES_FIELD_CANDIDATES = ('notes', 'NOTES', 'remarks', 'REMARKS', 'maelezo', 'MAELEZO')

# Mpangokinaa / CCRO shapefile — mapping SHP field -> model field
MPANGOKINAA_FIELD_MAP: dict[str, str] = {
    'PID': 'pid',
    'CLAIM_NO': 'claim_no',
    'DATE_': 'claim_date',
    'PARAS': 'paras',
    'VILLAGE': 'shp_village',
    'HAMLET': 'hamlet',
    'PARTIES': 'parties',
    'Kaskazini': 'neighbor_north',
    'Kusini': 'neighbor_south',
    'Magharibi': 'neighbor_west',
    'Mashariki': 'neighbor_east',
    'Wenza': 'spouse',
    'Watoto': 'children',
    'Wengineo': 'others',
    'Kitongoji': 'kitongoji',
    'Topolijia': 'topography',
    'Majira_ya_': 'season',
    'Haki_ya_Nj': 'right_of_way',
    'Shahidi_wa': 'witness_1',
    'Shahidi__1': 'witness_2',
    'Toa_maoni_': 'remarks',
    'Kijiji': 'shp_village',
    'Jina_la_Ta': 'land_title_name',
    'Matumizi_y': 'land_use',
    'Umiliki': 'ownership_type',
    'layer': 'source_layer',
    'path': 'source_path',
}

PARCEL_INDICATOR_FIELDS = set(
    c.lower()
    for group in (
        OWNER_FIELD_CANDIDATES,
        VILLAGE_FIELD_CANDIDATES,
        PARCEL_NUM_FIELD_CANDIDATES,
        GENDER_FIELD_CANDIDATES,
    )
    for c in group
)


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


def _resolve_shp_field(layer_defn, shp_name: str) -> str | None:
    names = {layer_defn.GetFieldDefn(i).GetName() for i in range(layer_defn.GetFieldCount())}
    if shp_name in names:
        return shp_name
    lower_map = {n.lower(): n for n in names}
    return lower_map.get(shp_name.lower())


def _extract_mpangokinaa_attrs(feat, layer_defn) -> dict[str, str | None]:
    """Chukua thamani zote za Mpangokinaa kutoka shapefile."""
    attrs: dict[str, str | None] = {}
    for shp_field, model_field in MPANGOKINAA_FIELD_MAP.items():
        resolved = _resolve_shp_field(layer_defn, shp_field)
        if not resolved:
            continue
        value = _clean(feat.GetField(resolved))
        if value is None:
            continue
        if model_field == 'shp_village' and attrs.get('shp_village'):
            continue
        attrs[model_field] = value
    return attrs


def _clean(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip().rstrip(',')
    if text in ('-', '_', '—', '–'):
        return None
    return text or None


def _infer_location_from_path(path: Path) -> dict[str, str | None]:
    """Infer mkoa/wilaya/kata/kijiji from folder names (e.g. Madaba VLUP / Mwande)."""
    parts = [p.lower() for p in path.parts]
    joined = ' '.join(parts)
    loc: dict[str, str | None] = {
        'region': None,
        'district': None,
        'ward': None,
        'village': None,
    }
    if 'madaba' in joined:
        loc['region'] = 'Ruvuma'
        loc['district'] = 'Madaba'
        loc['ward'] = 'Matetereka'
    if 'mwande' in joined:
        loc['village'] = 'Mwande'
    elif 'maweso' in joined:
        loc['village'] = 'Maweso'
    elif 'igawisenga' in joined or 'igawis' in joined:
        loc['village'] = 'Igawisenga'
    return loc


def _build_ccro_notes(
    *,
    claim_no: str | None,
    hamlet: str | None,
    land_use: str | None,
    ownership: str | None,
    spouse: str | None,
    children: str | None,
    remarks: str | None,
    shp_parcel_no: str | None,
    base_notes: str | None,
) -> str | None:
    parts: list[str] = []
    if base_notes:
        parts.append(base_notes)
    if shp_parcel_no:
        parts.append(f'SHP namba: {shp_parcel_no}')
    if claim_no:
        parts.append(f'Claim: {claim_no}')
    if hamlet:
        parts.append(f'Kitongoji: {hamlet}')
    if land_use:
        parts.append(f'Matumizi: {land_use}')
    if ownership:
        parts.append(f'Umiliki: {ownership}')
    if spouse:
        parts.append(f'Mwenza: {spouse}')
    if children:
        parts.append(f'Watoto: {children}')
    if remarks:
        parts.append(f'Maoni: {remarks}')
    return ' | '.join(parts) if parts else None


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


def _layer_srid(layer) -> int:
    srs = layer.GetSpatialRef()
    if srs is None:
        return 4326
    try:
        from osgeo import osr
        srs.AutoIdentifyEPSG()
        auth = srs.GetAuthorityCode(None)
        if auth:
            return int(auth)
    except Exception:
        pass
    return 4326


def _feature_geom(feat, source_srid: int) -> MultiPolygon | None:
    geom_ref = feat.GetGeometryRef()
    if geom_ref is None or geom_ref.IsEmpty():
        return None
    wkt = geom_ref.ExportToWkt()
    geom = GEOSGeometry(wkt, srid=source_srid or 4326)
    if geom.srid != TARGET_SRID:
        geom.transform(TARGET_SRID)
    if geom.geom_type == 'Polygon':
        return MultiPolygon(geom)
    if geom.geom_type == 'MultiPolygon':
        return geom
    return None


def _area_ha(geom: MultiPolygon) -> float:
    return round(geom.area / 10_000.0, 4)


def _is_parcel_layer(layer_defn, path: Path) -> bool:
    stem = path.stem
    if stem in EXCLUDED_STEMS and path.suffix.lower() == '.shp':
        return False
    if PARCEL_NAME_PATTERNS.search(path.name):
        return True
    field_names = {layer_defn.GetFieldDefn(i).GetName().lower() for i in range(layer_defn.GetFieldCount())}
    has_village = any(c.lower() in field_names for c in VILLAGE_FIELD_CANDIDATES)
    has_owner = any(c.lower() in field_names for c in OWNER_FIELD_CANDIDATES)
    has_parcel = any(c.lower() in field_names for c in PARCEL_NUM_FIELD_CANDIDATES)
    if has_village and (has_owner or has_parcel):
        return True
    parcel_hits = len(field_names & PARCEL_INDICATOR_FIELDS)
    return parcel_hits >= 3


def discover_shapefiles(search_dirs: list[Path], explicit_files: list[Path] | None = None) -> list[Path]:
    found: list[Path] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        key = str(path.resolve()).lower()
        if key not in seen and path.is_file():
            seen.add(key)
            found.append(path)

    if explicit_files:
        for p in explicit_files:
            add(p)
        return sorted(found)

    extensions = {'.shp', '.zip', '.gpkg'}
    for base in search_dirs:
        if not base.exists():
            continue
        if base.is_file() and base.suffix.lower() in extensions:
            add(base)
            continue
        for path in base.rglob('*'):
            if path.suffix.lower() not in extensions:
                continue
            if path.suffix.lower() == '.shp' and path.stem in EXCLUDED_STEMS:
                continue
            if PARCEL_NAME_PATTERNS.search(path.name):
                add(path)
                continue
            if path.suffix.lower() == '.shp':
                try:
                    ds = ogr.Open(str(path))
                    if ds is None:
                        continue
                    layer = ds.GetLayer()
                    if _is_parcel_layer(layer.GetLayerDefn(), path):
                        add(path)
                    ds = None
                except Exception:
                    continue
    return sorted(found)


def _open_datasource(path: Path):
    if path.suffix.lower() == '.zip':
        with zipfile.ZipFile(path, 'r') as zf:
            shp_names = [n for n in zf.namelist() if n.lower().endswith('.shp')]
            if not shp_names:
                raise RuntimeError(f'Hakuna .shp ndani ya {path.name}')
            tmpdir = tempfile.mkdtemp(prefix='viwanja_import_')
            zf.extractall(tmpdir)
            shp_path = Path(tmpdir) / Path(shp_names[0]).name
            ds = ogr.Open(str(shp_path))
            if ds is None:
                raise RuntimeError(f'GDAL haikuweza kufungua {path}')
            return ds, shp_path
    ds = ogr.Open(str(path))
    if ds is None:
        raise RuntimeError(f'GDAL haikuweza kufungua {path}')
    return ds, path


def inspect_shapefile(path: Path) -> dict:
    ds, opened = _open_datasource(path)
    layer = ds.GetLayer()
    defn = layer.GetLayerDefn()
    fields = [defn.GetFieldDefn(i).GetName() for i in range(defn.GetFieldCount())]
    sample = None
    feat = layer.GetNextFeature()
    if feat:
        sample = {f: feat.GetField(f) for f in fields[:12]}
    ds = None
    return {
        'path': str(path),
        'opened': str(opened),
        'feature_count': layer.GetFeatureCount(),
        'geom_type': ogr.GeometryTypeToName(defn.GetGeomType()),
        'srid': _layer_srid(layer),
        'fields': fields,
        'is_parcel_candidate': _is_parcel_layer(defn, path),
        'sample': sample,
    }


def _find_existing_parcel(region: str, district: str, ward: str, village: str, geom):
    """Linganisha kwa jiometri; sasisha viwanja vilivyo na village_name='Imported'."""
    base = PlanningParcel.objects.filter(
        region_name__iexact=region,
        ward_name__iexact=ward,
        geom=geom,
    ).filter(_district_name_q(district))
    existing = base.filter(village_name__iexact=village).first()
    if existing:
        return existing
    return base.filter(village_name__iexact='Imported').first()


def import_shapefile(
    path: Path,
    *,
    dry_run: bool = False,
    default_region: str | None = None,
    default_district: str | None = None,
    default_ward: str | None = None,
    default_village: str | None = None,
) -> dict:
    ds, _ = _open_datasource(path)
    layer = ds.GetLayer()
    layer_defn = layer.GetLayerDefn()
    source_srid = _layer_srid(layer)

    reg_f = _pick_field(layer_defn, REGION_FIELD_CANDIDATES)
    dist_f = _pick_field(layer_defn, DISTRICT_FIELD_CANDIDATES)
    ward_f = _pick_field(layer_defn, WARD_FIELD_CANDIDATES)
    vill_f = _pick_field(layer_defn, VILLAGE_FIELD_CANDIDATES)
    owner_f = _pick_field(layer_defn, OWNER_FIELD_CANDIDATES)
    gender_f = _pick_field(layer_defn, GENDER_FIELD_CANDIDATES)
    age_cat_f = _pick_field(layer_defn, AGE_CAT_FIELD_CANDIDATES)
    age_f = _pick_field(layer_defn, AGE_FIELD_CANDIDATES)
    ident_f = _pick_field(layer_defn, IDENTIFIED_FIELD_CANDIDATES)
    parcel_f = _pick_field(layer_defn, PARCEL_NUM_FIELD_CANDIDATES)
    notes_f = _pick_field(layer_defn, NOTES_FIELD_CANDIDATES)
    hamlet_f = _pick_field(layer_defn, HAMLET_FIELD_CANDIDATES)
    claim_f = _pick_field(layer_defn, CLAIM_FIELD_CANDIDATES)
    landuse_f = _pick_field(layer_defn, LANDUSE_FIELD_CANDIDATES)
    ownership_f = _pick_field(layer_defn, OWNERSHIP_FIELD_CANDIDATES)
    spouse_f = _pick_field(layer_defn, SPOUSE_FIELD_CANDIDATES)
    children_f = _pick_field(layer_defn, CHILDREN_FIELD_CANDIDATES)
    remarks_f = _pick_field(layer_defn, REMARKS_FIELD_CANDIDATES)

    inferred = _infer_location_from_path(path)
    fallback_region = default_region or inferred.get('region')
    fallback_district = default_district or inferred.get('district')
    fallback_ward = default_ward or inferred.get('ward')
    fallback_village = default_village or inferred.get('village')

    created = updated = skipped = errors = 0
    error_details: list[str] = []
    villages_touched: set[tuple[str, str, str, str]] = set()

    seq_cache: dict[tuple[str, str, str, str], int] = {}

    for feat in layer:
        try:
            region = _clean(feat.GetField(reg_f) if reg_f else None) or fallback_region
            district = _clean(feat.GetField(dist_f) if dist_f else None) or fallback_district
            district = normalize_import_district(district, fallback_district)
            ward = _clean(feat.GetField(ward_f) if ward_f else None) or fallback_ward
            village = _clean(feat.GetField(vill_f) if vill_f else None) or fallback_village

            if not all([region, district, ward, village]):
                skipped += 1
                error_details.append(
                    f'{path.name}: feature {feat.GetFID()} — hakuna mkoa/wilaya/kata/kijiji kamili'
                )
                continue

            geom = _feature_geom(feat, source_srid)
            if geom is None:
                skipped += 1
                continue

            owner_name = _clean(feat.GetField(owner_f) if owner_f else None)
            mpangokinaa = _extract_mpangokinaa_attrs(feat, layer_defn)
            if not owner_name and mpangokinaa.get('parties'):
                owner_name = mpangokinaa['parties']
            if not village and mpangokinaa.get('shp_village'):
                village = mpangokinaa['shp_village']

            owner_gender = _normalize_gender(_clean(feat.GetField(gender_f) if gender_f else None))
            age_raw = feat.GetField(age_f) if age_f else None
            owner_age_category = _normalize_age_category(
                _clean(feat.GetField(age_cat_f) if age_cat_f else None),
                age_raw,
            )
            ident_raw = feat.GetField(ident_f) if ident_f else None
            is_identified = compute_is_identified(raw=ident_raw, owner_name=owner_name, **mpangokinaa)
            base_notes = _clean(feat.GetField(notes_f) if notes_f else None)
            shp_parcel_no = _clean(feat.GetField(parcel_f) if parcel_f else None)
            notes = _build_ccro_notes(
                claim_no=mpangokinaa.get('claim_no') or _clean(feat.GetField(claim_f) if claim_f else None),
                hamlet=mpangokinaa.get('hamlet') or _clean(feat.GetField(hamlet_f) if hamlet_f else None),
                land_use=mpangokinaa.get('land_use') or _clean(feat.GetField(landuse_f) if landuse_f else None),
                ownership=mpangokinaa.get('ownership_type') or _clean(feat.GetField(ownership_f) if ownership_f else None),
                spouse=mpangokinaa.get('spouse') or _clean(feat.GetField(spouse_f) if spouse_f else None),
                children=mpangokinaa.get('children') or _clean(feat.GetField(children_f) if children_f else None),
                remarks=mpangokinaa.get('remarks') or _clean(feat.GetField(remarks_f) if remarks_f else None),
                shp_parcel_no=mpangokinaa.get('pid') or shp_parcel_no,
                base_notes=base_notes,
            )
            area_ha = _area_ha(geom)

            parcel_kwargs = {k: v for k, v in mpangokinaa.items() if v is not None}
            shp_name = path.name
            parcel_kwargs.setdefault('shapefile_name', shp_name)
            if not parcel_kwargs.get('source_layer'):
                parcel_kwargs['source_layer'] = path.stem
            if not parcel_kwargs.get('source_path'):
                parcel_kwargs['source_path'] = str(path.resolve())

            loc_key = (region, district, ward, village)
            villages_touched.add(loc_key)

            if dry_run:
                created += 1
                continue

            if loc_key not in seq_cache:
                seq_cache[loc_key] = next_plot_sequence(region, district, ward, village)

            seq = seq_cache[loc_key]
            seq_cache[loc_key] = seq + 1
            parcel_number = generate_plot_number(region, district, ward, village, seq)

            plan = get_or_create_village_plan(region, district, ward, village)

            existing = _find_existing_parcel(region, district, ward, village, geom)

            if existing:
                if existing.village_name != village:
                    existing.village_name = village
                existing.owner_name = owner_name or existing.owner_name
                existing.owner_gender = owner_gender or existing.owner_gender
                existing.owner_age_category = owner_age_category or existing.owner_age_category
                existing.area_ha = area_ha
                if notes:
                    existing.notes = notes
                for field, value in parcel_kwargs.items():
                    setattr(existing, field, value)
                existing.shapefile_name = shp_name
                apply_identification_to_parcel(existing, save=False)
                existing.save()
                updated += 1
            else:
                PlanningParcel.objects.create(
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
                    owner_is_landowner=True,
                    notes=notes,
                    village_plan=plan,
                    **parcel_kwargs,
                )
                created += 1
        except Exception as exc:
            errors += 1
            error_details.append(f'{path.name} FID {feat.GetFID()}: {exc}')

    ds = None

    if not dry_run:
        for loc in villages_touched:
            plan = VillageDetailedPlan.objects.filter(
                region_name__iexact=loc[0],
                district_name__iexact=loc[1],
                ward_name__iexact=loc[2],
                village_name__iexact=loc[3],
            ).first()
            if plan:
                plan.sync_parcel_counts(recalculate_identification=True)

    return {
        'file': str(path),
        'created': created,
        'updated': updated,
        'skipped': skipped,
        'errors': errors,
        'error_details': error_details,
        'villages': len(villages_touched),
    }


@transaction.atomic
def import_all(
    paths: list[Path],
    *,
    dry_run: bool = False,
    clear: bool = False,
    default_region: str | None = None,
    default_district: str | None = None,
    default_ward: str | None = None,
    default_village: str | None = None,
) -> dict:
    if clear and not dry_run:
        deleted, _ = PlanningParcel.objects.all().delete()
        print(f'Imefutwa viwanja {deleted} vilivyokuwepo.')

    totals = {
        'files': len(paths),
        'created': 0,
        'updated': 0,
        'skipped': 0,
        'errors': 0,
        'error_details': [],
        'per_file': [],
    }

    for path in paths:
        print(f'  -> {path}')
        result = import_shapefile(
            path,
            dry_run=dry_run,
            default_region=default_region,
            default_district=default_district,
            default_ward=default_ward,
            default_village=default_village,
        )
        totals['per_file'].append(result)
        totals['created'] += result['created']
        totals['updated'] += result['updated']
        totals['skipped'] += result['skipped']
        totals['errors'] += result['errors']
        totals['error_details'].extend(result['error_details'])

    totals['db_total'] = PlanningParcel.objects.count() if not dry_run else 0
    return totals


def main() -> int:
    parser = argparse.ArgumentParser(description='Import viwanja shapefiles into DETAILED PLANNING DB')
    parser.add_argument(
        '--shapefile-dir',
        type=Path,
        action='append',
        dest='shapefile_dirs',
        help='Folder to search for parcel shapefiles (repeatable)',
    )
    parser.add_argument(
        '--file',
        type=Path,
        action='append',
        dest='files',
        help='Single shapefile (.shp/.zip/.gpkg) to import',
    )
    parser.add_argument('--inspect', action='store_true', help='List discovered files and attributes only')
    parser.add_argument('--dry-run', action='store_true', help='Parse files without writing to DB')
    parser.add_argument('--clear', action='store_true', help='Delete existing planning_parcels before import')
    parser.add_argument('--region', help='Default mkoa when shapefile lacks region field')
    parser.add_argument('--district', help='Default wilaya when shapefile lacks district field')
    parser.add_argument('--ward', help='Default kata when shapefile lacks ward field')
    parser.add_argument('--village', help='Default kijiji when shapefile lacks village field')
    args = parser.parse_args()

    search_dirs = args.shapefile_dirs or DEFAULT_SEARCH_DIRS
    explicit = args.files

    print('=== UTAFUTAJI WA SHAPEFILE ZA VIWANJA ===')
    print('Folda zinazochunguzwa:')
    for d in search_dirs:
        status = 'ipo' if Path(d).exists() else 'haipo'
        print(f'  [{status}] {d}')

    paths = discover_shapefiles(search_dirs, explicit_files=explicit)
    print(f'\nShapefiles zilizopatikana: {len(paths)}')
    for p in paths:
        print(f'  - {p}')

    if not paths:
        print('\nHAKUNA shapefile za viwanja zilizopatikana.')
        print('Weka faili .shp / .zip / .gpkg kwenye moja ya folda hapo juu, au tumia:')
        print('  --file "D:\\path\\to\\viwanja.shp"')
        print('  --shapefile-dir "D:\\path\\to\\folder"')
        return 2

    if args.inspect:
        print('\n=== UCHAMBUZI WA SIFA (ATTRIBUTES) ===')
        for p in paths:
            info = inspect_shapefile(p)
            print(f"\n{info['path']}")
            print(f"  Features: {info['feature_count']}, SRID: {info['srid']}, Geom: {info['geom_type']}")
            print(f"  Parcel candidate: {info['is_parcel_candidate']}")
            print(f"  Fields: {', '.join(info['fields'])}")
            if info['sample']:
                print(f"  Sample: {info['sample']}")
        return 0

    print(f'\nLengo: detailed_planning.planning_parcels (SRID {TARGET_SRID})')
    if args.dry_run:
        print('Hali: dry-run (hakuna kuandika DB)')
    print('Inaendesha import...\n')

    result = import_all(
        paths,
        dry_run=args.dry_run,
        clear=args.clear,
        default_region=args.region,
        default_district=args.district,
        default_ward=args.ward,
        default_village=args.village,
    )

    print('\n=== MUHTASARI ===')
    print(f"Faili zilizosomwa: {result['files']}")
    print(f"Imeundwa: {result['created']}")
    print(f"Imesasishwa: {result['updated']}")
    print(f"Imepuuzwa: {result['skipped']}")
    print(f"Makosa: {result['errors']}")
    if not args.dry_run:
        print(f"Jumla viwanja kwenye DB: {result['db_total']}")

    if result['error_details']:
        print('\nMaelezo ya makosa (kwanza 20):')
        for line in result['error_details'][:20]:
            print(f'  - {line}')

    return 1 if result['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
