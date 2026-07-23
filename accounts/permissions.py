"""Rangi za watumiaji — GIS Portal."""
from __future__ import annotations

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

ROLE_ADMIN = 'admin'
ROLE_MANAGER = 'manager'
ROLE_OFFICER = 'officer'
ROLE_VIEWER = 'viewer'

ROLE_LABELS = {
    ROLE_ADMIN: 'Administrator',
    ROLE_MANAGER: 'Planner',
    ROLE_OFFICER: 'GIS / Data Entry Officer',
    ROLE_VIEWER: 'Viewer / Guest',
}

# Ruhusa kwa kila jukumu (LUMC)
ROLE_PERMISSIONS = {
    ROLE_ADMIN: {'view_map', 'upload', 'download', 'manage_users', 'admin_panel', 'all_regions', 'approve'},
    ROLE_MANAGER: {'view_map', 'upload', 'download', 'region_scope', 'approve'},
    ROLE_OFFICER: {'view_map', 'upload', 'download', 'district_scope'},
    ROLE_VIEWER: {'view_map'},
}

# CRUD matrix kwa UI ya System Administration
CRUD_ACTIONS = ('create', 'read', 'update', 'delete', 'export', 'approve')

ROLE_CRUD_MATRIX = {
    ROLE_ADMIN: {'create', 'read', 'update', 'delete', 'export', 'approve'},
    ROLE_MANAGER: {'create', 'read', 'update', 'export', 'approve'},
    ROLE_OFFICER: {'create', 'read', 'update', 'export'},
    ROLE_VIEWER: {'read'},
}


def get_role_name(user) -> str | None:
    if not user or not getattr(user, 'is_authenticated', False):
        return None
    if user.is_superuser:
        return ROLE_ADMIN
    role = getattr(user, 'role', None)
    return role.name if role else None


def user_has_permission(user, permission: str) -> bool:
    role = get_role_name(user)
    if not role:
        return False
    return permission in ROLE_PERMISSIONS.get(role, set())


def can_upload(user) -> bool:
    return user_has_permission(user, 'upload')


def can_download(user) -> bool:
    return user_has_permission(user, 'download')


def can_manage_users(user) -> bool:
    return user.is_superuser or user_has_permission(user, 'manage_users')


def can_access_admin_panel(user) -> bool:
    return user.is_superuser or user_has_permission(user, 'admin_panel')


def role_required(*allowed_roles):
    """Dekorator — ruhusu tu majukumu yaliyoorodheshwa."""
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            role = get_role_name(request.user)
            if role not in allowed_roles and not request.user.is_superuser:
                raise PermissionDenied('Huna ruhusa ya kufanya kitendo hiki.')
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator
