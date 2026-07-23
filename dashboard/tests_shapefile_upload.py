"""Tests for shapefile upload validation and extraction."""
from __future__ import annotations

import io
import json
import os
import tempfile
import zipfile
from pathlib import Path
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings

from dashboard.shapefile_upload_service import (
    INCOMPLETE_SHAPEFILE_MSG,
    PARTIAL_SUCCESS_MSG,
    _build_import_meta,
    _extract_shapefile_from_zip,
    _validate_zip_shapefile_bundle,
    parse_spatial_upload_files,
)


def _make_zip(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buf.getvalue()


@override_settings(BASE_DIR=Path(tempfile.gettempdir()) / 'tanzania_gis_test')
class ShapefileZipValidationTests(SimpleTestCase):
    def test_rejects_zip_without_shp(self):
        data = _make_zip({'.shx': b'x', 'layer.dbf': b'd'})
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
            tmp.write(data)
            path = tmp.name
        try:
            with self.assertRaises(ValueError) as ctx:
                _validate_zip_shapefile_bundle(path)
            self.assertIn('.shp', str(ctx.exception))
        finally:
            os.unlink(path)

    def test_rejects_zip_with_shp_only(self):
        data = _make_zip({'Mpangokinaa1 mwande.shp': b'shp'})
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
            tmp.write(data)
            path = tmp.name
        try:
            with self.assertRaises(ValueError) as ctx:
                _validate_zip_shapefile_bundle(path)
            msg = str(ctx.exception)
            self.assertIn('.shx', msg)
            self.assertIn('.dbf', msg)
        finally:
            os.unlink(path)

    def test_accepts_complete_bundle(self):
        data = _make_zip({
            'Mpangokinaa1 mwande.shp': b'shp',
            'Mpangokinaa1 mwande.shx': b'shx',
            'Mpangokinaa1 mwande.dbf': b'dbf',
            'Mpangokinaa1 mwande.prj': b'prj',
        })
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
            tmp.write(data)
            path = tmp.name
        try:
            stem = _validate_zip_shapefile_bundle(path)
            self.assertEqual(stem, 'mpangokinaa1 mwande')
        finally:
            os.unlink(path)

    def test_extract_preserves_matching_companion_files(self):
        data = _make_zip({
            'folder/Mpangokinaa1 mwande.shp': b'shp-bytes',
            'folder/Mpangokinaa1 mwande.shx': b'shx-bytes',
            'folder/Mpangokinaa1 mwande.dbf': b'dbf-bytes',
        })
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = os.path.join(tmp, 'upload.zip')
            with open(zip_path, 'wb') as f:
                f.write(data)
            dest = os.path.join(tmp, 'out')
            shp = _extract_shapefile_from_zip(zip_path, dest)
            self.assertTrue(os.path.isfile(shp))
            base = os.path.basename(shp)
            self.assertTrue(base.endswith('.shp'))
            stem = base[:-4]
            for ext in ('.shx', '.dbf'):
                self.assertTrue(os.path.isfile(os.path.join(dest, stem + ext)))


@override_settings(BASE_DIR=Path(tempfile.gettempdir()) / 'tanzania_gis_test')
class ShapefileUploadParseTests(SimpleTestCase):
    def test_rejects_loose_shp_without_companions(self):
        shp = SimpleUploadedFile('Mpangokinaa1 mwande.shp', b'fake-shp')
        with self.assertRaises(ValueError) as ctx:
            parse_spatial_upload_files([shp])
        msg = str(ctx.exception)
        self.assertIn('haijakamilika', msg.lower())

    def test_accepts_loose_shp_shx_dbf(self):
        shp = SimpleUploadedFile('Mpangokinaa1 mwande.shp', b'fake')
        shx = SimpleUploadedFile('Mpangokinaa1 mwande.shx', b'fake')
        dbf = SimpleUploadedFile('Mpangokinaa1 mwande.dbf', b'fake')
        sample_fc = {
            'type': 'FeatureCollection',
            'features': [{'type': 'Feature', 'geometry': None, 'properties': {}}],
        }
        with mock.patch(
            'dashboard.shapefile_upload_service._convert_to_geojson',
            return_value=sample_fc,
        ):
            result = parse_spatial_upload_files([shp, shx, dbf])
        self.assertEqual(result['type'], 'FeatureCollection')

    def test_rejects_incomplete_zip(self):
        zdata = _make_zip({'layer.shp': b'only-shp'})
        zfile = SimpleUploadedFile('parcels.zip', zdata)
        with self.assertRaises(ValueError) as ctx:
            parse_spatial_upload_files([zfile])
        self.assertIn(INCOMPLETE_SHAPEFILE_MSG.split('{')[0], str(ctx.exception))


class ImportMetaTests(SimpleTestCase):
    def test_partial_success_message_swahili(self):
        meta = _build_import_meta(
            source_layer='igawisenga',
            source_srid=32736,
            source_feature_count=100,
            imported_feature_count=95,
            skipped_features=[{'fid': 1, 'reason': 'jiometri batili'}],
        )
        self.assertTrue(meta['partial_success'])
        self.assertIn('95', meta['message_sw'])
        self.assertIn('100', meta['message_sw'])
        self.assertIn('5', meta['message_sw'])


@override_settings(BASE_DIR=Path(tempfile.gettempdir()) / 'tanzania_gis_test')
class ShapefileConversionIntegrationTests(SimpleTestCase):
    """Jaribu badiliko halisi ya shapefile (ikiwa ipo kwenye diski)."""

    IGAWISENGA_SHP = Path(r'D:/SITE/MADABA/mawesu/Mpango kinaa/igawisenga.shp')

    def test_igawisenga_converts_with_import_meta(self):
        if not self.IGAWISENGA_SHP.is_file():
            self.skipTest('igawisenga.shp haipatikani kwenye D:/SITE')

        from osgeo import gdal
        from dashboard.shapefile_upload_service import _convert_to_geojson, _to_gdal_path

        gdal.UseExceptions()
        fc = _convert_to_geojson(_to_gdal_path(str(self.IGAWISENGA_SHP)), gdal)
        self.assertEqual(fc['type'], 'FeatureCollection')
        self.assertGreater(len(fc['features']), 0)
        meta = fc.get('import_meta', {})
        self.assertEqual(meta.get('source_layer'), 'igawisenga')
        self.assertIn(meta.get('source_srid'), (32736, 4326))

    def test_vector_translate_failure_falls_back_per_feature(self):
        shp = SimpleUploadedFile('igawisenga.shp', b'fake')
        shx = SimpleUploadedFile('igawisenga.shx', b'fake')
        dbf = SimpleUploadedFile('igawisenga.dbf', b'fake')
        sample_fc = {
            'type': 'FeatureCollection',
            'features': [{'type': 'Feature', 'geometry': None, 'properties': {'id': 1}}],
            'import_meta': {
                'source_layer': 'igawisenga',
                'skipped_count': 1,
                'message_sw': PARTIAL_SUCCESS_MSG.format(
                    imported=1, total=2, skipped=1,
                ),
            },
        }
        with mock.patch(
            'dashboard.shapefile_upload_service._try_vector_translate',
            return_value=None,
        ), mock.patch(
            'dashboard.shapefile_upload_service._convert_features_individually',
            return_value=sample_fc,
        ):
            result = parse_spatial_upload_files([shp, shx, dbf])
        self.assertEqual(result['import_meta']['source_layer'], 'igawisenga')
        self.assertIn('Imepakiwa sehemu', result['import_meta']['message_sw'])
