"""Tests for ward/district clip during shapefile upload."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from django.test import SimpleTestCase

from dashboard.gis_processing_service import (
    PARCEL_CLIP_DATA_TYPES,
    clip_geojson_to_aoi,
    _to_wgs84,
    _load_gdal,
    _wgs84_srs,
)


def _square_fc(minx, miny, maxx, maxy) -> dict:
    return {
        'type': 'FeatureCollection',
        'features': [{
            'type': 'Feature',
            'properties': {'name': 'parcel'},
            'geometry': {
                'type': 'Polygon',
                'coordinates': [[
                    [minx, miny],
                    [maxx, miny],
                    [maxx, maxy],
                    [minx, maxy],
                    [minx, miny],
                ]],
            },
        }],
    }


def _square_aoi(minx, miny, maxx, maxy) -> dict:
    return {
        'type': 'Polygon',
        'coordinates': [[
            [minx, miny],
            [maxx, miny],
            [maxx, maxy],
            [minx, maxy],
            [minx, miny],
        ]],
    }


class ClipAxisOrderTests(SimpleTestCase):
    """GeoJSON lon/lat must intersect AOI after GDAL 3 axis normalization."""

    def test_overlapping_squares_clip(self):
        fc = _square_fc(35.30, -9.71, 35.31, -9.70)
        aoi = _square_aoi(35.29, -9.72, 35.32, -9.69)
        result = clip_geojson_to_aoi(fc, aoi, data_type='village_boundary')
        meta = result['clip_meta']
        self.assertEqual(meta['clipped_count'], 1)
        self.assertEqual(len(result['features']), 1)
        self.assertFalse(meta.get('clip_fallback'))

    def test_vector_translate_srs_does_not_break_intersect(self):
        shp = Path(r'D:/SITE/MADABA/mawesu/Mpango kinaa/igawisenga.shp')
        if not shp.is_file():
            self.skipTest('igawisenga.shp haipatikani')

        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tanzania_gis.settings')
        import django
        django.setup()

        from osgeo import gdal
        from dashboard.shapefile_upload_service import _convert_to_geojson, _to_gdal_path

        gdal.UseExceptions()
        fc = _convert_to_geojson(_to_gdal_path(str(shp)), gdal)
        aoi = _square_aoi(35.29, -9.72, 35.32, -9.69)
        result = clip_geojson_to_aoi(fc, aoi, data_type='village_boundary')
        self.assertGreater(result['clip_meta']['clipped_count'], 0)


class ParcelClipFallbackTests(SimpleTestCase):
    def test_parcel_types_include_parcels(self):
        self.assertIn('parcels', PARCEL_CLIP_DATA_TYPES)

    def test_fallback_when_no_intersection(self):
        fc = _square_fc(36.0, -8.0, 36.01, -7.99)
        aoi = _square_aoi(35.0, -9.0, 35.1, -8.9)
        result = clip_geojson_to_aoi(fc, aoi, data_type='parcels')
        meta = result['clip_meta']
        self.assertTrue(meta['clip_fallback'])
        self.assertEqual(len(result['features']), 1)

    def test_strict_types_still_fail_without_fallback(self):
        fc = _square_fc(36.0, -8.0, 36.01, -7.99)
        aoi = _square_aoi(35.0, -9.0, 35.1, -8.9)
        result = clip_geojson_to_aoi(fc, aoi, data_type='village_boundary')
        meta = result['clip_meta']
        self.assertFalse(meta.get('clip_fallback'))
        self.assertEqual(len(result['features']), 0)


class Wgs84NormalizationTests(SimpleTestCase):
    def test_lat_lon_axis_metadata_fixed_without_moving_coords(self):
        _, ogr, osr = _load_gdal()
        geom = ogr.CreateGeometryFromWkt('POLYGON((35.30 -9.71, 35.31 -9.71, 35.31 -9.70, 35.30 -9.70, 35.30 -9.71))')
        wrong_srs = osr.SpatialReference()
        wrong_srs.ImportFromEPSG(4326)
        geom.AssignSpatialReference(wrong_srs)
        normalized = _to_wgs84(geom, ogr, osr)
        env = normalized.GetEnvelope()
        self.assertAlmostEqual(env[0], 35.30, places=4)
        self.assertAlmostEqual(env[2], -9.71, places=4)


if __name__ == '__main__':
    unittest.main()
