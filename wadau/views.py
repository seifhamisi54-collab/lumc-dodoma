import json

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from dashboard.financial_year import (
    DEFAULT_FINANCIAL_YEAR,
    normalize_financial_year,
    session_financial_year,
    set_session_financial_year,
)
from .models import Stakeholder


def _parse_body(request):
    if request.content_type and 'application/json' in request.content_type:
        try:
            return json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            return {}
    return request.POST.dict()


def _stakeholder_to_dict(obj):
    return {
        'id': str(obj.id),
        'name': obj.name,
        'organization': obj.organization or '',
        'stakeholder_type': obj.stakeholder_type,
        'stakeholder_type_label': obj.get_stakeholder_type_display(),
        'category': obj.category,
        'category_label': obj.get_category_display(),
        'phone': obj.phone or '',
        'email': obj.email or '',
        'role': obj.role or '',
        'financial_year': obj.financial_year or DEFAULT_FINANCIAL_YEAR,
        'region_name': obj.region_name or '',
        'district_name': obj.district_name or '',
        'ward_name': obj.ward_name or '',
        'village_name': obj.village_name or '',
        'notes': obj.notes or '',
        'is_active': obj.is_active,
        'created_at': obj.created_at.isoformat() if obj.created_at else None,
        'updated_at': obj.updated_at.isoformat() if obj.updated_at else None,
    }


def _apply_filters(qs, request):
    region = (request.GET.get('region_name') or request.GET.get('region') or '').strip()
    district = (request.GET.get('district_name') or request.GET.get('district') or '').strip()
    ward = (request.GET.get('ward_name') or request.GET.get('ward') or '').strip()
    village = (request.GET.get('village_name') or request.GET.get('village') or '').strip()
    stype = (request.GET.get('stakeholder_type') or request.GET.get('type') or '').strip()
    category = (request.GET.get('category') or '').strip()
    fy = (request.GET.get('financial_year') or request.GET.get('fy') or '').strip()
    q = (request.GET.get('q') or '').strip()
    active = request.GET.get('is_active')

    if region:
        qs = qs.filter(region_name__iexact=region)
    if district:
        qs = qs.filter(district_name__iexact=district)
    if ward:
        qs = qs.filter(ward_name__iexact=ward)
    if village:
        qs = qs.filter(village_name__iexact=village)
    if stype:
        qs = qs.filter(stakeholder_type=stype)
    if category:
        qs = qs.filter(category=category)
    if fy:
        qs = qs.filter(financial_year=normalize_financial_year(fy))
    if active in ('0', '1', 'true', 'false'):
        qs = qs.filter(is_active=active in ('1', 'true'))
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(organization__icontains=q)
            | Q(phone__icontains=q)
            | Q(email__icontains=q)
            | Q(role__icontains=q)
            | Q(village_name__icontains=q)
            | Q(financial_year__icontains=q)
            | Q(category__icontains=q)
        )
    return qs


def _payload_from_data(data, request=None):
    stype = (data.get('stakeholder_type') or Stakeholder.StakeholderType.COMMUNITY).strip()
    valid_types = {c[0] for c in Stakeholder.StakeholderType.choices}
    if stype not in valid_types:
        stype = Stakeholder.StakeholderType.COMMUNITY

    category = (
        data.get('category') or Stakeholder.StakeholderCategory.PUBLIC_INSTITUTIONS
    ).strip()
    valid_categories = {c[0] for c in Stakeholder.StakeholderCategory.choices}
    if category not in valid_categories:
        category = Stakeholder.StakeholderCategory.PUBLIC_INSTITUTIONS

    is_active = data.get('is_active', True)
    if isinstance(is_active, str):
        is_active = is_active.lower() in ('1', 'true', 'yes', 'on')

    fy_raw = (data.get('financial_year') or '').strip()
    if fy_raw:
        financial_year = normalize_financial_year(fy_raw)
    elif request is not None:
        financial_year = session_financial_year(request)
    else:
        financial_year = DEFAULT_FINANCIAL_YEAR

    return {
        'name': (data.get('name') or '').strip(),
        'organization': (data.get('organization') or '').strip(),
        'stakeholder_type': stype,
        'category': category,
        'phone': (data.get('phone') or '').strip(),
        'email': (data.get('email') or '').strip(),
        'role': (data.get('role') or '').strip(),
        'financial_year': financial_year,
        'region_name': (data.get('region_name') or '').strip(),
        'district_name': (data.get('district_name') or '').strip(),
        'ward_name': (data.get('ward_name') or '').strip(),
        'village_name': (data.get('village_name') or '').strip(),
        'notes': (data.get('notes') or '').strip(),
        'is_active': bool(is_active),
    }


def _type_stats(qs=None):
    qs = qs if qs is not None else Stakeholder.objects.all()
    agg = qs.aggregate(
        total=Count('id'),
        active=Count('id', filter=Q(is_active=True)),
        inactive=Count('id', filter=Q(is_active=False)),
    )
    by_type = {
        row['stakeholder_type']: row['c']
        for row in qs.values('stakeholder_type').annotate(c=Count('id'))
    }
    by_category = {
        row['category']: row['c']
        for row in qs.values('category').annotate(c=Count('id'))
    }
    agg['by_type'] = by_type
    agg['by_category'] = by_category
    return agg


@login_required
def wadau_portal(request):
    fy = normalize_financial_year(
        request.GET.get('financial_year') or request.GET.get('fy') or session_financial_year(request)
    )
    set_session_financial_year(request, fy)
    stats = _type_stats(Stakeholder.objects.filter(financial_year=fy))
    return render(request, 'wadau/portal.html', {
        'stats': stats,
        'stakeholder_types': Stakeholder.StakeholderType.choices,
        'stakeholder_categories': Stakeholder.StakeholderCategory.choices,
        'current_financial_year': fy,
        'default_financial_year': DEFAULT_FINANCIAL_YEAR,
    })


@login_required
@require_http_methods(['GET', 'POST'])
def api_stakeholders(request):
    if request.method == 'GET':
        qs = _apply_filters(Stakeholder.objects.all(), request)
        if not (request.GET.get('financial_year') or request.GET.get('fy')):
            qs = qs.filter(financial_year=session_financial_year(request))
        rows = [_stakeholder_to_dict(s) for s in qs[:2000]]
        filtered_base = _apply_filters(Stakeholder.objects.all(), request)
        if not (request.GET.get('financial_year') or request.GET.get('fy')):
            filtered_base = filtered_base.filter(financial_year=session_financial_year(request))
        return JsonResponse({
            'success': True,
            'count': len(rows),
            'totals': _type_stats(filtered_base),
            'results': rows,
            'categories': [
                {'value': v, 'label': lbl}
                for v, lbl in Stakeholder.StakeholderCategory.choices
            ],
        })

    data = _parse_body(request)
    payload = _payload_from_data(data, request)
    if not payload['name']:
        return JsonResponse({'success': False, 'message': 'Jaza jina la mdau'}, status=400)

    set_session_financial_year(request, payload['financial_year'])
    obj = Stakeholder.objects.create(
        created_by_id=request.user.id if request.user.is_authenticated else None,
        **payload,
    )
    return JsonResponse({'success': True, 'stakeholder': _stakeholder_to_dict(obj)}, status=201)


@login_required
@require_http_methods(['GET', 'PATCH', 'PUT', 'DELETE'])
def api_stakeholder_detail(request, stakeholder_id):
    try:
        obj = Stakeholder.objects.get(pk=stakeholder_id)
    except Stakeholder.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Mdau hajapatikana'}, status=404)

    if request.method == 'GET':
        return JsonResponse({'success': True, 'stakeholder': _stakeholder_to_dict(obj)})

    if request.method == 'DELETE':
        obj.delete()
        return JsonResponse({'success': True, 'message': 'Mdau amefutwa'})

    data = _parse_body(request)
    if request.method == 'PATCH':
        base = _stakeholder_to_dict(obj)
        for key in (
            'name', 'organization', 'stakeholder_type', 'category', 'phone', 'email', 'role',
            'financial_year', 'region_name', 'district_name', 'ward_name', 'village_name',
            'notes', 'is_active',
        ):
            if key not in data:
                data[key] = base.get(key)

    payload = _payload_from_data(data, request)
    if not payload['name']:
        return JsonResponse({'success': False, 'message': 'Jaza jina la mdau'}, status=400)

    set_session_financial_year(request, payload['financial_year'])
    for key, value in payload.items():
        setattr(obj, key, value)
    obj.save()
    return JsonResponse({'success': True, 'stakeholder': _stakeholder_to_dict(obj)})
