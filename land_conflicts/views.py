import json
from datetime import date

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .models import (
    DEFAULT_FINANCIAL_YEAR,
    LandConflictCase,
    available_financial_years,
    financial_year_from_date,
)


def _db_conflict_types():
    return list(LandConflictCase.ConflictType.choices)


def _db_conflict_sources():
    return list(LandConflictCase.ConflictSource.choices)


def _db_resolution_methods():
    return list(LandConflictCase.ResolutionMethod.choices)


def _db_financial_years():
    return available_financial_years()


def _parse_body(request):
    if request.content_type and 'application/json' in request.content_type:
        try:
            return json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            return {}
    return request.POST.dict()


def _parse_date(value):
    if not value:
        return None
    if hasattr(value, 'isoformat'):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _normalize_fy(value):
    fy = (value or '').strip()
    if not fy:
        return DEFAULT_FINANCIAL_YEAR
    # accept 2026-2027 → 2026/2027
    fy = fy.replace('-', '/')
    if len(fy) == 9 and fy[4] == '/':
        return fy
    return DEFAULT_FINANCIAL_YEAR


def _case_to_dict(case):
    return {
        'id': str(case.id),
        'case_number': case.case_number,
        'title': case.title,
        'financial_year': case.financial_year,
        'conflict_type': case.conflict_type,
        'conflict_type_label': case.get_conflict_type_display(),
        'conflict_type_other': case.conflict_type_other or '',
        'conflict_source': case.conflict_source,
        'conflict_source_label': case.get_conflict_source_display(),
        'status': case.status,
        'status_label': case.get_status_display(),
        'is_resolved': case.is_resolved,
        'region_name': case.region_name,
        'district_name': case.district_name,
        'ward_name': case.ward_name,
        'village_name': case.village_name,
        'village_name_other': case.village_name_other or '',
        'parties_label': case.parties_label(),
        'complainant': case.complainant,
        'respondent': case.respondent,
        'description': case.description,
        'started_date': case.started_date.isoformat() if case.started_date else None,
        'resolved_date': case.resolved_date.isoformat() if case.resolved_date else None,
        'filed_date': case.filed_date.isoformat() if case.filed_date else None,
        'resolution_method': case.resolution_method,
        'resolution_method_label': case.get_resolution_method_display(),
        'resolution_details': case.resolution_details,
        'unresolved_reason': case.unresolved_reason,
        'created_at': case.created_at.isoformat() if case.created_at else None,
        'updated_at': case.updated_at.isoformat() if case.updated_at else None,
    }


def _next_case_number(financial_year=None):
    fy = _normalize_fy(financial_year or DEFAULT_FINANCIAL_YEAR)
    # MG-2627-0001 from 2026/2027
    try:
        y1, y2 = fy.split('/')
        tag = y1[-2:] + y2[-2:]
    except ValueError:
        tag = str(date.today().year)[-2:] + str(date.today().year + 1)[-2:]
    prefix = f'MG-{tag}-'
    last = (
        LandConflictCase.objects.filter(case_number__startswith=prefix)
        .order_by('-case_number')
        .values_list('case_number', flat=True)
        .first()
    )
    seq = 1
    if last:
        try:
            seq = int(last.split('-')[-1]) + 1
        except (ValueError, IndexError):
            seq = LandConflictCase.objects.filter(case_number__startswith=prefix).count() + 1
    return f'{prefix}{seq:04d}'


def _apply_location_filters(qs, request):
    region = (request.GET.get('region') or request.GET.get('region_name') or '').strip()
    district = (request.GET.get('district') or request.GET.get('district_name') or '').strip()
    ward = (request.GET.get('ward') or request.GET.get('ward_name') or '').strip()
    village = (request.GET.get('village') or request.GET.get('village_name') or '').strip()
    status = (request.GET.get('status') or '').strip()
    resolved = (request.GET.get('resolved') or '').strip()
    conflict_type = (request.GET.get('conflict_type') or '').strip()
    financial_year = (request.GET.get('financial_year') or request.GET.get('fy') or '').strip()
    q = (request.GET.get('q') or '').strip()

    if financial_year:
        qs = qs.filter(financial_year=_normalize_fy(financial_year))
    if region:
        qs = qs.filter(region_name__iexact=region)
    if district:
        qs = qs.filter(district_name__iexact=district)
    if ward:
        qs = qs.filter(ward_name__iexact=ward)
    if village:
        qs = qs.filter(village_name__iexact=village)
    if status:
        qs = qs.filter(status=status)
    if resolved == '1' or resolved.lower() == 'true':
        qs = qs.filter(is_resolved=True)
    elif resolved == '0' or resolved.lower() == 'false':
        qs = qs.filter(is_resolved=False)
    if conflict_type:
        qs = qs.filter(conflict_type=conflict_type)
    if q:
        qs = qs.filter(
            Q(case_number__icontains=q)
            | Q(title__icontains=q)
            | Q(complainant__icontains=q)
            | Q(respondent__icontains=q)
            | Q(village_name__icontains=q)
            | Q(village_name_other__icontains=q)
            | Q(conflict_source__icontains=q)
            | Q(unresolved_reason__icontains=q)
            | Q(financial_year__icontains=q)
        )
    return qs


def _case_payload(data, user=None, existing=None):
    status = data.get('status') or (existing.status if existing else LandConflictCase.Status.OPEN)
    is_resolved = status in (LandConflictCase.Status.RESOLVED, LandConflictCase.Status.CLOSED)
    if 'is_resolved' in data:
        flag = data.get('is_resolved')
        is_resolved = flag in (True, 'true', '1', 1, 'yes', 'on')
        if is_resolved and status not in (LandConflictCase.Status.RESOLVED, LandConflictCase.Status.CLOSED):
            status = LandConflictCase.Status.RESOLVED
        if not is_resolved and status in (LandConflictCase.Status.RESOLVED, LandConflictCase.Status.CLOSED):
            status = LandConflictCase.Status.OPEN

    started = _parse_date(data.get('started_date'))
    if started is None and existing:
        started = existing.started_date

    fy_raw = (data.get('financial_year') or '').strip()
    if fy_raw:
        financial_year = _normalize_fy(fy_raw)
    elif started:
        financial_year = financial_year_from_date(started)
    elif existing and existing.financial_year:
        financial_year = existing.financial_year
    else:
        financial_year = DEFAULT_FINANCIAL_YEAR

    payload = {
        'title': (data.get('title') or '').strip(),
        'financial_year': financial_year,
        'conflict_type': data.get('conflict_type') or LandConflictCase.ConflictType.VILLAGE_BOUNDARY,
        'conflict_type_other': (data.get('conflict_type_other') or '').strip(),
        'conflict_source': data.get('conflict_source') or LandConflictCase.ConflictSource.OTHER,
        'status': status,
        'is_resolved': is_resolved,
        'region_name': (data.get('region_name') or '').strip(),
        'district_name': (data.get('district_name') or '').strip(),
        'ward_name': (data.get('ward_name') or '').strip(),
        'village_name': (data.get('village_name') or '').strip(),
        'village_name_other': (data.get('village_name_other') or '').strip(),
        'complainant': (data.get('complainant') or '').strip(),
        'respondent': (data.get('respondent') or '').strip(),
        'description': (data.get('description') or '').strip(),
        'started_date': started,
        'resolved_date': _parse_date(data.get('resolved_date')),
        'filed_date': _parse_date(data.get('filed_date')) or (existing.filed_date if existing else date.today()),
        'resolution_method': data.get('resolution_method') or LandConflictCase.ResolutionMethod.NONE,
        'resolution_details': (data.get('resolution_details') or '').strip(),
        'unresolved_reason': (data.get('unresolved_reason') or '').strip(),
    }
    if not is_resolved:
        payload['resolved_date'] = None
    else:
        payload['unresolved_reason'] = ''
        if not payload['resolution_method'] or payload['resolution_method'] == LandConflictCase.ResolutionMethod.NONE:
            payload['resolution_method'] = LandConflictCase.ResolutionMethod.OTHER
    if payload['conflict_type'] != LandConflictCase.ConflictType.OTHER:
        payload['conflict_type_other'] = ''
    return payload


def _type_stats(qs=None):
    qs = qs if qs is not None else LandConflictCase.objects.all()
    return qs.aggregate(
        total=Count('id'),
        open=Count('id', filter=Q(is_resolved=False)),
        resolved=Count('id', filter=Q(is_resolved=True)),
        villages=Count('village_name', distinct=True, filter=~Q(village_name='')),
        type_boundary=Count('id', filter=Q(conflict_type=LandConflictCase.ConflictType.VILLAGE_BOUNDARY)),
        type_farmers=Count('id', filter=Q(conflict_type=LandConflictCase.ConflictType.FARMERS_PASTORALISTS)),
        type_resources=Count('id', filter=Q(conflict_type=LandConflictCase.ConflictType.RESOURCES)),
        type_other=Count('id', filter=Q(conflict_type=LandConflictCase.ConflictType.OTHER)),
    )


@login_required
def migogoro_portal(request):
    fy = _normalize_fy(request.GET.get('financial_year') or DEFAULT_FINANCIAL_YEAR)
    stats = _type_stats(LandConflictCase.objects.filter(financial_year=fy))
    fy_choices = _db_financial_years()
    if DEFAULT_FINANCIAL_YEAR not in fy_choices:
        fy_choices.insert(0, DEFAULT_FINANCIAL_YEAR)
    return render(request, 'land_conflicts/portal.html', {
        'stats': stats,
        'conflict_types': _db_conflict_types(),
        'conflict_sources': _db_conflict_sources(),
        'resolution_methods': _db_resolution_methods(),
        'status_choices': LandConflictCase.Status.choices,
        'financial_years': fy_choices,
        'current_financial_year': fy,
        'default_financial_year': DEFAULT_FINANCIAL_YEAR,
    })


@login_required
@require_http_methods(['GET'])
def api_lookups(request):
    """Orodha za aina / chanzo / utatuzi / FY (kutoka model choices — jedwali moja)."""
    return JsonResponse({
        'success': True,
        'table': 'migogoro',
        'cases_count': LandConflictCase.objects.count(),
        'conflict_types': [
            {'code': code, 'name': name}
            for code, name in LandConflictCase.ConflictType.choices
        ],
        'conflict_sources': [
            {'code': code, 'name': name}
            for code, name in LandConflictCase.ConflictSource.choices
        ],
        'resolution_methods': [
            {'code': code, 'name': name}
            for code, name in LandConflictCase.ResolutionMethod.choices
        ],
        'financial_years': [
            {'code': y, 'label': y, 'is_default': y == DEFAULT_FINANCIAL_YEAR}
            for y in available_financial_years()
        ],
        'default_financial_year': DEFAULT_FINANCIAL_YEAR,
    })


@login_required
@require_http_methods(['GET'])
def api_summary(request):
    """Muhtasari: mikoa / wilaya / kata / vijiji vyenye migogoro (kwa FY)."""
    qs = _apply_location_filters(LandConflictCase.objects.all(), request)
    # Default FY when not specified
    if not (request.GET.get('financial_year') or request.GET.get('fy')):
        qs = qs.filter(financial_year=DEFAULT_FINANCIAL_YEAR)
    group = (request.GET.get('group') or 'village').strip().lower()

    if group == 'region':
        rows = (
            qs.values('region_name')
            .annotate(
                total=Count('id'),
                unresolved=Count('id', filter=Q(is_resolved=False)),
                resolved=Count('id', filter=Q(is_resolved=True)),
                villages=Count('village_name', distinct=True, filter=~Q(village_name='')),
            )
            .order_by('region_name')
        )
        results = [{
            'region_name': r['region_name'] or '—',
            'total': r['total'],
            'unresolved': r['unresolved'],
            'resolved': r['resolved'],
            'villages': r['villages'],
        } for r in rows if r['region_name']]
    elif group == 'district':
        rows = (
            qs.values('region_name', 'district_name')
            .annotate(
                total=Count('id'),
                unresolved=Count('id', filter=Q(is_resolved=False)),
                resolved=Count('id', filter=Q(is_resolved=True)),
                villages=Count('village_name', distinct=True, filter=~Q(village_name='')),
            )
            .order_by('region_name', 'district_name')
        )
        results = [{
            'region_name': r['region_name'] or '—',
            'district_name': r['district_name'] or '—',
            'total': r['total'],
            'unresolved': r['unresolved'],
            'resolved': r['resolved'],
            'villages': r['villages'],
        } for r in rows if r['district_name']]
    elif group == 'ward':
        rows = (
            qs.values('region_name', 'district_name', 'ward_name')
            .annotate(
                total=Count('id'),
                unresolved=Count('id', filter=Q(is_resolved=False)),
                resolved=Count('id', filter=Q(is_resolved=True)),
                villages=Count('village_name', distinct=True, filter=~Q(village_name='')),
            )
            .order_by('region_name', 'district_name', 'ward_name')
        )
        results = [{
            'region_name': r['region_name'] or '—',
            'district_name': r['district_name'] or '—',
            'ward_name': r['ward_name'] or '—',
            'total': r['total'],
            'unresolved': r['unresolved'],
            'resolved': r['resolved'],
            'villages': r['villages'],
        } for r in rows if r['ward_name']]
    else:
        rows = (
            qs.values('region_name', 'district_name', 'ward_name', 'village_name')
            .annotate(
                total=Count('id'),
                unresolved=Count('id', filter=Q(is_resolved=False)),
                resolved=Count('id', filter=Q(is_resolved=True)),
            )
            .order_by('region_name', 'district_name', 'ward_name', 'village_name')
        )
        results = [{
            'region_name': r['region_name'] or '—',
            'district_name': r['district_name'] or '—',
            'ward_name': r['ward_name'] or '—',
            'village_name': r['village_name'] or '—',
            'total': r['total'],
            'unresolved': r['unresolved'],
            'resolved': r['resolved'],
        } for r in rows if r['village_name']]

    totals = _type_stats(qs)
    totals['unresolved'] = totals.get('open', 0)
    return JsonResponse({
        'success': True,
        'group': group,
        'count': len(results),
        'totals': totals,
        'results': results,
    })


@login_required
@require_http_methods(['GET', 'POST'])
def api_cases(request):
    if request.method == 'GET':
        qs = _apply_location_filters(LandConflictCase.objects.all(), request)
        if not (request.GET.get('financial_year') or request.GET.get('fy')):
            qs = qs.filter(financial_year=DEFAULT_FINANCIAL_YEAR)
        cases = [_case_to_dict(c) for c in qs[:1000]]
        return JsonResponse({
            'success': True,
            'count': len(cases),
            'financial_year': request.GET.get('financial_year') or DEFAULT_FINANCIAL_YEAR,
            'results': cases,
        })

    data = _parse_body(request)
    region = (data.get('region_name') or '').strip()
    district = (data.get('district_name') or '').strip()
    village = (data.get('village_name') or '').strip()
    if not region or not district:
        return JsonResponse({'success': False, 'message': 'Chagua mkoa na wilaya'}, status=400)
    if not village:
        return JsonResponse({'success': False, 'message': 'Chagua kijiji chenye mgogoro'}, status=400)
    if not (data.get('complainant') or '').strip() or not (data.get('respondent') or '').strip():
        return JsonResponse({
            'success': False,
            'message': 'Jaza Mlalamikaji na Mlalamikiwa (mfano: Ifunde - Njaro)',
        }, status=400)
    if not data.get('conflict_type'):
        return JsonResponse({'success': False, 'message': 'Chagua aina ya mgogoro'}, status=400)
    if data.get('conflict_type') == LandConflictCase.ConflictType.OTHER and not (data.get('conflict_type_other') or '').strip():
        return JsonResponse({'success': False, 'message': 'Eleza aina nyingine ya mgogoro'}, status=400)
    if not data.get('started_date'):
        return JsonResponse({'success': False, 'message': 'Weka tarehe mgogoro ulipoanzia'}, status=400)

    payload = _case_payload(data, user=request.user)
    if not payload['is_resolved'] and not payload['unresolved_reason']:
        return JsonResponse({
            'success': False,
            'message': 'Eleza kwanini mgogoro bado haujatatuliwa',
        }, status=400)
    if payload['is_resolved'] and (
        not payload['resolution_method']
        or payload['resolution_method'] == LandConflictCase.ResolutionMethod.NONE
    ):
        return JsonResponse({
            'success': False,
            'message': 'Chagua mbinu za utatuzi kwa mgogoro uliotatuliwa',
        }, status=400)

    case = LandConflictCase.objects.create(
        case_number=(data.get('case_number') or '').strip() or _next_case_number(payload['financial_year']),
        created_by_id=request.user.id if request.user.is_authenticated else None,
        **payload,
    )
    return JsonResponse({'success': True, 'case': _case_to_dict(case)}, status=201)


@login_required
@require_http_methods(['GET', 'PATCH', 'PUT', 'DELETE'])
def api_case_detail(request, case_id):
    try:
        case = LandConflictCase.objects.get(pk=case_id)
    except LandConflictCase.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Kesi haijapatikana'}, status=404)

    if request.method == 'GET':
        return JsonResponse({'success': True, 'case': _case_to_dict(case)})

    if request.method == 'DELETE':
        case.delete()
        return JsonResponse({'success': True, 'message': 'Kesi imefutwa'})

    data = _parse_body(request)
    # Merge: keep existing fields if not sent (partial edit)
    if request.method == 'PATCH':
        base = _case_to_dict(case)
        for key in (
            'title', 'financial_year', 'conflict_type', 'conflict_type_other', 'conflict_source', 'status',
            'is_resolved', 'region_name', 'district_name', 'ward_name', 'village_name',
            'village_name_other',
            'complainant', 'respondent', 'description', 'started_date', 'resolved_date',
            'filed_date', 'resolution_method', 'resolution_details', 'unresolved_reason',
        ):
            if key not in data:
                data[key] = base.get(key)

    if not data.get('started_date') and case.started_date:
        data['started_date'] = case.started_date.isoformat()

    payload = _case_payload(data, user=request.user, existing=case)
    if not payload.get('region_name') or not payload.get('district_name'):
        return JsonResponse({'success': False, 'message': 'Chagua mkoa na wilaya'}, status=400)
    if not payload.get('village_name'):
        return JsonResponse({'success': False, 'message': 'Chagua kijiji chenye mgogoro'}, status=400)
    if not payload.get('complainant') or not payload.get('respondent'):
        return JsonResponse({
            'success': False,
            'message': 'Jaza Mlalamikaji na Mlalamikiwa (mfano: Ifunde - Njaro)',
        }, status=400)
    if payload.get('conflict_type') == LandConflictCase.ConflictType.OTHER and not payload.get('conflict_type_other'):
        return JsonResponse({'success': False, 'message': 'Eleza aina nyingine ya mgogoro'}, status=400)
    if not payload['is_resolved'] and not payload['unresolved_reason']:
        return JsonResponse({
            'success': False,
            'message': 'Eleza kwanini mgogoro bado haujatatuliwa',
        }, status=400)
    if payload['is_resolved'] and (
        not payload['resolution_method']
        or payload['resolution_method'] == LandConflictCase.ResolutionMethod.NONE
    ):
        return JsonResponse({
            'success': False,
            'message': 'Chagua mbinu za utatuzi kwa mgogoro uliotatuliwa',
        }, status=400)

    for key, value in payload.items():
        setattr(case, key, value)
    case.save()
    return JsonResponse({'success': True, 'case': _case_to_dict(case)})
