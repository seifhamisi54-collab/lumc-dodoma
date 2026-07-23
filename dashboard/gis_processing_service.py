"""
GIS processing — GDAL/GEOS (sahihi kama QGIS & Mapshaper).
Turf.js kwenye browser haifiki usahihi wa GEOS kwa topology na cleaning.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)

ISSUE_LABELS = {
    'overlap': 'Must not overlap',
    'gap': 'Must not have gaps',
    'invalid': 'Invalid geometry',
    'self_intersect': 'Must not self-intersect',
    'duplicate': 'Must not duplicate',
    'sliver': 'Sliver polygon',
    'dangle': 'Dangling edge',
    'hole': 'Invalid hole',
    'null_geom': 'Null / empty geometry',
    'fixed_overlap': 'Overlap fixed',
    'fixed_gap': 'Gap fixed',
}


def _load_gdal():
    from osgeo import gdal, ogr, osr
    gdal.UseExceptions()
    return gdal, ogr, osr


def _feat_name(props: dict | None, idx: int) -> str:
    if not props:
        return f'Feature {idx}'
    for key in ('name', 'NAME', 'district_n', 'ward_name', 'id', 'ID'):
        if props.get(key):
            return str(props[key])
    return f'Feature {idx}'


def _json_geom(ogr_geom) -> dict | None:
    if ogr_geom is None:
        return None
    try:
        return json.loads(ogr_geom.ExportToJson())
    except Exception:
        return None


def _ogr_geom_from_feature(feature: dict, ogr_module, osr_module=None):
    geom = feature.get('geometry')
    if not geom:
        return None
    g = ogr_module.CreateGeometryFromJson(json.dumps(geom))
    if g and osr_module is not None:
        # GeoJSON coordinates are always [lon, lat]; fix GDAL 3 axis metadata.
        g.AssignSpatialReference(_wgs84_srs(osr_module))
    return g


def _wgs84_srs(osr_module):
    srs = osr_module.SpatialReference()
    srs.ImportFromEPSG(4326)
    srs.SetAxisMappingStrategy(osr_module.OAMS_TRADITIONAL_GIS_ORDER)
    return srs


def _to_wgs84(geom, ogr_module, osr_module):
    """Normalize geometry to WGS84 lon/lat (X=lon, Y=lat) for GEOS operations."""
    if geom is None or geom.IsEmpty():
        return geom
    wgs = _wgs84_srs(osr_module)
    src = geom.GetSpatialReference()
    out = geom.Clone()
    if src is None:
        out.AssignSpatialReference(wgs)
        return out

    src_norm = src.Clone()
    src_norm.SetAxisMappingStrategy(osr_module.OAMS_TRADITIONAL_GIS_ORDER)
    if src_norm.IsSame(wgs):
        # VectorTranslate GeoJSON may attach EPSG:4326 with lat/lon axis order while
        # values remain [lon, lat] — reassign CRS without moving coordinates.
        out.AssignSpatialReference(wgs)
        return out

    tx = osr_module.CoordinateTransformation(src_norm, wgs)
    out.Transform(tx)
    out.AssignSpatialReference(wgs)
    return out


def _envelope_wgs84(geom) -> dict[str, float] | None:
    """Return {min_lon, max_lon, min_lat, max_lat} for a WGS84-normalized geometry."""
    if geom is None or geom.IsEmpty():
        return None
    minx, maxx, miny, maxy = geom.GetEnvelope()
    return {
        'min_lon': minx,
        'max_lon': maxx,
        'min_lat': miny,
        'max_lat': maxy,
    }


def _fc_envelope_wgs84(fc: dict, ogr_module, osr_module) -> dict[str, float] | None:
    """Bounding box of all features in lon/lat."""
    bounds: dict[str, float] | None = None
    for feat in fc.get('features', []):
        g = _ogr_geom_from_feature(feat, ogr_module, osr_module)
        if not g or g.IsEmpty():
            continue
        g = _to_wgs84(g, ogr_module, osr_module)
        env = _envelope_wgs84(g)
        if not env:
            continue
        if bounds is None:
            bounds = dict(env)
        else:
            bounds['min_lon'] = min(bounds['min_lon'], env['min_lon'])
            bounds['max_lon'] = max(bounds['max_lon'], env['max_lon'])
            bounds['min_lat'] = min(bounds['min_lat'], env['min_lat'])
            bounds['max_lat'] = max(bounds['max_lat'], env['max_lat'])
    return bounds


# Parcel/CCRO uploads: trust user's ward selection if strict clip finds nothing.
PARCEL_CLIP_DATA_TYPES = frozenset({'parcels', 'landuse', 'other'})


def clip_geojson_to_aoi(
    fc: dict,
    aoi_geometry: dict,
    *,
    data_type: str | None = None,
    trust_user_aoi: bool | None = None,
) -> dict:
    """Kata features zilizopakiwa kwa mipaka ya wilaya/kata (GEOS Intersection)."""
    _, ogr, osr = _load_gdal()
    raw_count = len(fc.get('features', []))
    aoi_geom = ogr.CreateGeometryFromJson(json.dumps(aoi_geometry))
    if aoi_geom is None or aoi_geom.IsEmpty():
        raise ValueError('Mipaka ya wilaya/kata haipatikani')
    aoi_geom = _to_wgs84(aoi_geom, ogr, osr)
    aoi_extent = _envelope_wgs84(aoi_geom)
    input_extent = _fc_envelope_wgs84(fc, ogr, osr)

    out_features = []
    for feat in fc.get('features', []):
        g = _ogr_geom_from_feature(feat, ogr, osr)
        if not g or g.IsEmpty():
            continue
        g = _to_wgs84(g, ogr, osr)
        if not g.Intersects(aoi_geom):
            continue
        clipped = g.Intersection(aoi_geom)
        if clipped is None or clipped.IsEmpty():
            continue
        out_features.append({
            'type': 'Feature',
            'properties': feat.get('properties') or {},
            'geometry': _json_geom(clipped),
        })

    clip_meta: dict[str, Any] = {
        'raw_count': raw_count,
        'clipped_count': len(out_features),
        'input_extent': input_extent,
        'aoi_extent': aoi_extent,
        'clip_skipped': False,
        'clip_fallback': False,
    }

    if len(out_features) == 0 and raw_count > 0:
        logger.warning(
            'clip_geojson_to_aoi: 0/%s features intersect AOI '
            '(data_type=%s input_extent=%s aoi_extent=%s)',
            raw_count, data_type, input_extent, aoi_extent,
        )
        use_fallback = trust_user_aoi
        if use_fallback is None:
            use_fallback = (data_type or '') in PARCEL_CLIP_DATA_TYPES
        if use_fallback:
            clip_meta['clip_skipped'] = True
            clip_meta['clip_fallback'] = True
            logger.info(
                'clip_geojson_to_aoi: trusting user AOI — importing all %s features',
                raw_count,
            )
            return _attach_clip_meta(fc, clip_meta)

    return _attach_clip_meta(
        {'type': 'FeatureCollection', 'features': out_features},
        clip_meta,
    )


def _attach_clip_meta(fc: dict, clip_meta: dict) -> dict:
    fc = dict(fc)
    fc['clip_meta'] = clip_meta
    return fc


def _feature_from_ogr(feat, layer_defn, ogr_module) -> dict:
    geom = feat.GetGeometryRef()
    props = {}
    for i in range(layer_defn.GetFieldCount()):
        fd = layer_defn.GetFieldDefn(i)
        props[fd.GetName()] = feat.GetField(i)
    return {
        'type': 'Feature',
        'properties': props,
        'geometry': _json_geom(geom),
    }


def _write_fc_to_vsimem(fc: dict, gdal_module, ogr_module) -> str:
    path = f'/vsimem/gis_proc_{uuid.uuid4().hex}.geojson'
    data = json.dumps(fc, ensure_ascii=False).encode('utf-8')
    gdal_module.FileFromMemBuffer(path, data)
    return path


def _read_vsimem_geojson(path: str, gdal_module) -> dict:
    stat = gdal_module.VSIStatL(path)
    if stat is None:
        raise ValueError('Imeshindwa kusoma matokeo ya GDAL')
    handle = gdal_module.VSIFOpenL(path, 'rb')
    try:
        raw = gdal_module.VSIFReadL(1, stat.size, handle)
    finally:
        gdal_module.VSIFCloseL(handle)
    data = json.loads(raw.decode('utf-8'))
    if data.get('type') == 'Feature':
        data = {'type': 'FeatureCollection', 'features': [data]}
    return data


def _unlink(path: str, gdal_module):
    try:
        gdal_module.Unlink(path)
    except Exception:
        pass


def _bbox(fc: dict) -> tuple[float, float, float, float] | None:
    gdal, ogr, _ = _load_gdal()
    path = _write_fc_to_vsimem(fc, gdal, ogr)
    try:
        ds = ogr.Open(path)
        if not ds:
            return None
        lyr = ds.GetLayer(0)
        return lyr.GetExtent() if lyr else None
    finally:
        _unlink(path, gdal)


def _utm_srs_for_extent(extent: tuple[float, float, float, float], osr_module):
    minx, maxx, miny, maxy = extent[0], extent[1], extent[2], extent[3]
    lon = (minx + maxx) / 2.0
    lat = (miny + maxy) / 2.0
    zone = int((lon + 180) / 6) + 1
    epsg = (32600 if lat >= 0 else 32700) + zone
    srs = osr_module.SpatialReference()
    srs.ImportFromEPSG(epsg)
    return srs


def _reproject_geom(geom, target_srs, osr_module):
    if geom is None:
        return None
    src_srs = geom.GetSpatialReference()
    if src_srs is None:
        wgs = osr_module.SpatialReference()
        wgs.ImportFromEPSG(4326)
        geom.AssignSpatialReference(wgs)
        src_srs = wgs
    if src_srs.IsSame(target_srs):
        return geom.Clone()
    tx = osr_module.CoordinateTransformation(src_srs, target_srs)
    cloned = geom.Clone()
    cloned.Transform(tx)
    return cloned


def _make_valid(geom, ogr_module):
    if geom is None:
        return None
    if geom.IsValid():
        return geom.Clone()
    if hasattr(geom, 'MakeValid'):
        try:
            fixed = geom.MakeValid()
            if fixed and not fixed.IsEmpty():
                return fixed
        except Exception:
            pass
    try:
        buffered = geom.Buffer(0)
        if buffered and not buffered.IsEmpty():
            return buffered
    except Exception:
        pass
    return geom.Clone()


def _area_sqm(geom, utm_srs, osr_module) -> float:
    if geom is None or geom.IsEmpty():
        return 0.0
    g = _reproject_geom(geom, utm_srs, osr_module)
    return abs(g.GetArea()) if g else 0.0


def _load_features(fc: dict) -> list[dict]:
    if not fc or fc.get('type') != 'FeatureCollection':
        return []
    return list(fc.get('features') or [])


def run_topology_check(fc: dict, rules: dict | None = None, min_area_sqm: float = 100) -> dict:
    """QGIS Topology Checker — GEOS/GDAL."""
    _, ogr, osr = _load_gdal()
    rules = rules or {}
    enabled = {
        'overlap': rules.get('overlap', True),
        'gap': rules.get('gap', True),
        'invalid': rules.get('invalid', True),
        'self_intersect': rules.get('self_intersect', True),
        'duplicate': rules.get('duplicate', True),
        'sliver': rules.get('sliver', True),
        'dangle': rules.get('dangle', False),
        'hole': rules.get('hole', True),
        'null_geom': rules.get('null_geom', True),
    }
    features = _load_features(fc)
    issues: list[dict] = []
    stats = {k: 0 for k in (
        'overlap', 'gap', 'invalid', 'self_intersect', 'duplicate',
        'sliver', 'dangle', 'hole', 'null_geom',
    )}
    parsed = []
    wkb_seen: dict[str, str] = {}
    extent = _bbox(fc)
    utm = _utm_srs_for_extent(extent, osr) if extent else None

    for idx, raw in enumerate(features):
        props = raw.get('properties') or {}
        name = _feat_name(props, idx)
        geom = _ogr_geom_from_feature(raw, ogr)

        if geom is None or geom.IsEmpty():
            if enabled['null_geom']:
                stats['null_geom'] += 1
                issues.append({
                    'rule': 'null_geom', 'type': 'null_geom', 'name': name,
                    'feature': raw, 'message': 'Geometry haipo au ni tupu',
                })
            continue

        parsed.append({'idx': idx, 'raw': raw, 'geom': geom, 'name': name})

        if enabled['invalid'] and not geom.IsValid():
            stats['invalid'] += 1
            reason = ''
            if hasattr(geom, 'IsValidReason'):
                try:
                    reason = geom.IsValidReason() or ''
                except Exception:
                    pass
            issues.append({
                'rule': 'invalid', 'type': 'invalid', 'name': name,
                'feature': raw,
                'message': reason or 'Jiometri batili (GEOS)',
            })
            if enabled['self_intersect'] and 'self-intersection' in reason.lower():
                stats['self_intersect'] += 1
                issues.append({
                    'rule': 'self_intersect', 'type': 'self_intersect', 'name': name,
                    'feature': raw, 'message': reason,
                })
        elif enabled['self_intersect'] and geom.GetGeometryType() in (
            ogr.wkbPolygon, ogr.wkbMultiPolygon,
        ):
            if not geom.IsValid():
                stats['self_intersect'] += 1
                issues.append({
                    'rule': 'self_intersect', 'type': 'self_intersect', 'name': name,
                    'feature': raw, 'message': 'Self-intersection (GEOS)',
                })

        if enabled['duplicate']:
            try:
                wkb = geom.ExportToWkb()
                key = wkb.hex() if isinstance(wkb, bytes) else str(wkb)
                if key in wkb_seen:
                    stats['duplicate'] += 1
                    issues.append({
                        'rule': 'duplicate', 'type': 'duplicate', 'name': name,
                        'feature': raw, 'message': f'Duplicate ya {wkb_seen[key]}',
                    })
                else:
                    wkb_seen[key] = name
            except Exception:
                pass

        if enabled['sliver'] and utm and geom.GetGeometryType() in (
            ogr.wkbPolygon, ogr.wkbMultiPolygon,
        ):
            area = _area_sqm(geom, utm, osr)
            if 0 < area < min_area_sqm:
                stats['sliver'] += 1
                issues.append({
                    'rule': 'sliver', 'type': 'sliver', 'name': name,
                    'feature': raw, 'message': f'Eneo dogo: {area:.1f} m² (GEOS)',
                })

        if enabled['hole'] and geom.GetGeometryType() == ogr.wkbPolygon:
            for ri in range(1, geom.GetGeometryCount()):
                ring = geom.GetGeometryRef(ri)
                if ring and ring.GetPointCount() < 4:
                    stats['hole'] += 1
                    issues.append({
                        'rule': 'hole', 'type': 'hole', 'name': name,
                        'feature': raw, 'message': f'Tundu batili #{ri}',
                    })

    if enabled['overlap']:
        polys = [p for p in parsed if p['geom'].GetGeometryType() in (
            ogr.wkbPolygon, ogr.wkbMultiPolygon,
        )]
        for i in range(len(polys)):
            for j in range(i + 1, len(polys)):
                a, b = polys[i], polys[j]
                try:
                    if a['geom'].Overlaps(b['geom']) or a['geom'].Contains(b['geom']) or b['geom'].Contains(a['geom']):
                        inter = a['geom'].Intersection(b['geom'])
                        if inter and not inter.IsEmpty():
                            if utm:
                                ia = _area_sqm(inter, utm, osr)
                                if ia < 0.01:
                                    continue
                            stats['overlap'] += 1
                            issues.append({
                                'rule': 'overlap', 'type': 'overlap',
                                'name': a['name'], 'b': b['name'],
                                'feature': {
                                    'type': 'Feature',
                                    'properties': {'name': 'Overlap'},
                                    'geometry': _json_geom(inter),
                                },
                                'message': f"{a['name']} / {b['name']}",
                            })
                except Exception:
                    continue

    if enabled['gap'] and utm and len(parsed) >= 2:
        polys = [p for p in parsed if p['geom'].GetGeometryType() in (
            ogr.wkbPolygon, ogr.wkbMultiPolygon,
        )]
        if len(polys) >= 2:
            try:
                union = polys[0]['geom'].Clone()
                for p in polys[1:]:
                    union = union.Union(p['geom'])
                mp = ogr.Geometry(ogr.wkbMultiPolygon)
                for p in polys:
                    g = p['geom'].Clone()
                    if g.GetGeometryType() == ogr.wkbPolygon:
                        mp.AddGeometry(g)
                    else:
                        for k in range(g.GetGeometryCount()):
                            mp.AddGeometry(g.GetGeometryRef(k).Clone())
                hull = mp.ConvexHull()
                if hull and union:
                    gap = hull.Difference(union)
                    if gap and not gap.IsEmpty():
                        ga = _area_sqm(gap, utm, osr)
                        if ga > min_area_sqm:
                            stats['gap'] += 1
                            issues.append({
                                'rule': 'gap', 'type': 'gap', 'name': 'Pengo la topology',
                                'feature': {
                                    'type': 'Feature',
                                    'properties': {'name': 'Gap'},
                                    'geometry': _json_geom(gap),
                                },
                                'message': f'Pengo ~{ga:.0f} m² (GEOS)',
                            })
            except Exception as exc:
                logger.debug('Gap check skipped: %s', exc)

    return {
        'engine': 'GDAL/GEOS',
        'issues': issues,
        'stats': stats,
        'feature_count': len(features),
    }


def clean_geojson(fc: dict, options: dict | None = None) -> dict:
    """Mapshaper -clean style — GEOS MakeValid, overlap repair, slivers."""
    gdal, ogr, osr = _load_gdal()
    options = options or {}
    min_area = float(options.get('min_area_sqm', 100))
    features = _load_features(fc)
    report = {
        'removed': 0, 'fixed_invalid': 0, 'fixed_overlap': 0, 'fixed_gap': 0,
        'fixed_duplicate': 0, 'fixed_sliver': 0, 'fixed_coords': 0, 'issues': [],
    }
    extent = _bbox(fc)
    utm = _utm_srs_for_extent(extent, osr) if extent else None
    out_feats: list[dict] = []
    wkb_seen: set[str] = set()

    for idx, raw in enumerate(features):
        props = dict(raw.get('properties') or {})
        name = _feat_name(props, idx)
        geom = _ogr_geom_from_feature(raw, ogr)
        if geom is None or geom.IsEmpty():
            report['removed'] += 1
            report['issues'].append({
                'type': 'null_geom', 'name': name, 'message': 'Imeondolewa — hakuna geometry',
            })
            continue

        if options.get('fix_invalid', True) or options.get('fix_coords', True):
            if not geom.IsValid():
                fixed = _make_valid(geom, ogr)
                if fixed:
                    geom = fixed
                    report['fixed_invalid'] += 1
                    report['issues'].append({
                        'type': 'invalid', 'name': name,
                        'message': 'Jiometri imerekebishwa (GEOS MakeValid)',
                    })

        if options.get('remove_slivers', True) and utm and geom.GetGeometryType() in (
            ogr.wkbPolygon, ogr.wkbMultiPolygon,
        ):
            area = _area_sqm(geom, utm, osr)
            if area < min_area:
                report['fixed_sliver'] += 1
                report['issues'].append({
                    'type': 'sliver', 'name': name,
                    'message': f'Sliver imeondolewa ({area:.1f} m²)',
                })
                continue

        feat = {
            'type': 'Feature',
            'properties': props,
            'geometry': _json_geom(geom),
        }

        if options.get('remove_duplicates', True):
            try:
                key = geom.ExportToWkb().hex()
                if key in wkb_seen:
                    report['fixed_duplicate'] += 1
                    report['issues'].append({
                        'type': 'duplicate', 'name': name, 'message': 'Duplicate imeondolewa',
                    })
                    continue
                wkb_seen.add(key)
            except Exception:
                pass

        out_feats.append(feat)

    if options.get('fix_overlaps', True) and len(out_feats) > 1:
        geoms = []
        for f in out_feats:
            g = _ogr_geom_from_feature(f, ogr)
            geoms.append(g if g else None)
        for i in range(len(out_feats)):
            if not geoms[i]:
                continue
            for j in range(i + 1, len(out_feats)):
                if not geoms[j]:
                    continue
                try:
                    if geoms[i].Overlaps(geoms[j]) or geoms[i].Contains(geoms[j]):
                        inter = geoms[i].Intersection(geoms[j])
                        if inter and not inter.IsEmpty():
                            ai = _area_sqm(geoms[i], utm, osr) if utm else geoms[i].Area()
                            aj = _area_sqm(geoms[j], utm, osr) if utm else geoms[j].Area()
                            if aj <= ai:
                                diff = geoms[j].Difference(geoms[i])
                                geoms[j] = diff
                                out_feats[j]['geometry'] = _json_geom(diff)
                            else:
                                diff = geoms[i].Difference(geoms[j])
                                geoms[i] = diff
                                out_feats[i]['geometry'] = _json_geom(diff)
                            report['fixed_overlap'] += 1
                            report['issues'].append({
                                'type': 'fixed_overlap',
                                'name': _feat_name(out_feats[j].get('properties'), j),
                                'message': 'Overlap imerekebishwa (GEOS Difference)',
                                'feature': out_feats[j],
                            })
                except Exception:
                    continue

    if options.get('fix_gaps', True) and utm and len(out_feats) >= 2:
        try:
            polys = []
            for f in out_feats:
                g = _ogr_geom_from_feature(f, ogr)
                if g and g.GetGeometryType() in (ogr.wkbPolygon, ogr.wkbMultiPolygon):
                    polys.append(g)
            if len(polys) >= 2:
                union = polys[0].Clone()
                for g in polys[1:]:
                    union = union.Union(g)
                mp = ogr.Geometry(ogr.wkbMultiPolygon)
                for g in polys:
                    if g.GetGeometryType() == ogr.wkbPolygon:
                        mp.AddGeometry(g.Clone())
                    else:
                        for k in range(g.GetGeometryCount()):
                            mp.AddGeometry(g.GetGeometryRef(k).Clone())
                hull = mp.ConvexHull()
                gap = hull.Difference(union) if hull and union else None
                if gap and not gap.IsEmpty():
                    ga = _area_sqm(gap, utm, osr)
                    if ga > min_area:
                        valid_gap = _make_valid(gap, ogr)
                        out_feats.append({
                            'type': 'Feature',
                            'properties': {'name': 'Gap Fixed', '_gap_fix': True},
                            'geometry': _json_geom(valid_gap),
                        })
                        report['fixed_gap'] += 1
                        report['issues'].append({
                            'type': 'fixed_gap', 'name': 'Gap patch',
                            'message': 'Pengo limejazwa (GEOS)',
                        })
        except Exception as exc:
            logger.debug('Gap fix skipped: %s', exc)

    return {
        'engine': 'GDAL/GEOS',
        'feature_collection': {'type': 'FeatureCollection', 'features': out_feats},
        'report': report,
    }


def _layer_to_geojson_file(layer, path: str, gdal_module, ogr_module):
    drv = ogr_module.GetDriverByName('GeoJSON')
    if gdal_module.VSIStatL(path):
        gdal_module.Unlink(path)
    out_ds = drv.CreateDataSource(path)
    out_lyr = out_ds.CreateLayer('out', layer.GetSpatialRef(), layer.GetGeomType())
    in_defn = layer.GetLayerDefn()
    for i in range(in_defn.GetFieldCount()):
        out_lyr.CreateField(in_defn.GetFieldDefn(i))
    for feat in layer:
        out_lyr.CreateFeature(feat.Clone())
    out_ds = None


def run_edit_command(fc: dict, command: str, params: dict | None = None) -> dict:
    """Mapshaper-style editing — GDAL/GEOS."""
    gdal, ogr, osr = _load_gdal()
    params = params or {}
    command = (command or '').strip().lower()
    features = _load_features(fc)

    if not features:
        raise ValueError('Pakia data kwanza')

    if command == 'clean':
        result = clean_geojson(fc, {
            'min_area_sqm': float(params.get('minArea', 100)),
            'fix_gaps': True, 'fix_overlaps': True, 'fix_invalid': True,
            'remove_duplicates': True, 'remove_slivers': True, 'fix_coords': True,
        })
        return {
            'engine': 'GDAL/GEOS',
            'geojson': result['feature_collection'],
            'message': 'Clean imekamilika (Mapshaper-style GEOS)',
            'report': result['report'],
        }

    if command == 'filter-slivers':
        min_a = float(params.get('minArea', 100))
        result = clean_geojson(fc, {
            'min_area_sqm': min_a,
            'fix_gaps': False, 'fix_overlaps': False, 'fix_invalid': False,
            'remove_duplicates': False, 'remove_slivers': True, 'fix_coords': False,
        })
        return {
            'engine': 'GDAL/GEOS',
            'geojson': result['feature_collection'],
            'message': f'Slivers < {min_a} m² zimeondolewa (GEOS)',
        }

    src_path = _write_fc_to_vsimem(fc, gdal, ogr)
    out_path = f'/vsimem/gis_out_{uuid.uuid4().hex}.geojson'

    try:
        if command == 'buffer':
            distance = float(params.get('distance', 100))
            units = params.get('units', 'meters')
            if units == 'kilometers':
                distance *= 1000
            elif units == 'feet':
                distance *= 0.3048
            ds = ogr.Open(src_path)
            lyr = ds.GetLayer(0)
            extent = lyr.GetExtent()
            utm = _utm_srs_for_extent(extent, osr)
            mem_drv = ogr.GetDriverByName('Memory')
            mem = mem_drv.CreateDataSource('buf')
            out_lyr = mem.CreateLayer('out', lyr.GetSpatialRef(), ogr.wkbUnknown)
            layer_defn = lyr.GetLayerDefn()
            for i in range(layer_defn.GetFieldCount()):
                out_lyr.CreateField(layer_defn.GetFieldDefn(i))
            wgs = _wgs84(osr)
            for feat in lyr:
                geom = feat.GetGeometryRef()
                if not geom:
                    continue
                g = _reproject_geom(geom, utm, osr)
                buf = g.Buffer(distance)
                if lyr.GetSpatialRef():
                    buf = _reproject_geom(buf, lyr.GetSpatialRef(), osr)
                else:
                    buf = _reproject_geom(buf, wgs, osr)
                nf = ogr.Feature(out_lyr.GetLayerDefn())
                nf.SetGeometry(buf)
                for i in range(layer_defn.GetFieldCount()):
                    nf.SetField(i, feat.GetField(i))
                out_lyr.CreateFeature(nf)
            _layer_to_geojson_file(out_lyr, out_path, gdal, ogr)
            message = f'Buffer {distance}m (GEOS)'

        elif command in ('dissolve', 'dissolve2'):
            field = params.get('field', 'name')
            groups: dict[Any, list] = {}
            for f in features:
                key = (f.get('properties') or {}).get(field, '')
                g = _ogr_geom_from_feature(f, ogr)
                if g:
                    groups.setdefault(key, []).append(g)
            out_feats = []
            for key, geoms in groups.items():
                union = geoms[0].Clone()
                for g in geoms[1:]:
                    union = union.Union(g)
                props = {field: key}
                out_feats.append({
                    'type': 'Feature',
                    'properties': props,
                    'geometry': _json_geom(union),
                })
            geojson = {'type': 'FeatureCollection', 'features': out_feats}
            return {
                'engine': 'GDAL/GEOS',
                'geojson': geojson,
                'message': f'Dissolve kwa "{field}" (GEOS Union)',
            }

        elif command in ('union', 'mosaic'):
            geoms = []
            for f in features:
                g = _ogr_geom_from_feature(f, ogr)
                if g:
                    geoms.append(g)
            if not geoms:
                raise ValueError('Hakuna geometry')
            union = geoms[0].Clone()
            for g in geoms[1:]:
                union = union.Union(g)
            geojson = {
                'type': 'FeatureCollection',
                'features': [{
                    'type': 'Feature',
                    'properties': {'name': 'union'},
                    'geometry': _json_geom(union),
                }],
            }
            return {
                'engine': 'GDAL/GEOS',
                'geojson': geojson,
                'message': 'Union/mosaic (GEOS)',
            }

        elif command == 'simplify':
            tol = float(params.get('tolerance', 0.001))
            hq = str(params.get('highQuality', 'true')).lower() in ('1', 'true', 'yes')
            ds = ogr.Open(src_path)
            lyr = ds.GetLayer(0)
            mem_drv = ogr.GetDriverByName('Memory')
            mem = mem_drv.CreateDataSource('simp')
            out_lyr = mem.CreateLayer('out', lyr.GetSpatialRef(), ogr.wkbUnknown)
            layer_defn = lyr.GetLayerDefn()
            for i in range(layer_defn.GetFieldCount()):
                out_lyr.CreateField(layer_defn.GetFieldDefn(i))
            for feat in lyr:
                geom = feat.GetGeometryRef()
                if not geom:
                    continue
                if hq and hasattr(geom, 'SimplifyPreserveTopology'):
                    sg = geom.SimplifyPreserveTopology(tol)
                else:
                    sg = geom.Simplify(tol)
                nf = ogr.Feature(out_lyr.GetLayerDefn())
                nf.SetGeometry(sg)
                for i in range(layer_defn.GetFieldCount()):
                    nf.SetField(i, feat.GetField(i))
                out_lyr.CreateFeature(nf)
            _layer_to_geojson_file(out_lyr, out_path, gdal, ogr)
            message = f'Simplify tolerance={tol} (GEOS preserve topology)'

        elif command == 'explode':
            out_feats = []
            for f in features:
                props = dict(f.get('properties') or {})
                g = _ogr_geom_from_feature(f, ogr)
                if not g:
                    continue
                gtype = g.GetGeometryType()
                if gtype in (ogr.wkbMultiPolygon, ogr.wkbMultiLineString, ogr.wkbMultiPoint):
                    for i in range(g.GetGeometryCount()):
                        part = g.GetGeometryRef(i)
                        out_feats.append({
                            'type': 'Feature',
                            'properties': dict(props),
                            'geometry': _json_geom(part),
                        })
                else:
                    out_feats.append(f)
            return {
                'engine': 'GDAL/GEOS',
                'geojson': {'type': 'FeatureCollection', 'features': out_feats},
                'message': 'Explode multi-part (GEOS)',
            }

        else:
            raise ValueError(
                f'Amri "{command}" bado haijatekelezwa kwenye server. '
                'Jaribu: buffer, dissolve, union, simplify, clean, explode, filter-slivers'
            )

        geojson = _read_vsimem_geojson(out_path, gdal)
        return {
            'engine': 'GDAL/GEOS',
            'geojson': geojson,
            'message': message,
        }
    finally:
        _unlink(src_path, gdal)
        _unlink(out_path, gdal)


def _wgs84(osr_module):
    return _wgs84_srs(osr_module)
