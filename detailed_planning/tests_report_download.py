"""Smoke tests — ripoti download kama faili (si JSON) kwa majukumu yasiyo ya superuser."""
from __future__ import annotations

import io
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, SimpleTestCase


def _user(role_name=None, *, superuser=False, authenticated=True):
    role = SimpleNamespace(name=role_name) if role_name else None
    return SimpleNamespace(
        is_authenticated=authenticated,
        is_superuser=superuser,
        role=role,
    )


class ReportDownloadUnitTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.pdf_bytes = b'%PDF-1.4 smoke-report'
        self.report = SimpleNamespace(
            id='11111111-1111-1111-1111-111111111111',
            original_filename='mpango.pdf',
            file_path='planning_reports/Ruvuma/mpango.pdf',
            file_format='pdf',
        )
        self.docx = SimpleNamespace(
            id='22222222-2222-2222-2222-222222222222',
            original_filename='minutes.docx',
            file_path='meeting_minutes/minutes.docx',
            file_format='docx',
        )

    def _open_bytes(self, data: bytes):
        return io.BytesIO(data)

    def test_anonymous_gets_json_401(self):
        from detailed_planning.views import api_report_download

        req = self.factory.get(f'/api/planning/reports/{self.report.id}/download/')
        req.user = AnonymousUser()
        with patch('detailed_planning.views.PlanningReport.objects.get', return_value=self.report):
            resp = api_report_download(req, self.report.id)
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp['Content-Type'].split(';')[0], 'application/json')
        self.assertIn('Ingia', resp.content.decode('utf-8'))

    def test_user_without_role_forbidden(self):
        from detailed_planning.views import api_report_download

        req = self.factory.get(f'/api/planning/reports/{self.report.id}/download/')
        req.user = _user(None)
        resp = api_report_download(req, self.report.id)
        self.assertEqual(resp.status_code, 403)
        self.assertIn('forbidden', resp.content.decode('utf-8'))

    def test_gis_officer_gets_pdf_attachment(self):
        from detailed_planning.views import api_report_download

        req = self.factory.get(f'/api/planning/reports/{self.report.id}/download/')
        req.user = _user('gis_officer')
        storage = MagicMock()
        storage.exists.return_value = True
        storage.open.return_value = self._open_bytes(self.pdf_bytes)
        with patch('detailed_planning.views.PlanningReport.objects.get', return_value=self.report), \
             patch('detailed_planning.views.default_storage', storage):
            resp = api_report_download(req, self.report.id)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('attachment', (resp.get('Content-Disposition') or '').lower())
        self.assertIn('pdf', (resp.get('Content-Type') or '').lower())
        self.assertNotIn('application/json', (resp.get('Content-Type') or '').lower())
        body = b''.join(resp.streaming_content)
        self.assertEqual(body, self.pdf_bytes)

    def test_data_management_officer_quarter_report(self):
        from detailed_planning.views import api_quarter_report_download

        req = self.factory.get(f'/api/planning/quarter-reports/{self.report.id}/download/')
        req.user = _user('data_management_officer')
        storage = MagicMock()
        storage.exists.return_value = True
        storage.open.return_value = self._open_bytes(self.pdf_bytes)
        with patch('detailed_planning.views.QuarterReport.objects.get', return_value=self.report), \
             patch('detailed_planning.views.default_storage', storage):
            resp = api_quarter_report_download(req, self.report.id)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('attachment', (resp.get('Content-Disposition') or '').lower())
        self.assertNotIn('application/json', (resp.get('Content-Type') or '').lower())

    def test_gis_officer_meeting_minutes_docx(self):
        from detailed_planning.views import api_meeting_minutes_download

        req = self.factory.get(f'/api/planning/meeting-minutes/{self.docx.id}/download/')
        req.user = _user('gis_officer')
        storage = MagicMock()
        storage.exists.return_value = True
        storage.open.return_value = self._open_bytes(b'PK\x03\x04fake')
        with patch('detailed_planning.views.MeetingMinutes.objects.get', return_value=self.docx), \
             patch('detailed_planning.views.default_storage', storage):
            resp = api_meeting_minutes_download(req, self.docx.id)
        self.assertEqual(resp.status_code, 200)
        ct = (resp.get('Content-Type') or '').lower()
        self.assertIn('openxmlformats', ct)
        self.assertIn('attachment', (resp.get('Content-Disposition') or '').lower())

    def test_missing_file_swahili_json(self):
        from detailed_planning.views import api_report_download

        req = self.factory.get(f'/api/planning/reports/{self.report.id}/download/')
        req.user = _user('land_dispute_officer')
        storage = MagicMock()
        storage.exists.return_value = False
        with patch('detailed_planning.views.PlanningReport.objects.get', return_value=self.report), \
             patch('detailed_planning.views.default_storage', storage), \
             patch('detailed_planning.views.os.path.isfile', return_value=False):
            resp = api_report_download(req, self.report.id)
        self.assertEqual(resp.status_code, 404)
        text = resp.content.decode('utf-8')
        self.assertIn('Faili', text)
        self.assertIn('file_missing', text)
