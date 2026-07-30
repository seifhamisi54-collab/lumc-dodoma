"""Smoke tests — admin passcode unlock / first-time set (JSON API)."""
from __future__ import annotations

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, SimpleTestCase, TestCase, override_settings

from accounts.models import UserRole
from dashboard.admin_gate import (
    PASSCODE_SETTING_KEY,
    SESSION_UNLOCK_KEY,
    get_passcode_hash,
    passcode_is_configured,
    set_passcode,
    verify_passcode,
)


User = get_user_model()


@override_settings(
    MIDDLEWARE=[
        'django.middleware.security.SecurityMiddleware',
        'django.contrib.sessions.middleware.SessionMiddleware',
        'django.middleware.common.CommonMiddleware',
        'django.middleware.csrf.CsrfViewMiddleware',
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        'django.contrib.messages.middleware.MessageMiddleware',
    ],
)
class AdminPasscodeApiTests(TestCase):
    """Uses the project DB (Postgres). Skips gracefully if SystemSetting table missing."""

    @classmethod
    def setUpTestData(cls):
        role, _ = UserRole.objects.get_or_create(name='admin')
        cls.admin = User.objects.create_user(
            username='passcode_admin',
            password='AdminPass123!',
            is_staff=True,
            is_superuser=True,
            role=role,
        )

    def setUp(self):
        from dashboard.models import SystemSetting

        SystemSetting.objects.filter(key=PASSCODE_SETTING_KEY).delete()
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.admin)

    def _csrf(self):
        # Unlock page sets CSRF cookie
        resp = self.client.get('/system-admin/unlock/?setup=1')
        self.assertEqual(resp.status_code, 200)
        return self.client.cookies.get('csrftoken').value

    def test_get_unlock_page_setup_mode(self):
        resp = self.client.get('/system-admin/unlock/?setup=1')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Passcode ya Kwanza')
        self.assertContains(resp, 'setupForm')

    def test_set_passcode_first_time_returns_json(self):
        token = self._csrf()
        resp = self.client.post(
            '/api/system-admin/passcode/',
            data=json.dumps({'passcode': 'lumc2026'}),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(resp['Content-Type'].split(';')[0], 'application/json')
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertEqual(body.get('status'), 'success')
        self.assertTrue(body.get('configured'))
        self.assertTrue(passcode_is_configured())
        self.assertTrue(verify_passcode('lumc2026'))
        self.assertTrue(self.client.session.get(SESSION_UNLOCK_KEY))

    def test_verify_passcode_unlock_json(self):
        set_passcode('secret99', user=self.admin)
        # Lock session
        session = self.client.session
        session.pop(SESSION_UNLOCK_KEY, None)
        session.save()

        token = self._csrf()
        resp = self.client.post(
            '/api/system-admin/unlock/',
            data=json.dumps({'passcode': 'secret99', 'next': '/system-admin/'}),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertTrue(body.get('unlocked'))
        self.assertTrue(self.client.session.get(SESSION_UNLOCK_KEY))

    def test_wrong_passcode_json_error(self):
        set_passcode('secret99', user=self.admin)
        token = self._csrf()
        resp = self.client.post(
            '/api/system-admin/unlock/',
            data=json.dumps({'passcode': 'wrong'}),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json().get('code'), 'invalid_passcode')


class AdminPasscodeJsonAlwaysTests(SimpleTestCase):
    """View-level: API must return JSON even when set_passcode raises."""

    def test_passcode_save_error_is_json(self):
        from django.test import RequestFactory
        from dashboard import system_admin_views as views

        factory = RequestFactory()
        request = factory.post(
            '/api/system-admin/passcode/',
            data=json.dumps({'passcode': 'abcd'}),
            content_type='application/json',
        )
        request.user = type('U', (), {
            'is_authenticated': True,
            'is_superuser': True,
            'is_staff': True,
        })()

        with patch('dashboard.system_admin_views._require_admin', return_value=None), \
             patch('dashboard.system_admin_views.passcode_is_configured', return_value=False), \
             patch('dashboard.system_admin_views.set_passcode', side_effect=RuntimeError('db down')):
            resp = views.api_admin_passcode(request)

        self.assertEqual(resp.status_code, 500)
        payload = json.loads(resp.content)
        self.assertIn('Imeshindikana kuhifadhi passcode', payload['error'])
        self.assertEqual(payload['code'], 'passcode_save_error')
