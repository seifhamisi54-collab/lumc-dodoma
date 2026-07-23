"""
Pakia shapefile / GeoJSON — GDAL (kutumika na GIS Portal na GIS Tools).
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import uuid
import zipfile
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile

logger = logging.getLogger(__name__)

DISPLAY_SRID = 4326
FALLBACK_SOURCE_SRID = 32736  # UTM 36S — Tanzania (CRS ya kawaida kwa viwanja)
PARTIAL_SUCCESS_MSG = (
    'Imepakiwa sehemu: features {imported} kati ya {total}. '
    'Features {skipped} hazikusomwa (jiometri batili au sifa zisizo sahihi).'
)

REQUIRED_SHAPEFILE_EXTS = {'.shp', '.shx', '.dbf'}
OPTIONAL_SHAPEFILE_EXTS = {'.prj', '.cpg', '.sbn', '.sbx'}
INCOMPLETE_SHAPEFILE_MSG = (
    'Shapefile haijakamilika. Pakia faili zote pamoja (.shp, .shx, .dbf) '
    'ndani ya .zip moja, au chagua faili zote (.shp, .shx, .dbf) mara moja. '
    'Faili zinazokosekana: {missing}'
)


def spatial_files_from_request(request, field_names=('shapefile', 'file')) -> list:
    """Chukua faili zote za upload kutoka request (zip moja au .shp+.shx+.dbf)."""
    seen = set()
    files = []
    for field in field_names:
        for uploaded in request.FILES.getlist(field):
            key = (uploaded.name, uploaded.size)
            if key in seen:
                continue
            seen.add(key)
            files.append(uploaded)
    return files


def parse_spatial_upload_file(uploaded, extra_files=None) -> dict:
    """Badilisha faili iliyopakiwa (.zip/.shp/.geojson) → FeatureCollection."""
    files = [uploaded]
    if extra_files:
        files.extend(extra_files)
    return parse_spatial_upload_files(files)


def parse_spatial_upload_files(files) -> dict:
    """Badilisha faili moja au zaidi (.zip, .shp+.shx+.dbf, .geojson) → FeatureCollection."""
    if not files:
        raise ValueError('Hakuna faili iliyopakiwa')

    primary = files[0]
    name = primary.name or 'upload'
    lower = name.lower()

    if lower.endswith('.geojson') or lower.endswith('.json'):
        if len(files) > 1:
            raise ValueError('GeoJSON ni faili moja tu')
        data = json.loads(primary.read().decode('utf-8'))
        if data.get('type') == 'Feature':
            data = {'type': 'FeatureCollection', 'features': [data]}
        if data.get('type') != 'FeatureCollection':
            raise ValueError('GeoJSON si sahihi')
        return data

    from osgeo import gdal

    gdal.UseExceptions()
    os.environ['SHAPE_RESTORE_SHX'] = 'YES'
    gdal.SetConfigOption('SHAPE_RESTORE_SHX', 'YES')

    work_root = Path(settings.BASE_DIR) / 'media' / 'gis_upload_tmp'
    work_root.mkdir(parents=True, exist_ok=True)
    work_dir = work_root / uuid.uuid4().hex
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        shp_path = _prepare_shapefile_on_disk(files, work_dir)
        return _convert_to_geojson(_to_gdal_path(str(shp_path)), gdal)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def _prepare_shapefile_on_disk(files, work_dir: Path) -> Path:
    """Andaa .shp kwenye folda ya muda — kutoka zip au faili za pamoja."""
    primary = files[0]
    name = primary.name or 'upload'
    lower = name.lower()

    if lower.endswith('.zip'):
        if len(files) > 1:
            raise ValueError('Zip ni faili moja tu. Weka .shp, .shx, .dbf ndani ya zip.')
        zip_path = work_dir / _safe_basename(name, default='upload.zip')
        _save_uploaded_file(primary, zip_path)
        return _extract_shapefile_from_zip(str(zip_path), str(work_dir / 'bundle'))

    if lower.endswith('.shp') or any(
        (f.name or '').lower().endswith('.shp') for f in files
    ):
        return _save_loose_shapefile_bundle(files, work_dir)

    raise ValueError('Tumia .zip (shapefile kamili), .shp+.shx+.dbf pamoja, au .geojson')


def _save_loose_shapefile_bundle(files, work_dir: Path) -> Path:
    """Hifadhi .shp, .shx, .dbf (na .prj) kwenye folda moja na jina la msingi linalolingana."""
    bundle_dir = work_dir / 'bundle'
    bundle_dir.mkdir(parents=True, exist_ok=True)

    shp_upload = None
    by_ext: dict[str, UploadedFile] = {}
    for uploaded in files:
        fname = uploaded.name or ''
        ext = os.path.splitext(fname)[1].lower()
        if ext == '.shp':
            shp_upload = uploaded
        if ext:
            by_ext[ext] = uploaded

    if not shp_upload:
        raise ValueError(INCOMPLETE_SHAPEFILE_MSG.format(missing='.shp'))

    stem = _safe_stem(shp_upload.name)
    missing = sorted(REQUIRED_SHAPEFILE_EXTS - set(by_ext))
    if missing:
        raise ValueError(INCOMPLETE_SHAPEFILE_MSG.format(missing=', '.join(missing)))

    for ext, uploaded in by_ext.items():
        if ext not in REQUIRED_SHAPEFILE_EXTS | OPTIONAL_SHAPEFILE_EXTS and ext != '.shp.xml':
            continue
        if ext == '.shp.xml':
            out_name = f'{stem}.shp.xml'
        else:
            out_name = f'{stem}{ext}'
        _save_uploaded_file(uploaded, bundle_dir / out_name)

    shp_path = bundle_dir / f'{stem}.shp'
    if not shp_path.is_file():
        raise ValueError(INCOMPLETE_SHAPEFILE_MSG.format(missing='.shp'))
    return shp_path


def _save_uploaded_file(uploaded, dest_path: Path) -> None:
    with open(dest_path, 'wb') as dest:
        for chunk in uploaded.chunks():
            dest.write(chunk)


def _safe_stem(filename: str) -> str:
    stem = os.path.splitext(os.path.basename(filename or 'upload'))[0]
    return re.sub(r'[^\w.\-]', '_', stem) or 'upload'


def _safe_basename(filename: str, default: str = 'upload') -> str:
    base = os.path.basename(filename or default)
    return re.sub(r'[^\w.\-]', '_', base) or default


def _zip_member_stems(zip_path: str) -> dict[str, set[str]]:
    """Rudisha {stem_lower: {'.shp', '.shx', ...}} kwa members za zip."""
    stems: dict[str, set[str]] = {}
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for member in zf.namelist():
            if member.endswith('/') or '__MACOSX' in member:
                continue
            base = os.path.basename(member)
            if not base or base.startswith('.'):
                continue
            lower = base.lower()
            if lower.endswith('.shp.xml'):
                stem_l = lower[:-len('.shp.xml')]
                stems.setdefault(stem_l, set()).add('.shp.xml')
                continue
            name_part, ext = os.path.splitext(lower)
            if not ext:
                continue
            stems.setdefault(name_part, set()).add(ext)
    return stems


def _validate_zip_shapefile_bundle(zip_path: str) -> str:
    """Hakikisha zip ina .shp, .shx, .dbf. Rudisha stem ya .shp ya kwanza."""
    stems = _zip_member_stems(zip_path)
    shp_stems = [s for s, exts in stems.items() if '.shp' in exts]
    if not shp_stems:
        raise ValueError('Hakuna .shp ndani ya zip. Pakia zip yenye .shp, .shx, .dbf pamoja.')

    stem = shp_stems[0]
    missing = sorted(REQUIRED_SHAPEFILE_EXTS - stems.get(stem, set()))
    if missing:
        raise ValueError(INCOMPLETE_SHAPEFILE_MSG.format(missing=', '.join(missing)))
    return stem


def _extract_shapefile_from_zip(zip_path: str, dest_dir: str) -> str:
    """Chopoa shapefile kutoka zip — faili zote zina msingi uleule na ziko kwenye folda moja."""
    os.makedirs(dest_dir, exist_ok=True)
    stem_l = _validate_zip_shapefile_bundle(zip_path)
    safe_stem = re.sub(r'[^\w.\-]', '_', stem_l) or 'layer'

    with zipfile.ZipFile(zip_path, 'r') as zf:
        for member in zf.namelist():
            if member.endswith('/') or '__MACOSX' in member:
                continue
            base = os.path.basename(member)
            if not base:
                continue
            lower = base.lower()
            if lower.endswith('.shp.xml'):
                if lower[:-len('.shp.xml')] != stem_l:
                    continue
                out_name = f'{safe_stem}.shp.xml'
            else:
                name_part, ext = os.path.splitext(lower)
                if name_part != stem_l:
                    continue
                if ext not in REQUIRED_SHAPEFILE_EXTS | OPTIONAL_SHAPEFILE_EXTS:
                    continue
                out_name = f'{safe_stem}{ext}'
            out_path = os.path.join(dest_dir, out_name)
            with zf.open(member) as src, open(out_path, 'wb') as dst:
                shutil.copyfileobj(src, dst)

    shp_out = os.path.join(dest_dir, f'{safe_stem}.shp')
    if not os.path.isfile(shp_out):
        raise ValueError(INCOMPLETE_SHAPEFILE_MSG.format(missing='.shp'))
    return shp_out


def _find_shp_in_zip(zip_path):
    with zipfile.ZipFile(zip_path, 'r') as zf:
        return [
            n for n in zf.namelist()
            if n.lower().endswith('.shp')
            and '__MACOSX' not in n
            and not os.path.basename(n).startswith('.')
        ]


def _to_gdal_path(abs_path):
    p = os.path.abspath(abs_path).replace('\\', '/')
    if len(p) > 1 and p[1] == ':':
        return p[0].lower() + ':' + p[2:]
    return p


def _read_vsimem_json(vsi_path, gdal_module):
    stat = gdal_module.VSIStatL(vsi_path)
    if stat is None:
        raise ValueError('GDAL haikusoma GeoJSON ya muda')
    handle = gdal_module.VSIFOpenL(vsi_path, 'rb')
    if not handle:
        raise ValueError('GDAL haikuweza kufungua GeoJSON ya muda')
    try:
        raw = gdal_module.VSIFReadL(1, stat.size, handle)
    finally:
        gdal_module.VSIFCloseL(handle)
    return json.loads(raw.decode('utf-8'))


def _friendly_gdal_error(exc: Exception) -> str | None:
    msg = str(exc)
    lower = msg.lower()
    if 'shape_restore_shx' in lower or 'unable to open' in lower and '.shx' in lower:
        return INCOMPLETE_SHAPEFILE_MSG.format(missing='.shx')
    if '.dbf' in lower and ('unable to open' in lower or 'no such file' in lower):
        return INCOMPLETE_SHAPEFILE_MSG.format(missing='.dbf')
    return None


def _configure_gdal_for_shapefile(gdal_module) -> None:
    gdal_module.SetConfigOption('SHAPE_ENCODING', 'UTF-8')
    gdal_module.SetConfigOption('SHAPE_RESTORE_SHX', 'YES')


def _detect_source_srid(source_path: str) -> int | None:
    """Tambua EPSG ya chanzo; None ikiwa .prj haipo au haijulikani."""
    from osgeo import ogr, osr

    ds = ogr.Open(source_path)
    if ds is None:
        return None
    try:
        layer = ds.GetLayer()
        if layer is None:
            return None
        srs = layer.GetSpatialRef()
        if srs is None:
            return None
        srs_clone = srs.Clone()
        srs_clone.AutoIdentifyEPSG()
        auth = srs_clone.GetAuthorityCode(None)
        if auth:
            return int(auth)
    except Exception:
        return None
    finally:
        ds = None
    return None


def _source_layer_info(source_path: str) -> tuple[str | None, int]:
    """Rudisha (jina la tabaka, idadi ya features)."""
    from osgeo import ogr

    ds = ogr.Open(source_path)
    if ds is None:
        return None, 0
    try:
        layer = ds.GetLayer()
        if layer is None:
            return None, 0
        return layer.GetName(), layer.GetFeatureCount()
    finally:
        ds = None


def _build_import_meta(
    *,
    source_layer: str | None,
    source_srid: int,
    source_feature_count: int,
    imported_feature_count: int,
    skipped_features: list[dict],
) -> dict:
    skipped_count = len(skipped_features)
    meta = {
        'source_layer': source_layer,
        'source_srid': source_srid,
        'source_feature_count': source_feature_count,
        'imported_feature_count': imported_feature_count,
        'skipped_count': skipped_count,
        'skipped_features': skipped_features[:50],
        'partial_success': skipped_count > 0,
        'message_sw': '',
    }
    if skipped_count > 0:
        meta['message_sw'] = PARTIAL_SUCCESS_MSG.format(
            imported=imported_feature_count,
            total=source_feature_count,
            skipped=skipped_count,
        )
    return meta


def _attach_import_meta(data: dict, import_meta: dict) -> dict:
    data['import_meta'] = import_meta
    return data


def _normalize_feature_collection(data: dict) -> dict:
    if data.get('type') == 'Feature':
        data = {'type': 'FeatureCollection', 'features': [data]}
    if data.get('type') != 'FeatureCollection':
        raise ValueError('Matokeo si GeoJSON sahihi')
    return data


def _try_vector_translate(source_path: str, gdal_module, source_srid: int) -> dict | None:
    """Jaribu VectorTranslate na -skipfailures; -makevalid ikiwezekana."""
    translate_attempts = [
        {'makeValid': True, 'skipFailures': True},
        {'makeValid': False, 'skipFailures': True},
    ]
    for attempt in translate_attempts:
        out_mem = f'/vsimem/gis_upload_{uuid.uuid4().hex}.geojson'
        try:
            try:
                gdal_module.Unlink(out_mem)
            except Exception:
                pass
            translated = gdal_module.VectorTranslate(
                out_mem,
                source_path,
                format='GeoJSON',
                srcSRS=f'EPSG:{source_srid}',
                dstSRS=f'EPSG:{DISPLAY_SRID}',
                **attempt,
            )
            if translated is None:
                continue
            translated = None
            data = _normalize_feature_collection(_read_vsimem_json(out_mem, gdal_module))
            return data
        except Exception as exc:
            msg = str(exc).lower()
            if attempt.get('makeValid') and 'makevalid' in msg:
                logger.info(
                    'GDAL -makevalid haipatikani; jaribu tena bila makeValid (%s)',
                    source_path,
                )
                continue
            logger.warning(
                'VectorTranslate imeshindwa kwa %s (SRID %s): %s',
                source_path, source_srid, exc,
            )
        finally:
            try:
                gdal_module.Unlink(out_mem)
            except Exception:
                pass
    return None


def _repair_geometry(ogr_geom):
    if ogr_geom is None or ogr_geom.IsEmpty():
        return None
    if ogr_geom.IsValid():
        return ogr_geom
    try:
        fixed = ogr_geom.MakeValid()
    except Exception:
        fixed = None
    if fixed is not None and not fixed.IsEmpty():
        return fixed
    try:
        buffered = ogr_geom.Buffer(0)
    except Exception:
        return None
    if buffered is not None and not buffered.IsEmpty() and buffered.IsValid():
        return buffered
    return None


def _feature_to_geojson(feat, transform) -> dict | None:
    from osgeo import ogr

    geom = feat.GetGeometryRef()
    if geom is None or geom.IsEmpty():
        return None
    geom = _repair_geometry(geom.Clone())
    if geom is None:
        return None
    if transform is not None:
        try:
            geom.Transform(transform)
        except Exception:
            return None
    try:
        feat_copy = feat.Clone()
        feat_copy.SetGeometry(geom)
        payload = json.loads(feat_copy.ExportToJson())
    except Exception:
        return None
    if not payload.get('geometry'):
        return None
    if payload.get('type') != 'Feature':
        payload = {
            'type': 'Feature',
            'geometry': payload.get('geometry'),
            'properties': payload.get('properties') or {},
        }
    return payload


def _convert_features_individually(source_path: str, source_srid: int) -> dict:
    """Soma kila feature peke yake — ruka zile zisizoweza kubadilishwa."""
    from osgeo import ogr, osr

    ds = ogr.Open(source_path)
    if ds is None:
        raise ValueError('Shapefile haikusomwa. Hakikisha .zip ina .shp, .shx, .dbf pamoja.')

    layer = ds.GetLayer()
    if layer is None:
        raise ValueError('Shapefile haina tabaka la kusoma')

    layer_name = layer.GetName()
    source_feature_count = layer.GetFeatureCount()
    src_srs = osr.SpatialReference()
    src_srs.ImportFromEPSG(source_srid)
    dst_srs = osr.SpatialReference()
    dst_srs.ImportFromEPSG(DISPLAY_SRID)
    transform = osr.CoordinateTransformation(src_srs, dst_srs)

    features: list[dict] = []
    skipped_features: list[dict] = []

    for feat in layer:
        fid = feat.GetFID()
        try:
            gj = _feature_to_geojson(feat, transform)
            if gj is None:
                reason = 'jiometri batili au tupu'
                skipped_features.append({'fid': fid, 'reason': reason})
                logger.warning(
                    'Shapefile %s layer %s: feature FID %s imerukwa — %s',
                    source_path, layer_name, fid, reason,
                )
                continue
            features.append(gj)
        except Exception as exc:
            reason = str(exc)[:200]
            skipped_features.append({'fid': fid, 'reason': reason})
            logger.warning(
                'Shapefile %s layer %s: feature FID %s imerukwa — %s',
                source_path, layer_name, fid, reason,
            )

    ds = None

    if not features:
        raise ValueError(
            f'Hakuna features zilizosomwa kutoka tabaka "{layer_name}". '
            'Angalia jiometri na CRS (.prj).'
        )

    import_meta = _build_import_meta(
        source_layer=layer_name,
        source_srid=source_srid,
        source_feature_count=source_feature_count,
        imported_feature_count=len(features),
        skipped_features=skipped_features,
    )
    return _attach_import_meta({'type': 'FeatureCollection', 'features': features}, import_meta)


def _identify_skipped_by_fid(source_path: str, source_srid: int, imported_count: int) -> list[dict]:
    """Tambua FID zilizorukwa baada ya VectorTranslate (kwa ajili ya log)."""
    from osgeo import ogr, osr

    layer_name, source_feature_count = _source_layer_info(source_path)
    if imported_count >= source_feature_count:
        return []

    ds = ogr.Open(source_path)
    if ds is None:
        return []
    layer = ds.GetLayer()
    if layer is None:
        return []

    src_srs = osr.SpatialReference()
    src_srs.ImportFromEPSG(source_srid)
    dst_srs = osr.SpatialReference()
    dst_srs.ImportFromEPSG(DISPLAY_SRID)
    transform = osr.CoordinateTransformation(src_srs, dst_srs)

    skipped: list[dict] = []
    for feat in layer:
        fid = feat.GetFID()
        try:
            if _feature_to_geojson(feat, transform) is None:
                reason = 'jiometri batili au haikubadilishwa'
                skipped.append({'fid': fid, 'reason': reason})
                logger.warning(
                    'Shapefile %s layer %s: feature FID %s imerukwa — %s',
                    source_path, layer_name, fid, reason,
                )
        except Exception as exc:
            reason = str(exc)[:200]
            skipped.append({'fid': fid, 'reason': reason})
            logger.warning(
                'Shapefile %s layer %s: feature FID %s imerukwa — %s',
                source_path, layer_name, fid, reason,
            )

    ds = None
    return skipped


def _convert_to_geojson(source_path, gdal_module):
    _configure_gdal_for_shapefile(gdal_module)

    detected_srid = _detect_source_srid(source_path)
    source_srid = detected_srid or FALLBACK_SOURCE_SRID
    if detected_srid is None:
        logger.info(
            'Shapefile %s haina CRS inayojulikana; tumia EPSG:%s',
            source_path, FALLBACK_SOURCE_SRID,
        )

    layer_name, source_feature_count = _source_layer_info(source_path)

    data = _try_vector_translate(source_path, gdal_module, source_srid)
    if data is None and detected_srid is None and source_srid == FALLBACK_SOURCE_SRID:
        data = _try_vector_translate(source_path, gdal_module, DISPLAY_SRID)
        if data is not None:
            source_srid = DISPLAY_SRID

    if data is None:
        return _convert_features_individually(source_path, source_srid)

    if not data.get('features'):
        return _convert_features_individually(source_path, source_srid)

    imported_count = len(data['features'])
    skipped_features: list[dict] = []
    if source_feature_count and imported_count < source_feature_count:
        skipped_features = _identify_skipped_by_fid(source_path, source_srid, imported_count)

    import_meta = _build_import_meta(
        source_layer=layer_name,
        source_srid=source_srid,
        source_feature_count=source_feature_count or imported_count,
        imported_feature_count=imported_count,
        skipped_features=skipped_features,
    )
    return _attach_import_meta(data, import_meta)
