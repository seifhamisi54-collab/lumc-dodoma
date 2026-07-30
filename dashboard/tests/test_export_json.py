"""Smoke tests for GIS download / export (JSON + planning fallback)."""
import json
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings


class ExportServiceUnitTests(SimpleTestCase):
    def test_normalize_json_alias(self):
        from dashboard.export_service import _normalize_fmt
        self.assertEqual(_normalize_fmt('json'), 'geojson')
        self.assertEqual(_normalize_fmt('JSON'), 'geojson')
        self.assertEqual(_normalize_fmt('geojson'), 'geojson')

    def test_json_download_response_headers(self):
        from dashboard.export_service import _json_download_response
        fc = {'type': 'FeatureCollection', 'features': []}
        resp = _json_download_response(fc, 'district_boundaries_Ruvuma', 'json')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('application/json', resp['Content-Type'])
        self.assertIn('attachment', resp['Content-Disposition'])
        self.assertIn('.json', resp['Content-Disposition'])
        body = json.loads(resp.content.decode('utf-8'))
        self.assertEqual(body['type'], 'FeatureCollection')

    def test_geojson_download_bypasses_gdal(self):
        from dashboard.export_service import export_data
        fake_fc = {
            'type': 'FeatureCollection',
            'features': [{
                'type': 'Feature',
                'geometry': {'type': 'Point', 'coordinates': [35.0, -10.0]},
                'properties': {'name': 'Test'},
            }],
        }
        with patch('dashboard.export_service._spatial_geojson', return_value=fake_fc):
            resp = export_data('district_boundaries', 'geojson', region='Ruvuma')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('geo+json', resp['Content-Type'])
        self.assertIn('attachment', resp['Content-Disposition'])
        body = json.loads(resp.content.decode('utf-8'))
        self.assertEqual(len(body['features']), 1)

    def test_json_format_accepted(self):
        from dashboard.export_service import export_data
        with patch('dashboard.export_service._spatial_geojson', return_value={
            'type': 'FeatureCollection', 'features': []
        }):
            resp = export_data('district_boundaries', 'json', region='Ruvuma')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('application/json', resp['Content-Type'])
        self.assertIn('.json', resp['Content-Disposition'])


@override_settings(ROOT_URLCONF='tanzania_gis.urls')
class ExportApiSmokeTests(SimpleTestCase):
    """URL-level smoke without requiring PostGIS fixtures."""

    def test_export_json_route_returns_attachment(self):
        from django.test import Client
        from dashboard.export_service import _empty_fc
        client = Client()
        with patch('dashboard.export_service._spatial_geojson', return_value=_empty_fc()):
            resp = client.get('/api/export/district_boundaries/json/?region=Ruvuma')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('attachment', resp.get('Content-Disposition', ''))
        self.assertIn('json', (resp.get('Content-Type') or '').lower())
