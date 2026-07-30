"""Passcode gate — System Administration & Organizations (Django Admin)."""
from __future__ import annotations

import logging

from django.contrib.auth.hashers import check_password, make_password
from django.db import OperationalError, ProgrammingError

from dashboard.models import SystemSetting

logger = logging.getLogger(__name__)

SESSION_UNLOCK_KEY = 'lumc_admin_unlocked'
PASSCODE_SETTING_KEY = 'admin_area_passcode'

PROTECTED_PREFIXES = (
    '/system-admin/',
    '/api/system-admin/',
    '/admin/',
)

EXEMPT_PREFIXES = (
    '/system-admin/unlock/',
    '/api/system-admin/unlock/',
    '/api/system-admin/gate-status/',
    '/api/system-admin/passcode/',
    '/api/system-admin/passcode/reset/',
    '/api/system-admin/lock/',
    '/admin/login/',
    '/admin/logout/',
    '/admin/jsi18n/',
)


def get_passcode_hash() -> str:
    """Soma hash ya passcode. Missing table / DB glitch → treat as not configured."""
    try:
        row = SystemSetting.objects.filter(key=PASSCODE_SETTING_KEY).first()
        return (row.value if row else '') or ''
    except (ProgrammingError, OperationalError) as exc:
        logger.warning('SystemSetting unavailable for passcode gate: %s', exc)
        return ''


def passcode_is_configured() -> bool:
    return bool(get_passcode_hash())


def set_passcode(raw_passcode: str, user=None) -> None:
    digest = make_password((raw_passcode or '').strip())
    SystemSetting.objects.update_or_create(
        key=PASSCODE_SETTING_KEY,
        defaults={'value': digest, 'updated_by': user if getattr(user, 'is_authenticated', False) else None},
    )


def verify_passcode(raw_passcode: str) -> bool:
    stored = get_passcode_hash()
    if not stored:
        return False
    return check_password((raw_passcode or '').strip(), stored)


def is_unlocked(request) -> bool:
    return bool(request.session.get(SESSION_UNLOCK_KEY))


def unlock_session(request) -> None:
    request.session[SESSION_UNLOCK_KEY] = True
    request.session.modified = True


def lock_session(request) -> None:
    if SESSION_UNLOCK_KEY in request.session:
        del request.session[SESSION_UNLOCK_KEY]
        request.session.modified = True


def path_is_exempt(path: str) -> bool:
    return any(path.startswith(p) for p in EXEMPT_PREFIXES)


def path_is_protected(path: str) -> bool:
    if path_is_exempt(path):
        return False
    return any(path.startswith(p) for p in PROTECTED_PREFIXES)
