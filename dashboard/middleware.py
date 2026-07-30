"""Middleware — zuia System Admin / Organizations bila passcode."""
from __future__ import annotations

import logging
from urllib.parse import quote

from django.conf import settings
from django.db import connections
from django.http import JsonResponse
from django.shortcuts import redirect

from accounts.permissions import can_access_admin_panel
from dashboard.admin_gate import is_unlocked, passcode_is_configured, path_is_exempt, path_is_protected

logger = logging.getLogger(__name__)


class EnsureSearchPathMiddleware:
    """Re-apply search_path every request (Neon/PgBouncer transaction pool resets it)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        paths = getattr(settings, 'DATABASE_SEARCH_PATHS', {}) or {}
        for alias, path in paths.items():
            if not path or alias not in connections.databases:
                continue
            try:
                with connections[alias].cursor() as cursor:
                    cursor.execute(f'SET search_path TO {path}')
            except Exception as exc:
                logger.warning('search_path not set on request (%s): %s', alias, exc)
        return self.get_response(request)


class AdminPasscodeMiddleware:
    """Inahitaji passcode session kwa /system-admin/ na /admin/."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path or '/'

        if not path_is_protected(path) or path_is_exempt(path):
            return self.get_response(request)

        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated:
            return self.get_response(request)

        configured = passcode_is_configured()
        unlocked = is_unlocked(request)

        # Passcode haijawekwa: elekeza kuweka passcode kwanza (isiingie moja kwa moja)
        if not configured:
            if can_access_admin_panel(user):
                if path.startswith('/api/system-admin/'):
                    return self.get_response(request)
                if path.startswith('/admin/') or path.rstrip('/') == '/system-admin':
                    nxt = quote(path if path.startswith('/admin') else '/system-admin/')
                    return redirect(f'/system-admin/unlock/?next={nxt}&setup=1')
                return self.get_response(request)
            return self._deny(request, path)

        if unlocked:
            return self.get_response(request)

        return self._deny(request, path)

    def _deny(self, request, path: str):
        wants_json = (
            path.startswith('/api/')
            or 'application/json' in (request.headers.get('Accept') or '')
        )
        if wants_json:
            return JsonResponse({
                'error': 'Passcode inahitajika kwa System Administration / Organizations',
                'code': 'admin_passcode_required',
                'unlock_url': '/system-admin/unlock/',
            }, status=403)
        next_url = quote(request.get_full_path())
        return redirect(f'/system-admin/unlock/?next={next_url}')
