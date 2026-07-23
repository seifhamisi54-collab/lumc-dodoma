"""Tests for planning shapefile and report delete APIs."""
from __future__ import annotations

import os
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from detailed_planning.models import PlanningParcel, PlanningReport, PlanningShapefile
from detailed_planning.services import save_planning_report_file

User = get_user_model()


class PlanningDeleteApiTests(TestCase):
    databases = {'default', 'detailed_planning'}

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser(
            username='delete_admin',
            email='admin@test.local',
            password='testpass123',
        )
        self.viewer = User.objects.create_user(
            username='delete_viewer',
            email='viewer@test.local',
            password='testpass123',
        )

    def test_delete_report_requires_login(self):
        report = save_planning_report_file(
            SimpleUploadedFile('test.pdf', b'%PDF-1.4 fake'),
            report_type='plan_summary',
            region='Ruvuma',
            district='Songea',
        )
        resp = self.client.delete(f'/api/planning/reports/{report.id}/')
        self.assertEqual(resp.status_code, 302)

    def test_delete_report_success(self):
        report = save_planning_report_file(
            SimpleUploadedFile('test.pdf', b'%PDF-1.4 fake'),
            report_type='plan_summary',
            region='Ruvuma',
            district='Songea',
        )
        file_path = report.file_path
        self.client.force_login(self.admin)
        resp = self.client.delete(f'/api/planning/reports/{report.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(PlanningReport.objects.filter(pk=report.id).exists())
        if file_path:
            self.assertFalse(default_storage.exists(file_path))

    def test_delete_report_denied_for_viewer(self):
        report = save_planning_report_file(
            SimpleUploadedFile('test.pdf', b'%PDF-1.4 fake'),
            report_type='plan_summary',
            region='Ruvuma',
        )
        self.client.force_login(self.viewer)
        resp = self.client.delete(f'/api/planning/reports/{report.id}/')
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(PlanningReport.objects.filter(pk=report.id).exists())

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_delete_stored_shapefile(self):
        rel_path = default_storage.save(
            'planning_shapefiles/test/test.zip',
            SimpleUploadedFile('parcels.zip', b'zip-bytes'),
        )
        shapefile = PlanningShapefile.objects.create(
            title='Test parcels',
            boundary_level='parcel',
            region_name='Ruvuma',
            district_name='Songea',
            original_filename='parcels.zip',
            stored_filename='test.zip',
            file_path=rel_path,
        )
        self.client.force_login(self.admin)
        resp = self.client.delete(f'/api/planning/shapefiles/{shapefile.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(PlanningShapefile.objects.filter(pk=shapefile.id).exists())
        self.assertFalse(default_storage.exists(rel_path))

    def test_delete_parcels_by_shapefile_name(self):
        PlanningParcel.objects.create(
            parcel_number='DEL-001',
            region_name='Ruvuma',
            district_name='Songea',
            ward_name='TestWard',
            village_name='TestVillage',
            shapefile_name='delete_me.zip',
        )
        self.client.force_login(self.admin)
        resp = self.client.delete(
            '/api/planning/shapefiles/parcel/',
            data='{"shapefile_name": "delete_me.zip", "region": "Ruvuma", "district": "Songea"}',
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['deleted'], 1)
        self.assertFalse(
            PlanningParcel.objects.filter(shapefile_name='delete_me.zip').exists()
        )

    def test_list_shapefiles_includes_parcel_imports(self):
        PlanningParcel.objects.create(
            parcel_number='LIST-001',
            region_name='Ruvuma',
            district_name='Songea',
            ward_name='TestWard',
            village_name='TestVillage',
            shapefile_name='listed.zip',
        )
        resp = self.client.get(
            '/api/planning/shapefiles/',
            {'region': 'Ruvuma', 'district': 'Songea'},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        names = {item['original_filename'] for item in data['shapefiles']}
        self.assertIn('listed.zip', names)

    def test_list_parcel_shapefiles_only(self):
        PlanningParcel.objects.create(
            parcel_number='MW-001',
            region_name='Ruvuma',
            district_name='Songea',
            ward_name='Mwande',
            village_name='Mwande',
            shapefile_name='Mpangokinaa1_mwande.shp',
        )
        PlanningParcel.objects.create(
            parcel_number='IG-001',
            region_name='Ruvuma',
            district_name='Songea',
            ward_name='Igawisenga',
            village_name='Igawisenga',
            shapefile_name='igawisenga.shp',
        )
        PlanningParcel.objects.create(
            parcel_number='IG-002',
            region_name='Ruvuma',
            district_name='Songea',
            ward_name='Igawisenga',
            village_name='Igawisenga',
            shapefile_name='igawisenga.shp',
        )
        resp = self.client.get(
            '/api/planning/shapefiles/parcels/',
            {'region': 'Ruvuma', 'district': 'Songea'},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['data_source'], 'planning_parcels')
        by_name = {item['shapefile_name']: item['parcel_count'] for item in data['shapefiles']}
        self.assertEqual(by_name['Mpangokinaa1_mwande.shp'], 1)
        self.assertEqual(by_name['igawisenga.shp'], 2)

    def test_delete_igawisenga_parcels_keeps_mwande(self):
        PlanningParcel.objects.create(
            parcel_number='MW-001',
            region_name='Ruvuma',
            district_name='Songea',
            shapefile_name='Mpangokinaa1_mwande.shp',
        )
        PlanningParcel.objects.create(
            parcel_number='IG-001',
            region_name='Ruvuma',
            district_name='Songea',
            shapefile_name='igawisenga.shp',
        )
        PlanningParcel.objects.create(
            parcel_number='IG-002',
            region_name='Ruvuma',
            district_name='Songea',
            shapefile_name='igawisenga.shp',
        )
        self.client.force_login(self.admin)
        resp = self.client.delete(
            '/api/planning/shapefiles/parcel/',
            data='{"shapefile_name": "igawisenga.shp", "region": "Ruvuma", "district": "Songea"}',
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['deleted'], 2)
        self.assertFalse(PlanningParcel.objects.filter(shapefile_name='igawisenga.shp').exists())
        self.assertTrue(PlanningParcel.objects.filter(shapefile_name='Mpangokinaa1_mwande.shp').exists())

    def test_delete_mwande_parcels_keeps_igawisenga(self):
        PlanningParcel.objects.create(
            parcel_number='MW-001',
            region_name='Ruvuma',
            district_name='Songea',
            shapefile_name='Mpangokinaa1_mwande.shp',
        )
        PlanningParcel.objects.create(
            parcel_number='IG-001',
            region_name='Ruvuma',
            district_name='Songea',
            shapefile_name='igawisenga.shp',
        )
        self.client.force_login(self.admin)
        resp = self.client.delete(
            '/api/planning/shapefiles/parcel/',
            data='{"shapefile_name": "Mpangokinaa1_mwande.shp", "region": "Ruvuma", "district": "Songea"}',
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['deleted'], 1)
        self.assertFalse(PlanningParcel.objects.filter(shapefile_name='Mpangokinaa1_mwande.shp').exists())
        self.assertTrue(PlanningParcel.objects.filter(shapefile_name='igawisenga.shp').exists())
