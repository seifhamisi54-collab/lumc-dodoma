"""Local smoke: GET unlock + first-time set + verify passcode (JSON).

Usage (from tanzania_gis/):
  .venv_test/Scripts/python.exe scripts/dev/smoke_admin_passcode.py
"""
from __future__ import annotations

import json
import os
import sys

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tanzania_gis.settings')
os.environ.setdefault('DEBUG', '1')
django.setup()

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client

from accounts.models import UserRole
from dashboard.admin_gate import (
    PASSCODE_SETTING_KEY,
    SESSION_UNLOCK_KEY,
    ensure_system_setting_table,
    passcode_is_configured,
    verify_passcode,
)
from dashboard.models import SystemSetting

User = get_user_model()
SMOKE_USER = 'smoke_passcode_admin'
SMOKE_CODE = 'smoke-pass-2026'


def main() -> int:
    ensure_system_setting_table()
    role, _ = UserRole.objects.get_or_create(name='admin')
    user, created = User.objects.get_or_create(
        username=SMOKE_USER,
        defaults={
            'is_staff': True,
            'is_superuser': True,
            'role': role,
        },
    )
    if created or not user.check_password('AdminPass123!'):
        user.set_password('AdminPass123!')
        user.is_staff = True
        user.is_superuser = True
        user.role = role
        user.save()

    # Isolate smoke from any existing production-like passcode in local DB
    SystemSetting.objects.filter(key=PASSCODE_SETTING_KEY).delete()

    client = Client(enforce_csrf_checks=True)
    client.force_login(user)

    print('1) GET /system-admin/unlock/?setup=1')
    resp = client.get('/system-admin/unlock/?setup=1')
    assert resp.status_code == 200, resp.status_code
    assert b'setupForm' in resp.content, 'expected first-time setup form'
    token = client.cookies['csrftoken'].value
    print('   OK — setup page + CSRF')

    print('2) POST /api/system-admin/passcode/ (first-time set)')
    resp = client.post(
        '/api/system-admin/passcode/',
        data=json.dumps({'passcode': SMOKE_CODE}),
        content_type='application/json',
        HTTP_X_CSRFTOKEN=token,
        HTTP_ACCEPT='application/json',
    )
    ctype = resp['Content-Type']
    assert 'application/json' in ctype, ctype
    body = resp.json()
    assert resp.status_code == 200, body
    assert body.get('status') == 'success', body
    assert passcode_is_configured()
    assert verify_passcode(SMOKE_CODE)
    assert client.session.get(SESSION_UNLOCK_KEY) is True
    print('   OK — JSON success, session unlocked')

    # Lock and verify
    session = client.session
    session.pop(SESSION_UNLOCK_KEY, None)
    session.save()

    print('3) POST /api/system-admin/unlock/ (verify)')
    resp = client.post(
        '/api/system-admin/unlock/',
        data=json.dumps({'passcode': SMOKE_CODE, 'next': '/system-admin/'}),
        content_type='application/json',
        HTTP_X_CSRFTOKEN=token,
        HTTP_ACCEPT='application/json',
    )
    body = resp.json()
    assert resp.status_code == 200, body
    assert body.get('unlocked') is True
    assert client.session.get(SESSION_UNLOCK_KEY) is True
    print('   OK — unlock JSON + session')

    print('4) POST wrong passcode -> JSON 403')
    session = client.session
    session.pop(SESSION_UNLOCK_KEY, None)
    session.save()
    resp = client.post(
        '/api/system-admin/unlock/',
        data=json.dumps({'passcode': 'wrong-code'}),
        content_type='application/json',
        HTTP_X_CSRFTOKEN=token,
        HTTP_ACCEPT='application/json',
    )
    body = resp.json()
    assert resp.status_code == 403, body
    assert body.get('code') == 'invalid_passcode'
    print('   OK — invalid_passcode JSON')

    # Cleanup local smoke passcode
    SystemSetting.objects.filter(key=PASSCODE_SETTING_KEY).delete()
    print('DONE — all smoke checks passed')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print('FAIL:', exc, file=sys.stderr)
        raise
