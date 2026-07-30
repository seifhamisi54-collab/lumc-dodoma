"""Passcode gate — System Administration & Organizations (Django Admin)."""
from __future__ import annotations

import logging

from django.contrib.auth.hashers import check_password, make_password
from django.db import connection, transaction
from django.db.utils import OperationalError, ProgrammingError

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


def _rollback_quietly() -> None:
    """After ProgrammingError/OperationalError Postgres aborts the txn until rollback."""
    try:
        connection.rollback()
    except Exception:
        pass


def ensure_system_setting_table() -> None:
    """Create/move boundaries.dashboard_systemsetting if missing (Neon pooler / partial migrate)."""
    with connection.cursor() as cur:
        cur.execute('CREATE SCHEMA IF NOT EXISTS boundaries')
        cur.execute(
            """
            SELECT table_schema
            FROM information_schema.tables
            WHERE table_name = 'dashboard_systemsetting'
              AND table_schema IN ('public', 'boundaries')
            """
        )
        schemas = {row[0] for row in cur.fetchall()}
        if 'boundaries' not in schemas and 'public' in schemas:
            cur.execute('ALTER TABLE public.dashboard_systemsetting SET SCHEMA boundaries')
            schemas.add('boundaries')
        if 'boundaries' not in schemas:
            cur.execute(
                """
                CREATE TABLE boundaries.dashboard_systemsetting (
                    id BIGSERIAL PRIMARY KEY,
                    key VARCHAR(100) NOT NULL UNIQUE,
                    value TEXT NOT NULL DEFAULT '',
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_by_id INTEGER NULL
                )
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS dashboard_systemsetting_key_idx
                ON boundaries.dashboard_systemsetting (key)
                """
            )


def get_passcode_hash() -> str:
    """Soma hash ya passcode. Missing table / DB glitch → treat as not configured."""
    try:
        row = SystemSetting.objects.filter(key=PASSCODE_SETTING_KEY).first()
        return (row.value if row else '') or ''
    except (ProgrammingError, OperationalError) as exc:
        logger.warning('SystemSetting unavailable for passcode gate: %s', exc)
        _rollback_quietly()
        return ''


def passcode_is_configured() -> bool:
    return bool(get_passcode_hash())


def set_passcode(raw_passcode: str, user=None) -> None:
    digest = make_password((raw_passcode or '').strip())
    updated_by = user if getattr(user, 'is_authenticated', False) else None
    defaults = {'value': digest, 'updated_by': updated_by}

    try:
        with transaction.atomic():
            SystemSetting.objects.update_or_create(
                key=PASSCODE_SETTING_KEY,
                defaults=defaults,
            )
            return
    except (ProgrammingError, OperationalError) as exc:
        logger.warning('SystemSetting write failed, ensuring table: %s', exc)
        _rollback_quietly()

    ensure_system_setting_table()
    with transaction.atomic():
        SystemSetting.objects.update_or_create(
            key=PASSCODE_SETTING_KEY,
            defaults=defaults,
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
