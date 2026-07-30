"""CSRF failure → JSON for API / XHR (avoids HTML → response.json() crash)."""
from __future__ import annotations

from django.http import HttpResponseForbidden, JsonResponse


def csrf_failure(request, reason=''):
    path = request.path or ''
    wants_json = (
        path.startswith('/api/')
        or '/api/' in path
        or 'application/json' in (request.headers.get('Content-Type') or '')
        or 'application/json' in (request.headers.get('Accept') or '')
        or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or request.headers.get('X-CSRFToken') is not None
    )
    if wants_json:
        return JsonResponse(
            {
                'success': False,
                'message': 'CSRF token haipo au si sahihi. Pakia upya ukurasa kisha jaribu tena.',
                'code': 'csrf_failure',
                'reason': str(reason or ''),
            },
            status=403,
        )
    return HttpResponseForbidden(
        'CSRF verification failed. Pakia upya ukurasa.',
        content_type='text/plain; charset=utf-8',
    )
