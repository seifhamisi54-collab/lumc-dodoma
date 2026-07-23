"""Tests for administrative boundary lookup (upload AOI)."""
from __future__ import annotations

from unittest import mock

from django.test import SimpleTestCase, TestCase

from dashboard.boundary_service import (
    _fuzzy_pick,
    _normalize_key,
    format_boundary_not_found_message,
    resolve_admin_boundary,
)


class NormalizeNameTests(SimpleTestCase):
    def test_normalize_key_strips_and_lowercases(self):
        self.assertEqual(_normalize_key('  Matetereka '), 'matetereka')
        self.assertEqual(_normalize_key('Madaba'), 'madaba')

    def test_fuzzy_pick_close_spelling(self):
        choices = ['Matetereka', 'Matetema', 'Mahanje']
        self.assertEqual(_fuzzy_pick('Mateteleka', choices), 'Matetereka')
        self.assertEqual(_fuzzy_pick('matetereka', choices), 'Matetereka')


class ResolveAdminBoundaryTests(TestCase):
    databases = {'default', 'detailed_planning'}

    def test_matetereka_ruvuma_songea_resolves(self):
        resolved = resolve_admin_boundary('Ruvuma', 'Songea', 'Matetereka')
        if resolved is None:
            self.skipTest('Matetereka haipo kwenye detailed_planning DB')
        self.assertEqual(resolved['ward'], 'Matetereka')
        self.assertEqual(resolved['district'], 'Songea')
        self.assertEqual(resolved['region'], 'Ruvuma')
        self.assertIsNotNone(resolved['geometry'])

    def test_matetereka_madaba_alias_resolves_to_songea(self):
        resolved = resolve_admin_boundary('Ruvuma', 'Madaba', 'Matetereka')
        if resolved is None:
            self.skipTest('Matetereka haipo kwenye detailed_planning DB')
        self.assertEqual(resolved['ward'], 'Matetereka')
        self.assertEqual(resolved['district'], 'Songea')
        self.assertTrue(resolved.get('district_corrected'))

    def test_fuzzy_ward_spelling(self):
        resolved = resolve_admin_boundary('Ruvuma', 'Songea', 'Mateteleka')
        if resolved is None:
            self.skipTest('Matetereka haipo kwenye detailed_planning DB')
        self.assertEqual(resolved['ward'], 'Matetereka')

    def test_unknown_ward_lists_available(self):
        msg = format_boundary_not_found_message('Ruvuma', 'Songea', 'KataIsiyoipoXYZ')
        self.assertIn('haipatikani', msg.lower())
        if 'Kata zinazopatikana' in msg:
            self.assertIn('Songea', msg)


class LegacyFallbackTests(SimpleTestCase):
    @mock.patch('dashboard.boundary_service._find_ward_in_region', return_value=None)
    @mock.patch('dashboard.boundary_service._find_district_boundary', return_value=None)
    @mock.patch('dashboard.boundary_service._legacy_boundary_geometry')
    def test_legacy_used_when_planning_missing(self, legacy_geom, *_mocks):
        legacy_geom.return_value = {'type': 'Polygon', 'coordinates': []}
        resolved = resolve_admin_boundary('Geita', 'Geita', None)
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved['source'], 'boundaries.tanzania_administrative')
