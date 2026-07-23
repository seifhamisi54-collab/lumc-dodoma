"""System Administration — Dashboard, Users, Roles, Forms, CCRO, Setups."""
from __future__ import annotations

import json
import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.sessions.models import Session
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods

from accounts.models import UserRole
from accounts.permissions import (
    CRUD_ACTIONS,
    ROLE_CRUD_MATRIX,
    ROLE_LABELS,
    ROLE_PERMISSIONS,
    can_access_admin_panel,
    can_manage_users,
)
from dashboard.admin_gate import (
    is_unlocked,
    lock_session,
    passcode_is_configured,
    set_passcode,
    unlock_session,
    verify_passcode,
)
from dashboard.models import (
    CcroConfigOption,
    Currency,
    Designation,
    ImportLog,
    Locality,
    SystemFormTemplate,
)

User = get_user_model()


def _require_admin(request):
    """Rudisha JsonResponse ikiwa hakuna ruhusa; vinginevyo None."""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Ingia kwanza', 'code': 'login_required'}, status=401)
    if not can_access_admin_panel(request.user):
        return JsonResponse({'error': 'Huna ruhusa ya kusimamia mfumo', 'code': 'forbidden'}, status=403)
    return None


def _require_admin_page(request):
    """Kwa HTML pages — PermissionDenied / redirect login."""
    if not request.user.is_authenticated:
        raise PermissionDenied('Ingia kwanza.')
    if not can_access_admin_panel(request.user):
        raise PermissionDenied('Huna ruhusa ya kusimamia mfumo.')


def _parse_body(request) -> dict:
    try:
        return json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return {}


def _uuid_or_none(value):
    if not value:
        return None
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


def _serialize_currency(obj: Currency) -> dict:
    return {
        'id': str(obj.id),
        'code': obj.code,
        'name': obj.name,
        'symbol': obj.symbol,
        'exchange_rate': float(obj.exchange_rate),
        'is_default': obj.is_default,
        'is_active': obj.is_active,
    }


def _serialize_locality(obj: Locality) -> dict:
    data = {
        'id': str(obj.id),
        'locality_type': obj.locality_type,
        'locality_type_label': obj.get_locality_type_display(),
        'name': obj.name,
        'code': obj.code,
        'parent_id': str(obj.parent_id) if obj.parent_id else None,
        'region_name': obj.region_name,
        'district_name': obj.district_name,
        'ward_name': obj.ward_name,
        'is_active': obj.is_active,
        'notes': obj.notes,
        'has_boundary': False,
        'shapefile_name': None,
        'boundary_id': None,
        'boundary_level': None,
    }
    meta = _locality_boundary_meta(obj)
    if meta:
        data.update(meta)
    return data


def _locality_boundary_meta(obj: Locality) -> dict | None:
    """Tafuta mipaka ya wilaya/kata inayolingana na Locality."""
    if obj.locality_type not in ('district', 'ward'):
        return None
    try:
        from detailed_planning.models import DistrictPlanningBoundary, WardPlanningBoundary
    except Exception:
        return None

    region = (obj.region_name or '').strip()
    if obj.locality_type == 'district':
        district = (obj.district_name or obj.name or '').strip()
        if not district:
            return None
        qs = DistrictPlanningBoundary.objects.filter(district_name__iexact=district)
        if region:
            qs = qs.filter(region_name__iexact=region)
        b = qs.exclude(geom__isnull=True).first() or qs.first()
        if not b:
            return None
        return {
            'has_boundary': bool(b.geom),
            'shapefile_name': b.shapefile_name or None,
            'boundary_id': str(b.id),
            'boundary_level': 'district',
        }

    ward = (obj.ward_name or obj.name or '').strip()
    district = (obj.district_name or '').strip()
    if not ward:
        return None
    qs = WardPlanningBoundary.objects.filter(ward_name__iexact=ward)
    if district:
        qs = qs.filter(district_name__iexact=district)
    if region:
        qs = qs.filter(region_name__iexact=region)
    b = qs.exclude(geom__isnull=True).first() or qs.first()
    if not b:
        return None
    return {
        'has_boundary': bool(b.geom),
        'shapefile_name': b.shapefile_name or None,
        'boundary_id': str(b.id),
        'boundary_level': 'ward',
    }


def _sync_locality_from_names(
    *,
    level: str,
    region: str,
    district: str,
    ward: str | None = None,
) -> Locality | None:
    from dashboard.locality_sync import sync_locality_from_names
    return sync_locality_from_names(level=level, region=region, district=district, ward=ward)

def _serialize_designation(obj: Designation) -> dict:
    return {
        'id': str(obj.id),
        'name': obj.name,
        'code': obj.code,
        'category': obj.category,
        'description': obj.description,
        'is_active': obj.is_active,
        'sort_order': obj.sort_order,
    }


def _serialize_form(obj: SystemFormTemplate) -> dict:
    return {
        'id': str(obj.id),
        'name': obj.name,
        'code': obj.code,
        'category': obj.category,
        'category_label': obj.get_category_display(),
        'description': obj.description,
        'fields_schema': obj.fields_schema or [],
        'version': obj.version,
        'is_active': obj.is_active,
    }


def _serialize_ccro_option(obj: CcroConfigOption) -> dict:
    return {
        'id': str(obj.id),
        'category': obj.category,
        'category_label': obj.get_category_display(),
        'value': obj.value,
        'label': obj.label or obj.value,
        'sort_order': obj.sort_order,
        'is_active': obj.is_active,
    }


@login_required
@ensure_csrf_cookie
@require_GET
def system_admin_page(request):
    """Ukurasa kamili wa System Administration (LUMC)."""
    _require_admin_page(request)
    # Lazima passcode iwe imethibitishwa kwenye session
    if passcode_is_configured() and not is_unlocked(request):
        from django.shortcuts import redirect as dj_redirect
        return dj_redirect('/system-admin/unlock/?next=/system-admin/&reauth=1')
    if not passcode_is_configured():
        from django.shortcuts import redirect as dj_redirect
        return dj_redirect('/system-admin/unlock/?next=/system-admin/&setup=1')
    return render(request, 'dashboard/system_admin.html', {
        'can_admin': True,
        'can_manage_users': can_manage_users(request.user) or can_access_admin_panel(request.user),
        'system_version': 'LUMC 1.0',
        'passcode_configured': passcode_is_configured(),
        'admin_unlocked': is_unlocked(request),
    })


@login_required
@ensure_csrf_cookie
@require_GET
def admin_unlock_page(request):
    """Ukurasa wa kuingiza / kuweka passcode — kila mara unapoingia SysAdmin/Organizations."""
    next_url = request.GET.get('next') or '/system-admin/'
    if not next_url.startswith('/') or next_url.startswith('//'):
        next_url = '/system-admin/'

    # Kutoka Nyumbani (reauth=1): funga session ili passcode iulizwe tena
    if request.GET.get('reauth') == '1':
        lock_session(request)

    setup = request.GET.get('setup') == '1' or not passcode_is_configured()
    return render(request, 'dashboard/admin_unlock.html', {
        'next_url': next_url,
        'setup_mode': setup,
        'passcode_configured': passcode_is_configured(),
        'can_setup': can_access_admin_panel(request.user),
    })


@require_GET
def api_gate_status(request):
    """Hali ya passcode / unlock (kwa Nyumbani modal)."""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Ingia kwanza'}, status=401)
    return JsonResponse({
        'status': 'success',
        'configured': passcode_is_configured(),
        'unlocked': is_unlocked(request),
        'can_setup': can_access_admin_panel(request.user),
    })


@require_http_methods(['POST'])
def api_admin_unlock(request):
    """Thibitisha passcode na fungua session."""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Ingia kwanza'}, status=401)
    body = _parse_body(request)
    code = (body.get('passcode') or body.get('password') or '').strip()
    if not passcode_is_configured():
        return JsonResponse({
            'error': 'Passcode haijawekwa bado. Weka passcode kwanza.',
            'code': 'passcode_not_set',
        }, status=400)
    if not verify_passcode(code):
        return JsonResponse({'error': 'Passcode si sahihi', 'code': 'invalid_passcode'}, status=403)
    unlock_session(request)
    return JsonResponse({
        'status': 'success',
        'unlocked': True,
        'next': body.get('next') or '/system-admin/',
    })


@require_http_methods(['POST'])
def api_admin_lock(request):
    """Funga tena System Admin / Organizations."""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Ingia kwanza'}, status=401)
    lock_session(request)
    return JsonResponse({'status': 'success', 'unlocked': False})


@require_http_methods(['GET', 'POST'])
def api_admin_passcode(request):
    """Weka au badilisha passcode ya System Administration / Organizations."""
    denied = _require_admin(request)
    if denied:
        return denied

    if request.method == 'GET':
        return JsonResponse({
            'status': 'success',
            'configured': passcode_is_configured(),
            'unlocked': is_unlocked(request),
        })

    body = _parse_body(request)
    new_code = (body.get('passcode') or body.get('new_passcode') or '').strip()
    if len(new_code) < 4:
        return JsonResponse({'error': 'Passcode angalau herufi/namba 4'}, status=400)

    configured = passcode_is_configured()
    if configured:
        if not is_unlocked(request):
            return JsonResponse({'error': 'Fungua kwa passcode ya sasa kwanza'}, status=403)
        current = (body.get('current_passcode') or '').strip()
        # Ikiwa amefungua session, ruhusu kubadilisha; vinginevyo thibitisha ya sasa
        if current and not verify_passcode(current):
            return JsonResponse({'error': 'Passcode ya sasa si sahihi'}, status=403)

    set_passcode(new_code, user=request.user)
    unlock_session(request)
    return JsonResponse({
        'status': 'success',
        'configured': True,
        'message': 'Passcode imewekwa. Itahitajika kila unapoingia System Administration au Organizations.',
    })


@require_http_methods(['POST'])
def api_admin_passcode_reset(request):
    """Weka passcode upya kwa kuthibitisha password ya login (Admin)."""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Ingia kwanza'}, status=401)
    if not can_access_admin_panel(request.user):
        return JsonResponse({'error': 'Huna ruhusa'}, status=403)

    body = _parse_body(request)
    login_password = body.get('login_password') or body.get('password') or ''
    new_code = (body.get('passcode') or body.get('new_passcode') or '').strip()
    if not request.user.check_password(login_password):
        return JsonResponse({'error': 'Password ya login si sahihi'}, status=403)
    if len(new_code) < 4:
        return JsonResponse({'error': 'Passcode angalau herufi/namba 4'}, status=400)

    set_passcode(new_code, user=request.user)
    unlock_session(request)
    return JsonResponse({
        'status': 'success',
        'configured': True,
        'message': 'Passcode mpya imewekwa',
    })


def _serialize_user(user) -> dict:
    role = getattr(user, 'role', None)
    role_name = role.name if role else None
    return {
        'id': user.id,
        'username': user.username,
        'email': user.email or '',
        'first_name': user.first_name or '',
        'last_name': user.last_name or '',
        'phone': getattr(user, 'phone', '') or '',
        'role': role_name,
        'role_label': ROLE_LABELS.get(role_name, role.get_name_display() if role else '—'),
        'is_active': user.is_active,
        'is_superuser': user.is_superuser,
        'assigned_region': user.assigned_region.name if getattr(user, 'assigned_region_id', None) else '',
        'assigned_district': user.assigned_district.name if getattr(user, 'assigned_district_id', None) else '',
        'last_login': user.last_login.isoformat() if user.last_login else None,
        'date_joined': user.date_joined.isoformat() if user.date_joined else None,
    }


@require_GET
def api_admin_overview(request):
    """KPI za System Administration — nature ya LUMC (GIS + Planning + CCRO)."""
    denied = _require_admin(request)
    if denied:
        return denied

    now = timezone.now()
    active_sessions = Session.objects.filter(expire_date__gte=now)
    online_ids = set()
    for session in active_sessions.iterator():
        data = session.get_decoded()
        uid = data.get('_auth_user_id')
        if uid:
            try:
                online_ids.add(int(uid))
            except (TypeError, ValueError):
                pass

    users_total = User.objects.count()
    users_active = User.objects.filter(is_active=True).count()
    users_by_role = list(
        User.objects.values('role__name')
        .annotate(count=Count('id'))
        .order_by('role__name')
    )
    for row in users_by_role:
        key = row['role__name']
        row['role'] = key or 'none'
        row['role_label'] = ROLE_LABELS.get(key, key or 'Bila jukumu')

    villages = 0
    plans = 0
    parcels = 0
    try:
        from detailed_planning.models import PlanningParcel, VillageDetailedPlan
        villages = VillageDetailedPlan.objects.count()
        plans = villages
        parcels = PlanningParcel.objects.count()
    except Exception:
        pass

    try:
        from dashboard.models import VillageBoundary
        if villages == 0:
            villages = VillageBoundary.objects.count()
    except Exception:
        pass

    recent_logs = []
    try:
        for log in ImportLog.objects.order_by('-created_at')[:8]:
            recent_logs.append({
                'id': str(log.id),
                'action': log.import_type or 'import',
                'message': log.filename or 'Import',
                'status': log.status or '',
                'user': str(log.imported_by) if log.imported_by_id else '',
                'at': log.created_at.isoformat() if log.created_at else None,
            })
    except Exception:
        pass

    recent_users = [
        {
            'username': u.username,
            'action': 'login',
            'at': u.last_login.isoformat() if u.last_login else None,
        }
        for u in User.objects.filter(last_login__isnull=False).order_by('-last_login')[:6]
    ]

    return JsonResponse({
        'status': 'success',
        'kpis': {
            'users_total': users_total,
            'users_active': users_active,
            'users_online': len(online_ids),
            'villages_total': villages,
            'land_use_plans_total': plans,
            'parcels_total': parcels,
            'forms_total': SystemFormTemplate.objects.count(),
            'localities_total': Locality.objects.count(),
            'designations_total': Designation.objects.count(),
            'import_logs_total': ImportLog.objects.count() if ImportLog else 0,
        },
        'users_by_role': users_by_role,
        'recent_activities': recent_logs or recent_users,
        'modules': {
            'gis_portal': True,
            'data_portal': True,
            'detailed_planning': True,
            'ccro': True,
        },
    })


@require_GET
def api_roles_matrix(request):
    """Majukumu na ruhusa (CRUD / Export / Approve) kwa LUMC."""
    denied = _require_admin(request)
    if denied:
        return denied
    roles = []
    for code, label in ROLE_LABELS.items():
        crud = ROLE_CRUD_MATRIX.get(code, set())
        perms = ROLE_PERMISSIONS.get(code, set())
        roles.append({
            'code': code,
            'label': label,
            'permissions': sorted(perms),
            'crud': {action: action in crud for action in CRUD_ACTIONS},
        })
    return JsonResponse({
        'status': 'success',
        'actions': list(CRUD_ACTIONS),
        'roles': roles,
        'note': 'Administrator=admin, Planner=manager, GIS/Data Entry=officer, Viewer=viewer',
    })


@require_http_methods(['GET', 'POST'])
def api_users(request):
    """Orodha / unda watumiaji."""
    denied = _require_admin(request)
    if denied:
        return denied
    if request.method == 'GET':
        qs = User.objects.select_related('role', 'assigned_region', 'assigned_district').order_by('username')
        q = (request.GET.get('q') or '').strip()
        if q:
            qs = qs.filter(
                Q(username__icontains=q)
                | Q(email__icontains=q)
                | Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
            )
        role = (request.GET.get('role') or '').strip()
        if role:
            qs = qs.filter(role__name=role)
        items = [_serialize_user(u) for u in qs[:300]]
        return JsonResponse({'status': 'success', 'items': items, 'count': len(items)})

    if not (can_manage_users(request.user) or can_access_admin_panel(request.user)):
        return JsonResponse({'error': 'Huna ruhusa ya kuongeza watumiaji'}, status=403)

    body = _parse_body(request)
    username = (body.get('username') or '').strip()
    password = body.get('password') or ''
    if not username or not password:
        return JsonResponse({'error': 'Username na password vinahitajika'}, status=400)
    if User.objects.filter(username__iexact=username).exists():
        return JsonResponse({'error': 'Username tayari ipo'}, status=400)

    role_obj = None
    role_name = (body.get('role') or 'viewer').strip()
    if role_name:
        role_obj, _ = UserRole.objects.get_or_create(name=role_name)

    user = User.objects.create_user(
        username=username,
        password=password,
        email=(body.get('email') or '').strip(),
        first_name=(body.get('first_name') or '').strip(),
        last_name=(body.get('last_name') or '').strip(),
    )
    user.phone = (body.get('phone') or '').strip()
    user.role = role_obj
    user.is_active = body.get('is_active', True)
    user.save()
    return JsonResponse({'status': 'success', 'item': _serialize_user(user)}, status=201)


@require_http_methods(['GET', 'PUT', 'PATCH', 'DELETE'])
def api_user_detail(request, user_id):
    """Soma / hariri / futa / activate mtumiaji."""
    denied = _require_admin(request)
    if denied:
        return denied
    try:
        user = User.objects.select_related('role', 'assigned_region', 'assigned_district').get(pk=user_id)
    except User.DoesNotExist:
        return JsonResponse({'error': 'Mtumiaji hajapatikana'}, status=404)

    if request.method == 'GET':
        return JsonResponse({'status': 'success', 'item': _serialize_user(user)})

    if not (can_manage_users(request.user) or can_access_admin_panel(request.user)):
        return JsonResponse({'error': 'Huna ruhusa ya kusimamia watumiaji'}, status=403)

    if request.method == 'DELETE':
        if user.id == request.user.id:
            return JsonResponse({'error': 'Huwezi kufuta akaunti yako mwenyewe'}, status=400)
        if user.is_superuser and not request.user.is_superuser:
            return JsonResponse({'error': 'Huwezi kufuta superuser'}, status=403)
        uid = user.id
        try:
            user.delete()
            return JsonResponse({'status': 'success', 'deleted': uid})
        except Exception:
            # Fallback: zima akaunti ikiwa delete inashindwa (FK / DB legacy)
            user.is_active = False
            user.save(update_fields=['is_active'])
            return JsonResponse({
                'status': 'success',
                'deleted': uid,
                'deactivated': True,
                'message': 'Mtumiaji amezimwa (kufuta kamili hakukuwezekana)',
            })

    body = _parse_body(request)
    for field in ('email', 'first_name', 'last_name', 'phone'):
        if field in body:
            setattr(user, field, (body[field] or '').strip())

    if 'role' in body:
        role_name = (body.get('role') or '').strip()
        if role_name:
            role_obj, _ = UserRole.objects.get_or_create(name=role_name)
            user.role = role_obj
        else:
            user.role = None

    if 'is_active' in body:
        if user.id == request.user.id and not body['is_active']:
            return JsonResponse({'error': 'Huwezi kujizima mwenyewe'}, status=400)
        user.is_active = bool(body['is_active'])

    if body.get('reset_password'):
        new_pw = body.get('password') or 'ChangeMe123!'
        user.set_password(new_pw)

    user.save()
    return JsonResponse({
        'status': 'success',
        'item': _serialize_user(user),
        'password_reset': bool(body.get('reset_password')),
    })


# ── Currency ──────────────────────────────────────────────────────────────

@require_http_methods(['GET', 'POST'])
def api_currencies(request):
    denied = _require_admin(request)
    if denied:
        return denied
    if request.method == 'GET':
        items = [_serialize_currency(c) for c in Currency.objects.all()]
        return JsonResponse({'status': 'success', 'items': items, 'count': len(items)})

    body = _parse_body(request)
    obj = Currency.objects.create(
        code=(body.get('code') or '').strip().upper(),
        name=(body.get('name') or '').strip(),
        symbol=(body.get('symbol') or '').strip(),
        exchange_rate=body.get('exchange_rate') or 1,
        is_default=bool(body.get('is_default')),
        is_active=body.get('is_active', True),
    )
    return JsonResponse({'status': 'success', 'item': _serialize_currency(obj)}, status=201)


@require_http_methods(['PUT', 'PATCH', 'DELETE'])
def api_currency_detail(request, item_id):
    denied = _require_admin(request)
    if denied:
        return denied
    try:
        obj = Currency.objects.get(pk=item_id)
    except Currency.DoesNotExist:
        return JsonResponse({'error': 'Sarafu haijapatikana'}, status=404)

    if request.method == 'DELETE':
        obj.delete()
        return JsonResponse({'status': 'success', 'deleted': True})

    body = _parse_body(request)
    for field in ('code', 'name', 'symbol'):
        if field in body:
            val = body[field]
            setattr(obj, field, val.strip().upper() if field == 'code' else val.strip())
    if 'exchange_rate' in body:
        obj.exchange_rate = body['exchange_rate']
    if 'is_default' in body:
        obj.is_default = bool(body['is_default'])
    if 'is_active' in body:
        obj.is_active = bool(body['is_active'])
    obj.save()
    return JsonResponse({'status': 'success', 'item': _serialize_currency(obj)})


# ── Locality ──────────────────────────────────────────────────────────────

@require_http_methods(['GET', 'POST'])
def api_localities(request):
    denied = _require_admin(request)
    if denied:
        return denied
    loc_type = request.GET.get('type')
    qs = Locality.objects.all()
    if loc_type:
        qs = qs.filter(locality_type=loc_type)

    if request.method == 'GET':
        items = [_serialize_locality(x) for x in qs]
        return JsonResponse({'status': 'success', 'items': items, 'count': len(items)})

    body = _parse_body(request)
    parent_id = _uuid_or_none(body.get('parent_id'))
    loc_type_val = (body.get('locality_type') or 'office').strip()
    name = (body.get('name') or '').strip()
    region_name = (body.get('region_name') or '').strip()
    district_name = (body.get('district_name') or '').strip()
    ward_name = (body.get('ward_name') or '').strip()
    # Jaza majina ya kiutawala kutoka jina ikiwa hayakuwekwa
    if loc_type_val == 'district' and not district_name:
        district_name = name
    if loc_type_val == 'ward' and not ward_name:
        ward_name = name
    obj = Locality.objects.create(
        locality_type=loc_type_val,
        name=name,
        code=(body.get('code') or '').strip(),
        parent_id=parent_id,
        region_name=region_name,
        district_name=district_name,
        ward_name=ward_name,
        is_active=body.get('is_active', True),
        notes=(body.get('notes') or '').strip(),
    )
    return JsonResponse({'status': 'success', 'item': _serialize_locality(obj)}, status=201)


@require_http_methods(['PUT', 'PATCH', 'DELETE'])
def api_locality_detail(request, item_id):
    denied = _require_admin(request)
    if denied:
        return denied
    try:
        obj = Locality.objects.get(pk=item_id)
    except Locality.DoesNotExist:
        return JsonResponse({'error': 'Eneo halijapatikana'}, status=404)

    if request.method == 'DELETE':
        meta = _locality_boundary_meta(obj)
        if meta and meta.get('boundary_id') and meta.get('boundary_level'):
            try:
                from detailed_planning.services import clear_boundary_shapefile
                clear_boundary_shapefile(meta['boundary_id'], meta['boundary_level'])
            except Exception:
                pass
        obj.delete()
        return JsonResponse({'status': 'success', 'deleted': True})

    body = _parse_body(request)
    for field in ('locality_type', 'name', 'code', 'region_name', 'district_name', 'ward_name', 'notes'):
        if field in body:
            setattr(obj, field, (body[field] or '').strip())
    if 'parent_id' in body:
        obj.parent_id = _uuid_or_none(body.get('parent_id'))
    if 'is_active' in body:
        obj.is_active = bool(body['is_active'])
    obj.save()
    return JsonResponse({'status': 'success', 'item': _serialize_locality(obj)})


@require_GET
def api_locality_boundaries(request):
    """Orodha ya mipaka ya Wilaya/Kata (SHP) kwa Locality UI."""
    denied = _require_admin(request)
    if denied:
        return denied
    try:
        from detailed_planning.models import DistrictPlanningBoundary, WardPlanningBoundary
    except Exception as exc:
        return JsonResponse({'error': str(exc), 'items': []}, status=500)

    items = []
    for b in DistrictPlanningBoundary.objects.all().order_by('region_name', 'district_name')[:500]:
        items.append({
            'id': str(b.id),
            'level': 'district',
            'level_label': 'Wilaya',
            'region_name': b.region_name or '',
            'district_name': b.district_name or '',
            'ward_name': '',
            'title': b.district_name or 'Wilaya',
            'shapefile_name': b.shapefile_name or '',
            'has_geom': bool(b.geom),
            'uploaded_at': b.updated_at.isoformat() if getattr(b, 'updated_at', None) else None,
        })
    for b in WardPlanningBoundary.objects.all().order_by('region_name', 'district_name', 'ward_name')[:500]:
        items.append({
            'id': str(b.id),
            'level': 'ward',
            'level_label': 'Kata',
            'region_name': b.region_name or '',
            'district_name': b.district_name or '',
            'ward_name': b.ward_name or '',
            'title': b.ward_name or 'Kata',
            'shapefile_name': b.shapefile_name or '',
            'has_geom': bool(b.geom),
            'uploaded_at': b.updated_at.isoformat() if getattr(b, 'updated_at', None) else None,
        })
    return JsonResponse({'status': 'success', 'items': items, 'count': len(items)})


@require_http_methods(['POST'])
def api_locality_upload_boundary(request):
    """Pakia shapefile ya mipaka ya Wilaya au Kata kutoka Locality."""
    denied = _require_admin(request)
    if denied:
        return denied

    from dashboard.shapefile_upload_service import parse_spatial_upload_files, spatial_files_from_request
    from detailed_planning.services import import_boundaries_from_geojson

    files = spatial_files_from_request(request, ('shapefile', 'file'))
    if not files:
        return JsonResponse({'error': 'Hakuna faili. Chagua .zip (.shp+.shx+.dbf) au .geojson'}, status=400)

    level = (request.POST.get('level') or '').strip().lower()
    if level in ('district_boundary', 'wilaya'):
        level = 'district'
    if level in ('ward_boundary', 'kata'):
        level = 'ward'
    if level not in ('district', 'ward'):
        return JsonResponse({'error': 'Chagua kiwango: district (Wilaya) au ward (Kata)'}, status=400)

    region = (request.POST.get('region_name') or request.POST.get('region') or '').strip()
    district = (request.POST.get('district_name') or request.POST.get('district') or '').strip()
    ward = (request.POST.get('ward_name') or request.POST.get('ward') or '').strip()

    if not region or not district:
        return JsonResponse({'error': 'Mkoa na Wilaya vinahitajika'}, status=400)
    if level == 'ward' and not ward:
        return JsonResponse({'error': 'Jina la Kata linahitajika'}, status=400)

    try:
        geojson = parse_spatial_upload_files(files)
    except Exception as exc:
        return JsonResponse({'error': f'Imeshindwa kusoma shapefile: {exc}'}, status=400)

    shapefile_name = files[0].name if files else None
    try:
        result = import_boundaries_from_geojson(
            geojson,
            level=level,
            region=region,
            district=district,
            ward=ward or None,
            shapefile_name=shapefile_name,
            created_by=request.user,
        )
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    except Exception as exc:
        return JsonResponse({'error': f'Imeshindwa kuhifadhi mipaka: {exc}'}, status=500)

    # Sync Locality — wilaya au kata
    synced = []
    if level == 'district':
        loc = _sync_locality_from_names(level='district', region=region, district=district)
        if loc:
            synced.append(_serialize_locality(loc))
    else:
        loc = _sync_locality_from_names(level='ward', region=region, district=district, ward=ward)
        if loc:
            synced.append(_serialize_locality(loc))

    return JsonResponse({
        'status': 'success',
        'message': f'Mipaka imewekwa ({result.get("saved", 0)} vipengele)',
        'import': result,
        'localities': synced,
    })


@require_http_methods(['DELETE'])
def api_locality_delete_boundary(request, boundary_id):
    """Futa SHP/geom ya mipaka ya Wilaya au Kata (Locality inaweza kubaki)."""
    denied = _require_admin(request)
    if denied:
        return denied

    level = (request.GET.get('level') or '').strip().lower()
    if level not in ('district', 'ward'):
        return JsonResponse({'error': 'Kiwango kinahitajika (district au ward)'}, status=400)

    from detailed_planning.services import clear_boundary_shapefile

    try:
        cleared = clear_boundary_shapefile(str(boundary_id), level)
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)

    if not cleared:
        return JsonResponse({'error': 'Mipaka haijapatikana'}, status=404)

    return JsonResponse({'status': 'success', 'message': 'Shapefile ya mipaka imeondolewa'})


# ── Mpango Shapefiles (Organization) ───────────────────────────────────────

def _mpango_type_label(item: dict) -> str:
    src = item.get('source') or ''
    level = item.get('boundary_level') or ''
    if src == 'parcels' or level == 'parcel':
        return 'Viwanja'
    if src == 'landuse' or level == 'landuse':
        return 'Matumizi ya Ardhi'
    if src == 'boundary' or level in ('village', 'ward', 'district'):
        labels = {'village': 'Mpaka Kijiji', 'ward': 'Mpaka Kata', 'district': 'Mpaka Wilaya'}
        return labels.get(level, 'Mpaka')
    if src == 'stored':
        labels = {
            'parcel': 'Viwanja', 'landuse': 'Matumizi', 'village': 'Mpaka Kijiji',
            'ward': 'Mpaka Kata', 'district': 'Mpaka Wilaya',
        }
        return labels.get(level, 'Shapefile')
    return src or 'Shapefile'


@require_GET
def api_org_mpango_shapefiles(request):
    """Orodha ya shapefile za Mpango kwa Organization (viwanja, kijiji, matumizi, mipaka)."""
    denied = _require_admin(request)
    if denied:
        return denied

    region = (request.GET.get('region') or request.GET.get('region_name') or '').strip()
    district = (request.GET.get('district') or request.GET.get('district_name') or '').strip()
    ward = (request.GET.get('ward') or request.GET.get('ward_name') or '').strip()
    village = (request.GET.get('village') or request.GET.get('village_name') or '').strip()

    if not region:
        return JsonResponse({'status': 'success', 'items': [], 'count': 0, 'hint': 'Chagua mkoa'})

    from detailed_planning.services import list_uploaded_shapefiles

    items = list_uploaded_shapefiles(region, district or None, ward or None, village or None)
    if district:
        try:
            from dashboard.landuse_service import list_landuse_imports
            items.extend(list_landuse_imports(
                district=district,
                ward=ward or None,
                village=village or None,
            ))
        except Exception:
            pass

    items.sort(key=lambda x: x.get('uploaded_at') or x.get('title') or '', reverse=True)
    for it in items:
        it['type_label'] = _mpango_type_label(it)
    return JsonResponse({'status': 'success', 'items': items, 'count': len(items)})


@require_http_methods(['DELETE'])
def api_org_mpango_shapefile_delete(request):
    """Futa shapefile ya Mpango kutoka Organization."""
    denied = _require_admin(request)
    if denied:
        return denied

    body = _parse_body(request)
    source = (body.get('source') or '').strip()
    region = (body.get('region') or body.get('region_name') or '').strip()
    district = (body.get('district') or body.get('district_name') or '').strip()
    ward = (body.get('ward') or body.get('ward_name') or '').strip()
    village = (body.get('village') or body.get('village_name') or '').strip()

    if source == 'parcels':
        from detailed_planning.services import delete_parcels_by_shapefile_name
        name = (body.get('shapefile_name') or body.get('original_filename') or body.get('title') or '').strip()
        if not name or not region:
            return JsonResponse({'error': 'Jina la shapefile na mkoa vinahitajika'}, status=400)
        deleted = delete_parcels_by_shapefile_name(
            name, region=region, district=district or None, ward=ward or None, village=village or None,
        )
        if deleted == 0:
            return JsonResponse({'error': 'Hakuna viwanja vilivyopatikana'}, status=404)
        return JsonResponse({'status': 'success', 'message': f'Viwanja {deleted} vimefutwa', 'deleted': deleted})

    if source == 'landuse':
        from dashboard.landuse_service import delete_landuse_for_location
        if not district:
            return JsonResponse({'error': 'Wilaya inahitajika'}, status=400)
        deleted = delete_landuse_for_location(
            district=district, ward=ward or None, village=village or None,
        )
        if deleted == 0:
            return JsonResponse({'error': 'Hakuna matumizi yaliyopatikana'}, status=404)
        return JsonResponse({'status': 'success', 'message': f'Matumizi {deleted} yamefutwa', 'deleted': deleted})

    if source == 'boundary':
        from detailed_planning.services import clear_boundary_shapefile
        boundary_id = body.get('id') or body.get('boundary_id')
        level = (body.get('boundary_level') or body.get('level') or 'village').strip()
        if not boundary_id:
            return JsonResponse({'error': 'ID ya mipaka inahitajika'}, status=400)
        if level not in ('district', 'ward', 'village'):
            return JsonResponse({'error': 'Kiwango si sahihi'}, status=400)
        cleared = clear_boundary_shapefile(str(boundary_id), level)
        if not cleared:
            return JsonResponse({'error': 'Mipaka haijapatikana'}, status=404)
        return JsonResponse({'status': 'success', 'message': 'Mipaka ya shapefile imeondolewa'})

    if source == 'stored':
        from detailed_planning.models import PlanningShapefile
        from detailed_planning.services import delete_planning_shapefile
        shp_id = body.get('id')
        if not shp_id:
            return JsonResponse({'error': 'ID ya shapefile inahitajika'}, status=400)
        try:
            shp = PlanningShapefile.objects.get(pk=shp_id)
        except PlanningShapefile.DoesNotExist:
            return JsonResponse({'error': 'Shapefile haijapatikana'}, status=404)
        delete_planning_shapefile(shp)
        return JsonResponse({'status': 'success', 'message': 'Shapefile imefutwa'})

    return JsonResponse({'error': 'Aina ya chanzo haijulikani (source)'}, status=400)


@require_http_methods(['POST'])
def api_org_mpango_shapefile_upload(request):
    """Pakia shapefile ya Mpango (viwanja / kijiji / matumizi) kutoka Organization."""
    denied = _require_admin(request)
    if denied:
        return denied

    from dashboard.shapefile_upload_service import parse_spatial_upload_files, spatial_files_from_request

    files = spatial_files_from_request(request, ('shapefile', 'file'))
    if not files:
        return JsonResponse({'error': 'Hakuna faili. Chagua .zip/.shp/.geojson'}, status=400)

    data_type = (request.POST.get('data_type') or request.POST.get('type') or '').strip().lower()
    region = (request.POST.get('region') or request.POST.get('region_name') or '').strip()
    district = (request.POST.get('district') or request.POST.get('district_name') or '').strip()
    ward = (request.POST.get('ward') or request.POST.get('ward_name') or '').strip()
    village = (request.POST.get('village') or request.POST.get('village_name') or '').strip()

    type_map = {
        'parcels': 'parcels',
        'viwanja': 'parcels',
        'landuse': 'landuse',
        'matumizi': 'landuse',
        'village_boundary': 'village_boundary',
        'kijiji': 'village_boundary',
        'village': 'village_boundary',
    }
    data_type = type_map.get(data_type, data_type)
    if data_type not in ('parcels', 'landuse', 'village_boundary'):
        return JsonResponse({
            'error': 'Chagua aina: parcels (Viwanja), landuse (Matumizi), au village_boundary (Kijiji)',
        }, status=400)

    if not region or not district:
        return JsonResponse({'error': 'Mkoa na Wilaya vinahitajika'}, status=400)
    if data_type in ('parcels', 'village_boundary') and not ward:
        return JsonResponse({'error': 'Kata inahitajika kwa Viwanja / Mpaka wa Kijiji'}, status=400)
    if data_type == 'village_boundary' and not village:
        return JsonResponse({'error': 'Kijiji kinahitajika kwa mpaka wa kijiji'}, status=400)

    try:
        geojson = parse_spatial_upload_files(files)
    except Exception as exc:
        return JsonResponse({'error': f'Imeshindwa kusoma shapefile: {exc}'}, status=400)

    shapefile_name = files[0].name if files else None
    result = {}

    try:
        if data_type == 'parcels':
            from detailed_planning.services import import_parcels_from_geojson
            result = import_parcels_from_geojson(
                geojson,
                region=region,
                district=district,
                ward=ward or None,
                village=village or None,
                shapefile_name=shapefile_name,
                created_by=request.user,
            )
        elif data_type == 'landuse':
            from dashboard.landuse_service import import_landuse_from_geojson
            result = import_landuse_from_geojson(
                geojson,
                district=district,
                ward=ward or None,
                village=village or None,
                shapefile_name=shapefile_name,
            )
        else:
            from detailed_planning.services import import_boundaries_from_geojson
            result = import_boundaries_from_geojson(
                geojson,
                level='village',
                region=region,
                district=district,
                ward=ward or None,
                village=village or None,
                shapefile_name=shapefile_name,
                created_by=request.user,
            )
            from dashboard.locality_sync import sync_locality_from_names
            sync_locality_from_names(
                level='ward', region=region, district=district, ward=ward,
            )
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    except Exception as exc:
        return JsonResponse({'error': f'Imeshindwa kuhifadhi: {exc}'}, status=500)

    if isinstance(result, dict) and result.get('error'):
        return JsonResponse({'error': result['error']}, status=400)

    saved = (
        result.get('created', 0) + result.get('updated', 0)
        if data_type != 'village_boundary'
        else result.get('saved', 0)
    )
    return JsonResponse({
        'status': 'success',
        'message': f'Shapefile imehifadhiwa ({saved} vipengele)',
        'data_type': data_type,
        'import': result,
    })


# ── Designation ─────────────────────────────────────────────────────────────

@require_http_methods(['GET', 'POST'])
def api_designations(request):
    denied = _require_admin(request)
    if denied:
        return denied
    if request.method == 'GET':
        items = [_serialize_designation(d) for d in Designation.objects.all()]
        return JsonResponse({'status': 'success', 'items': items, 'count': len(items)})

    body = _parse_body(request)
    obj = Designation.objects.create(
        name=(body.get('name') or '').strip(),
        code=(body.get('code') or '').strip(),
        category=(body.get('category') or '').strip(),
        description=(body.get('description') or '').strip(),
        is_active=body.get('is_active', True),
        sort_order=int(body.get('sort_order') or 0),
    )
    return JsonResponse({'status': 'success', 'item': _serialize_designation(obj)}, status=201)


@require_http_methods(['PUT', 'PATCH', 'DELETE'])
def api_designation_detail(request, item_id):
    denied = _require_admin(request)
    if denied:
        return denied
    try:
        obj = Designation.objects.get(pk=item_id)
    except Designation.DoesNotExist:
        return JsonResponse({'error': 'Cheo hakijapatikana'}, status=404)

    if request.method == 'DELETE':
        obj.delete()
        return JsonResponse({'status': 'success', 'deleted': True})

    body = _parse_body(request)
    for field in ('name', 'code', 'category', 'description'):
        if field in body:
            setattr(obj, field, (body[field] or '').strip())
    if 'is_active' in body:
        obj.is_active = bool(body['is_active'])
    if 'sort_order' in body:
        obj.sort_order = int(body['sort_order'] or 0)
    obj.save()
    return JsonResponse({'status': 'success', 'item': _serialize_designation(obj)})


# ── Form Management ───────────────────────────────────────────────────────

@require_http_methods(['GET', 'POST'])
def api_forms(request):
    denied = _require_admin(request)
    if denied:
        return denied
    category = request.GET.get('category')
    qs = SystemFormTemplate.objects.all()
    if category:
        qs = qs.filter(category=category)

    if request.method == 'GET':
        items = [_serialize_form(f) for f in qs]
        return JsonResponse({'status': 'success', 'items': items, 'count': len(items)})

    body = _parse_body(request)
    obj = SystemFormTemplate.objects.create(
        name=(body.get('name') or '').strip(),
        code=(body.get('code') or '').strip(),
        category=body.get('category', 'general'),
        description=(body.get('description') or '').strip(),
        fields_schema=body.get('fields_schema') or [],
        version=(body.get('version') or '1.0').strip(),
        is_active=body.get('is_active', True),
    )
    return JsonResponse({'status': 'success', 'item': _serialize_form(obj)}, status=201)


@require_http_methods(['PUT', 'PATCH', 'DELETE'])
def api_form_detail(request, item_id):
    denied = _require_admin(request)
    if denied:
        return denied
    try:
        obj = SystemFormTemplate.objects.get(pk=item_id)
    except SystemFormTemplate.DoesNotExist:
        return JsonResponse({'error': 'Fomu haijapatikana'}, status=404)

    if request.method == 'DELETE':
        obj.delete()
        return JsonResponse({'status': 'success', 'deleted': True})

    body = _parse_body(request)
    for field in ('name', 'code', 'category', 'description', 'version'):
        if field in body:
            setattr(obj, field, (body[field] or '').strip())
    if 'fields_schema' in body:
        obj.fields_schema = body['fields_schema'] or []
    if 'is_active' in body:
        obj.is_active = bool(body['is_active'])
    obj.save()
    return JsonResponse({'status': 'success', 'item': _serialize_form(obj)})


# ── CCRO Management ───────────────────────────────────────────────────────

@require_http_methods(['GET', 'POST'])
def api_ccro_config(request):
    denied = _require_admin(request)
    if denied:
        return denied
    category = request.GET.get('category')
    qs = CcroConfigOption.objects.all()
    if category:
        qs = qs.filter(category=category)

    if request.method == 'GET':
        items = [_serialize_ccro_option(o) for o in qs]
        stats = _ccro_stats()
        return JsonResponse({
            'status': 'success',
            'items': items,
            'count': len(items),
            'stats': stats,
        })

    body = _parse_body(request)
    obj = CcroConfigOption.objects.create(
        category=body.get('category', 'land_use'),
        value=(body.get('value') or '').strip(),
        label=(body.get('label') or '').strip(),
        sort_order=int(body.get('sort_order') or 0),
        is_active=body.get('is_active', True),
    )
    return JsonResponse({'status': 'success', 'item': _serialize_ccro_option(obj)}, status=201)


@require_http_methods(['PUT', 'PATCH', 'DELETE'])
def api_ccro_config_detail(request, item_id):
    denied = _require_admin(request)
    if denied:
        return denied
    try:
        obj = CcroConfigOption.objects.get(pk=item_id)
    except CcroConfigOption.DoesNotExist:
        return JsonResponse({'error': 'Chaguo halijapatikana'}, status=404)

    if request.method == 'DELETE':
        obj.delete()
        return JsonResponse({'status': 'success', 'deleted': True})

    body = _parse_body(request)
    for field in ('category', 'value', 'label'):
        if field in body:
            setattr(obj, field, (body[field] or '').strip())
    if 'sort_order' in body:
        obj.sort_order = int(body['sort_order'] or 0)
    if 'is_active' in body:
        obj.is_active = bool(body['is_active'])
    obj.save()
    return JsonResponse({'status': 'success', 'item': _serialize_ccro_option(obj)})


def _ccro_stats() -> dict:
    try:
        from detailed_planning.models import PlanningParcel
        total = PlanningParcel.objects.count()
        identified = PlanningParcel.objects.filter(is_identified=True).count()
        villages = PlanningParcel.objects.values('village_name').distinct().count()
        return {
            'total_parcels': total,
            'identified_parcels': identified,
            'unidentified_parcels': total - identified,
            'villages_with_ccro': villages,
        }
    except Exception:
        return {
            'total_parcels': 0,
            'identified_parcels': 0,
            'unidentified_parcels': 0,
            'villages_with_ccro': 0,
        }


def seed_default_admin_data():
    """Weka data ya msingi ikiwa hakuna."""
    if not Currency.objects.exists():
        Currency.objects.bulk_create([
            Currency(code='TZS', name='Tanzanian Shilling', symbol='TSh', exchange_rate=1, is_default=True),
            Currency(code='USD', name='US Dollar', symbol='$', exchange_rate=2650),
        ])

    if not CcroConfigOption.objects.exists():
        defaults = [
            ('land_use', 'residential', 'Makazi'),
            ('land_use', 'agricultural', 'Kilimo'),
            ('land_use', 'commercial', 'Biashara'),
            ('ownership_type', 'individual', 'Binafsi'),
            ('ownership_type', 'joint', 'Wamiliki wa Pamoja'),
            ('ownership_type', 'communal', 'Jamii'),
        ]
        CcroConfigOption.objects.bulk_create([
            CcroConfigOption(category=cat, value=val, label=lbl, sort_order=i)
            for i, (cat, val, lbl) in enumerate(defaults)
        ])

    if not SystemFormTemplate.objects.exists():
        SystemFormTemplate.objects.create(
            name='Fomu ya CCRO',
            code='CCRO_STANDARD',
            category='ccro',
            description='Fomu ya kawaida ya CCRO / hati ya umiliki wa ardhi',
            fields_schema=[
                {'name': 'parties', 'label': 'Wamiliki', 'type': 'text', 'required': True},
                {'name': 'claim_no', 'label': 'Namba ya Dai', 'type': 'text', 'required': False},
                {'name': 'land_use', 'label': 'Matumizi ya Ardhi', 'type': 'select', 'required': True},
                {'name': 'ownership_type', 'label': 'Aina ya Umiliki', 'type': 'select', 'required': True},
            ],
        )

    if not Designation.objects.exists():
        Designation.objects.bulk_create([
            Designation(name='Afisa Ardhi', code='LAND_OFFICER', category='staff', sort_order=1),
            Designation(name='Meneja Mkoa', code='REGION_MGR', category='staff', sort_order=2),
            Designation(name='Mmiliki wa Ardhi', code='LANDOWNER', category='ccro', sort_order=3),
        ])
