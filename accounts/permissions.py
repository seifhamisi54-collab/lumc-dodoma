"""Rangi za watumiaji — GIS Portal (Core System User Roles)."""
from __future__ import annotations

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

# Core System User Roles (business roles)
ROLE_SECTION_HEAD = 'section_head'
ROLE_GIS_OFFICER = 'gis_officer'
ROLE_DATA_MANAGEMENT_OFFICER = 'data_management_officer'
ROLE_LAND_DISPUTE_OFFICER = 'land_dispute_officer'

# Legacy aliases kept for any leftover string checks during transition
ROLE_ADMIN = ROLE_SECTION_HEAD
ROLE_MANAGER = ROLE_DATA_MANAGEMENT_OFFICER
ROLE_OFFICER = ROLE_GIS_OFFICER
ROLE_VIEWER = ROLE_GIS_OFFICER

ROLE_LABELS = {
    ROLE_SECTION_HEAD: 'Section Head',
    ROLE_GIS_OFFICER: 'GIS Officer',
    ROLE_DATA_MANAGEMENT_OFFICER: 'Data Management Officer',
    ROLE_LAND_DISPUTE_OFFICER: 'Land Dispute Officer',
}

# Ruhusa kwa kila jukumu (LUMC)
ROLE_PERMISSIONS = {
    ROLE_SECTION_HEAD: {
        'view_map', 'upload', 'download', 'manage_users',
        'admin_panel', 'all_regions', 'approve',
    },
    ROLE_DATA_MANAGEMENT_OFFICER: {
        'view_map', 'upload', 'download', 'region_scope', 'approve',
    },
    ROLE_GIS_OFFICER: {
        'view_map', 'upload', 'download', 'district_scope',
    },
    ROLE_LAND_DISPUTE_OFFICER: {
        'view_map', 'upload', 'download', 'district_scope',
    },
}

# CRUD matrix kwa UI ya System Administration
CRUD_ACTIONS = ('create', 'read', 'update', 'delete', 'export', 'approve')

ROLE_CRUD_MATRIX = {
    ROLE_SECTION_HEAD: {'create', 'read', 'update', 'delete', 'export', 'approve'},
    ROLE_DATA_MANAGEMENT_OFFICER: {'create', 'read', 'update', 'export', 'approve'},
    ROLE_GIS_OFFICER: {'create', 'read', 'update', 'export'},
    ROLE_LAND_DISPUTE_OFFICER: {'create', 'read', 'update', 'export'},
}

# Old role code → new role code (data migration / auto-map)
LEGACY_ROLE_MAP = {
    'admin': ROLE_SECTION_HEAD,
    'manager': ROLE_DATA_MANAGEMENT_OFFICER,
    'officer': ROLE_GIS_OFFICER,
    'viewer': ROLE_GIS_OFFICER,
}


def normalize_role_name(name: str | None) -> str | None:
    """Map legacy role codes to current Core System roles."""
    if not name:
        return None
    if name in ROLE_LABELS:
        return name
    return LEGACY_ROLE_MAP.get(name, ROLE_GIS_OFFICER)


def get_role_name(user) -> str | None:
    if not user or not getattr(user, 'is_authenticated', False):
        return None
    if user.is_superuser:
        return ROLE_SECTION_HEAD
    role = getattr(user, 'role', None)
    return normalize_role_name(role.name if role else None)


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
            allowed = {normalize_role_name(r) or r for r in allowed_roles}
            if role not in allowed and not request.user.is_superuser:
                raise PermissionDenied('Huna ruhusa ya kufanya kitendo hiki.')
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator
