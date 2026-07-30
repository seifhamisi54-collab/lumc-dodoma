import json
import logging
import os

from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.db.models import Q
from django.http import FileResponse, JsonResponse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from dashboard.boundary_service import _district_search_names
from dashboard.shapefile_upload_service import parse_spatial_upload_files, spatial_files_from_request
from detailed_planning.models import (
    DistrictPlanningBoundary,
    MeetingMinutes,
    PlanningParcel,
    PlanningReport,
    PlanningShapefile,
    QuarterReport,
    VillageDetailedPlan,
    VillagePlanningBoundary,
    WardPlanningBoundary,
)
from detailed_planning.services import (
    _geom_to_wgs84_dict,
    boundary_to_geojson,
    boundaries_to_feature_collection,
    CCRO_SEARCH_FIELDS,
    clear_boundary_shapefile,
    compute_is_identified,
    create_planning_parcel,
    deduplicate_village_plan_list,
    delete_meeting_minutes,
    delete_parcels_by_shapefile_name,
    delete_planning_report,
    delete_planning_shapefile,
    delete_quarter_report,
    get_or_create_village_plan,
    list_parcel_shapefile_imports,
    list_uploaded_shapefiles,
    merge_duplicate_village_plans,
    parcel_source_summary,
    parcel_stats_from_queryset,
    save_meeting_minutes_file,
    save_planning_report_file,
    save_quarter_report_file,
    serialize_ccro_landowner,
    serialize_ccro_shapefile_fields,
    serialize_meeting_minutes,
    serialize_planning_report,
    serialize_quarter_report,
    serialize_village_plan,
)

logger = logging.getLogger(__name__)


def _upload_permission_denied(request):
    """Ruhusu tu watumiaji wenye ruhusa ya upload au admin."""
    from accounts.permissions import can_upload

    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Ingia kwanza ili kufuta data'}, status=401)
    if not (can_upload(request.user) or request.user.is_superuser):
        return JsonResponse({'error': 'Huna ruhusa ya kufuta data. Wasiliana na msimamizi.'}, status=403)
    return None


def _clean(value):
    if not value or str(value).lower() in ('undefined', 'null', 'none', ''):
        return None
    return str(value).strip()


def _gazette_regions():
    try:
        from locations.gazette_models import GazetteVillage
        return set(
            GazetteVillage.objects.exclude(region_name='')
            .values_list('region_name', flat=True)
            .distinct()
        )
    except Exception:
        return set()


def _is_gazette_noise_name(name: str, kind: str = 'any') -> bool:
    try:
        from locations.gazette_quality import is_impurity
        return is_impurity(name or '', kind=kind)
    except Exception:
        return False


def _gazette_districts(region):
    try:
        from locations.gazette_models import GazetteVillage
        return {
            d for d in GazetteVillage.objects.filter(region_name__iexact=region)
            .exclude(district_name='')
            .values_list('district_name', flat=True)
            .distinct()
            if not _is_gazette_noise_name(d, 'district')
        }
    except Exception:
        return set()


def _gazette_district_q(region, district):
    """Match gazeti halmashauri loosely against selected district name."""
    import re
    from django.db.models import Q
    from dashboard.boundary_service import _district_search_names

    q = Q(region_name__iexact=region)
    dist_q = Q()
    for dist in _district_search_names(district) or [district]:
        if not dist:
            continue
        dist_q |= Q(district_name__iexact=dist)
        dist_q |= Q(district_name__icontains=dist)
        core = re.sub(
            r'(?i)\s+(mjini|vijijini|manispaa|jiji|mji|dc|tc|mc|halmashauri)$',
            '',
            dist,
        ).strip()
        if core and core.lower() != dist.lower():
            dist_q |= Q(district_name__icontains=core)
            dist_q |= Q(district_name__iexact=core)
    if not dist_q:
        return q
    return q & dist_q


def _gazette_wards(region, district):
    try:
        from locations.gazette_models import GazetteVillage
        return {
            w for w in GazetteVillage.objects.filter(_gazette_district_q(region, district))
            .exclude(ward_name='')
            .values_list('ward_name', flat=True)
            .distinct()
            if not _is_gazette_noise_name(w, 'ward')
        }
    except Exception:
        return set()


def _gazette_villages(region, district, ward):
    try:
        from locations.gazette_models import GazetteVillage
        names = {
            v for v in GazetteVillage.objects.filter(
                _gazette_district_q(region, district),
                ward_name__iexact=ward,
            )
            .exclude(village_name='')
            .values_list('village_name', flat=True)
            .distinct()
            if not _is_gazette_noise_name(v, 'village')
        }
        if names:
            return names
        # Fallback: kijiji kwa mkoa + kata (halmashauri ya gazeti inaweza kutofautiana)
        return {
            v for v in GazetteVillage.objects.filter(
                region_name__iexact=region,
                ward_name__iexact=ward,
            )
            .exclude(village_name='')
            .values_list('village_name', flat=True)
            .distinct()
            if not _is_gazette_noise_name(v, 'village')
        }
    except Exception:
        return set()


def _regions_queryset():
    names = set(
        DistrictPlanningBoundary.objects.filter(region_name__isnull=False)
        .exclude(region_name='')
        .values_list('region_name', flat=True)
        .distinct()
    )
    names |= _gazette_regions()
    return sorted(names)


def _districts_queryset(region):
    names = set(
        DistrictPlanningBoundary.objects.filter(region_name__iexact=region, district_name__isnull=False)
        .exclude(district_name='')
        .values_list('district_name', flat=True)
        .distinct()
    )
    names |= _gazette_districts(region)
    return sorted(names)


def _district_name_q(district: str) -> Q:
    """OR-filter kwa jina la wilaya na aliases (mf. Madaba ↔ Songea)."""
    names = _district_search_names(district)
    if not names:
        return Q()
    clause = Q()
    for name in names:
        clause |= Q(district_name__iexact=name)
    return clause


def _wards_queryset(region, district):
    wards: set[str] = set()
    for dist in _district_search_names(district):
        wards.update(
            WardPlanningBoundary.objects.filter(
                region_name__iexact=region,
                district_name__iexact=dist,
                ward_name__isnull=False,
            )
            .exclude(ward_name='')
            .values_list('ward_name', flat=True)
        )
    wards |= _gazette_wards(region, district)
    return sorted(wards)


_PLACEHOLDER_VILLAGES = frozenset({'imported', 'unknown', 'n/a', '-'})


def _villages_queryset(region, district, ward):
    """Vijiji vyote vilivyo na data — planning_parcels, mipango, na mipaka."""
    villages: set[str] = set()
    for dist in _district_search_names(district):
        villages.update(
            VillagePlanningBoundary.objects.filter(
                region_name__iexact=region,
                district_name__iexact=dist,
                ward_name__iexact=ward,
                village_name__isnull=False,
            )
            .exclude(village_name='')
            .values_list('village_name', flat=True)
        )
        villages.update(
            VillageDetailedPlan.objects.filter(
                region_name__iexact=region,
                district_name__iexact=dist,
                ward_name__iexact=ward,
                village_name__isnull=False,
            )
            .exclude(village_name='')
            .values_list('village_name', flat=True)
        )
        villages.update(
            PlanningParcel.objects.filter(
                region_name__iexact=region,
                district_name__iexact=dist,
                ward_name__iexact=ward,
                village_name__isnull=False,
            )
            .exclude(village_name='')
            .values_list('village_name', flat=True)
        )
    villages |= _gazette_villages(region, district, ward)
    return sorted(
        v for v in villages
        if v and v.strip().lower() not in _PLACEHOLDER_VILLAGES
    )


@require_GET
def api_regions(request):
    try:
        data = [{'name': r} for r in _regions_queryset()]
        return JsonResponse(data, safe=False)
    except Exception as e:
        logger.exception('api_regions failed')
        return JsonResponse({'error': str(e)}, status=500)


@require_GET
def api_districts(request, region):
    region = _clean(region)
    if not region:
        return JsonResponse([], safe=False)
    try:
        data = [{'name': d} for d in _districts_queryset(region)]
        return JsonResponse(data, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_GET
def api_wards(request, region, district):
    region, district = _clean(region), _clean(district)
    if not region or not district:
        return JsonResponse([], safe=False)
    try:
        data = [{'name': w} for w in _wards_queryset(region, district)]
        return JsonResponse(data, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_GET
def api_villages(request, region, district, ward):
    region, district, ward = _clean(region), _clean(district), _clean(ward)
    if not all([region, district, ward]):
        return JsonResponse([], safe=False)
    try:
        data = [{'name': v} for v in _villages_queryset(region, district, ward)]
        return JsonResponse(data, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def _location_filter(region=None, district=None, ward=None, village=None):
    q = Q()
    if region:
        q &= Q(region_name__iexact=region)
    if district:
        q &= _district_name_q(district)
    if ward:
        q &= Q(ward_name__iexact=ward)
    if village:
        q &= Q(village_name__iexact=village)
    return q


def _parcels_geojson_features(parcels_qs) -> tuple[list, int, int]:
    """Jenga features za GeoJSON bila kikomo cha idadi (viwanja vyote vilivyochaguliwa)."""
    total_matching = parcels_qs.count()
    with_geom = parcels_qs.exclude(geom__isnull=True).count()
    features = []
    for p in parcels_qs.exclude(geom__isnull=True).iterator():
        geometry = _geom_to_wgs84_dict(p.geom)
        if not geometry:
            continue
        features.append({
            'type': 'Feature',
            'geometry': geometry,
            'properties': {
                'parcel_number': p.parcel_number,
                'is_identified': p.is_identified,
                'identified_label': 'Imetambuliwa' if p.is_identified else 'Haijatambuliwa',
                'owner_name': p.owner_name or '',
                'village_name': p.village_name,
                **serialize_ccro_shapefile_fields(p),
            },
        })
    return features, total_matching, with_geom


@require_GET
def api_stats(request):
    region = _clean(request.GET.get('region'))
    district = _clean(request.GET.get('district'))
    ward = _clean(request.GET.get('ward'))
    village = _clean(request.GET.get('village'))

    flt = _location_filter(region, district, ward, village)

    merge_duplicate_village_plans(
        region=region,
        district=district,
        ward=ward,
        village=village,
        prefer_district=district,
    )

    plans_qs = VillageDetailedPlan.objects.filter(flt)
    parcels = PlanningParcel.objects.filter(flt)
    parcel_stats = parcel_stats_from_queryset(parcels)

    plans = deduplicate_village_plan_list(list(plans_qs), prefer_district=district)

    plan = None
    if village:
        plan = next((p for p in plans if p.village_name.lower() == village.lower()), None)
        if not plan:
            plan = get_or_create_village_plan(region, district, ward, village)

    stats = {
        'region': region,
        'district': district,
        'ward': ward,
        'village': village,
        **parcel_stats,
        'villages_with_plans': len(plans),
        'total_mpango_kinaa': len(plans),
        'villages_with_parcels': parcels.values('village_name').distinct().count(),
        'data_source': 'planning_parcels',
        **parcel_source_summary(parcels),
        'plan_status': plan.plan_status if plan else None,
        'plan_year': plan.plan_year if plan else None,
    }
    return JsonResponse(stats)


@require_GET
def api_district_boundaries(request, region):
    region = _clean(region)
    if not region:
        return JsonResponse({'type': 'FeatureCollection', 'features': []})
    try:
        qs = DistrictPlanningBoundary.objects.filter(
            region_name__iexact=region,
            geom__isnull=False,
        ).order_by('district_name')
        return JsonResponse(
            boundaries_to_feature_collection(qs, name_attr='district_name', feature_type='district')
        )
    except Exception as e:
        logger.exception('api_district_boundaries failed')
        return JsonResponse({'type': 'FeatureCollection', 'features': [], 'error': str(e)})


@require_GET
def api_ward_boundaries(request, region, district):
    region, district = _clean(region), _clean(district)
    if not region or not district:
        return JsonResponse({'type': 'FeatureCollection', 'features': []})
    try:
        ward_q = Q(region_name__iexact=region, geom__isnull=False)
        ward_q &= _district_name_q(district)
        qs = WardPlanningBoundary.objects.filter(ward_q).order_by('ward_name')
        return JsonResponse(
            boundaries_to_feature_collection(qs, name_attr='ward_name', feature_type='ward')
        )
    except Exception as e:
        logger.exception('api_ward_boundaries failed')
        return JsonResponse({'type': 'FeatureCollection', 'features': [], 'error': str(e)})


@require_GET
def api_region_boundary(request, region):
    region = _clean(region)
    if not region:
        return JsonResponse({'success': False, 'error': 'Invalid region name'}, status=400)
    try:
        districts = DistrictPlanningBoundary.objects.filter(
            region_name__iexact=region,
            geom__isnull=False,
        )
        if not districts.exists():
            return JsonResponse({'success': False, 'error': f'Region "{region}" not found'}, status=404)

        merged = None
        for obj in districts:
            geom = obj.geom
            if not geom:
                continue
            if geom.srid != 4326:
                geom = geom.clone()
                geom.transform(4326)
            merged = geom if merged is None else merged.union(geom)

        geometry = _geom_to_wgs84_dict(merged)
        if not geometry:
            return JsonResponse({'success': False, 'error': f'Region "{region}" not found'}, status=404)

        centroid = merged.centroid
        return JsonResponse({
            'success': True,
            'boundary_geojson': geometry,
            'center_lat': centroid.y,
            'center_lon': centroid.x,
            'name': region,
        })
    except Exception as e:
        logger.exception('api_region_boundary failed')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_GET
def api_boundary(request):
    level = _clean(request.GET.get('level'))
    region = _clean(request.GET.get('region'))
    district = _clean(request.GET.get('district'))
    ward = _clean(request.GET.get('ward'))
    village = _clean(request.GET.get('village'))

    try:
        if level == 'district' and region and district:
            obj = None
            for dist in _district_search_names(district):
                obj = DistrictPlanningBoundary.objects.filter(
                    region_name__iexact=region, district_name__iexact=dist
                ).first()
                if obj:
                    break
        elif level == 'ward' and region and district and ward:
            obj = None
            for dist in _district_search_names(district):
                obj = WardPlanningBoundary.objects.filter(
                    region_name__iexact=region,
                    district_name__iexact=dist,
                    ward_name__iexact=ward,
                ).first()
                if obj:
                    break
        elif level == 'village' and all([region, district, ward, village]):
            obj = None
            for dist in _district_search_names(district):
                obj = VillagePlanningBoundary.objects.filter(
                    region_name__iexact=region,
                    district_name__iexact=dist,
                    ward_name__iexact=ward,
                    village_name__iexact=village,
                ).first()
                if obj:
                    break
        else:
            return JsonResponse({'error': 'Vigezo vya boundary si kamili'}, status=400)

        feature = boundary_to_geojson(obj)
        if not feature:
            return JsonResponse({'type': 'FeatureCollection', 'features': []})
        return JsonResponse({'type': 'FeatureCollection', 'features': [feature]})
    except Exception as e:
        logger.exception('api_boundary failed')
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def api_upload_shapefile(request):
    level = _clean(request.POST.get('level'))
    region = _clean(request.POST.get('region'))
    district = _clean(request.POST.get('district'))
    ward = _clean(request.POST.get('ward'))
    village = _clean(request.POST.get('village'))
    uploaded_files = spatial_files_from_request(request, ('file',))

    if not uploaded_files or not level:
        return JsonResponse({'error': 'Faili na level zinahitajika'}, status=400)
    uploaded = uploaded_files[0]

    try:
        from detailed_planning.services import import_boundaries_from_geojson

        fc = parse_spatial_upload_files(uploaded_files)
        import_meta = fc.get('import_meta') or {}
        result = import_boundaries_from_geojson(
            fc,
            level=level,
            region=region,
            district=district,
            ward=ward,
            village=village,
            shapefile_name=uploaded.name,
            created_by=request.user,
        )
        resp = {
            'status': 'success',
            'saved': result.get('saved', 0),
            'skipped': result.get('skipped', 0),
            'import_meta': import_meta,
            'boundary_import': result,
        }
        if import_meta.get('message_sw'):
            resp['warning'] = import_meta['message_sw']
        if result.get('errors'):
            resp['errors'] = result['errors']
        return JsonResponse(resp)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        logger.exception('upload shapefile failed')
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def api_create_parcel(request):
    try:
        body = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON si sahihi'}, status=400)

    region = _clean(body.get('region'))
    district = _clean(body.get('district'))
    ward = _clean(body.get('ward'))
    village = _clean(body.get('village'))

    if not all([region, district, ward, village]):
        return JsonResponse({'error': 'Mkoa, wilaya, kata na kijiji zinahitajika'}, status=400)

    parcel = create_planning_parcel(
        region, district, ward, village,
        is_identified=compute_is_identified(
            owner_name=body.get('owner_name'),
            notes=body.get('notes'),
        ) if body.get('is_identified') is None else bool(body.get('is_identified')),
        owner_name=body.get('owner_name'),
        owner_gender=body.get('owner_gender'),
        owner_age_category=body.get('owner_age_category'),
        owner_is_landowner=bool(body.get('owner_is_landowner', True)),
        notes=body.get('notes'),
        created_by=request.user,
    )
    return JsonResponse({
        'status': 'success',
        'parcel_number': parcel.parcel_number,
        'id': str(parcel.id),
    })


@login_required
@require_POST
def api_generate_plot_numbers(request):
    """Tengeneza namba za viwanja kwa vijiji vilivyochaguliwa."""
    try:
        body = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON si sahihi'}, status=400)

    region = _clean(body.get('region'))
    district = _clean(body.get('district'))
    ward = _clean(body.get('ward'))
    village = _clean(body.get('village'))
    count = int(body.get('count', 1))
    is_identified = bool(body.get('is_identified', False))

    if not all([region, district, ward, village]):
        return JsonResponse({'error': 'Eneo lazima lijazwe'}, status=400)

    created = []
    for _ in range(max(1, min(count, 500))):
        p = create_planning_parcel(
            region, district, ward, village,
            is_identified=is_identified,
            created_by=request.user,
        )
        created.append(p.parcel_number)

    return JsonResponse({'status': 'success', 'created': created, 'count': len(created)})


@require_GET
def api_parcels(request):
    region = _clean(request.GET.get('region'))
    district = _clean(request.GET.get('district'))
    ward = _clean(request.GET.get('ward'))
    village = _clean(request.GET.get('village'))

    flt = _location_filter(region, district, ward, village)
    parcels_qs = PlanningParcel.objects.filter(flt).order_by('parcel_number')
    total = parcels_qs.count()

    data = [{
        'id': str(p.id),
        'parcel_number': p.parcel_number,
        'village_name': p.village_name,
        'is_identified': p.is_identified,
        'owner_name': p.owner_name,
        'owner_gender': p.owner_gender,
        'owner_age_category': p.owner_age_category,
        'area_ha': p.area_ha,
        **serialize_ccro_shapefile_fields(p),
    } for p in parcels_qs]

    return JsonResponse({'parcels': data, 'count': len(data), 'total': total})


@require_GET
def api_parcels_geojson(request):
    """GeoJSON ya viwanja vya detailed planning — kwa GIS Portal (WGS84)."""
    region = _clean(request.GET.get('region'))
    district = _clean(request.GET.get('district'))
    ward = _clean(request.GET.get('ward'))
    village = _clean(request.GET.get('village'))

    if not all([region, district, ward]):
        return JsonResponse({'type': 'FeatureCollection', 'features': []})

    flt = _location_filter(region, district, ward, village)
    parcels_qs = PlanningParcel.objects.filter(flt).order_by('village_name', 'parcel_number')
    features, total_matching, with_geom = _parcels_geojson_features(parcels_qs)

    return JsonResponse({
        'type': 'FeatureCollection',
        'features': features,
        'meta': {
            'total_matching': total_matching,
            'with_geometry': with_geom,
            'returned': len(features),
            'region': region,
            'district': district,
            'ward': ward,
            'village': village or None,
        },
    })


@require_http_methods(['GET', 'POST'])
def api_village_plans(request):
    """Orodha / unda mipango ya kina kutoka detailed_planning.village_plans."""
    if request.method == 'POST':
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Ingia kwanza'}, status=401)
        try:
            body = json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON si sahihi'}, status=400)

        region = _clean(body.get('region') or body.get('region_name'))
        district = _clean(body.get('district') or body.get('district_name'))
        ward = _clean(body.get('ward') or body.get('ward_name'))
        village = _clean(body.get('village') or body.get('village_name'))
        if not all([region, district, ward, village]):
            return JsonResponse({'error': 'Mkoa, wilaya, kata na kijiji vinahitajika'}, status=400)

        plan = get_or_create_village_plan(region, district, ward, village)
        if body.get('plan_year') is not None:
            try:
                plan.plan_year = int(body['plan_year'])
            except (TypeError, ValueError):
                pass
        if body.get('financial_year') is not None:
            from dashboard.financial_year import normalize_financial_year, set_session_financial_year
            plan.financial_year = normalize_financial_year(body.get('financial_year') or '')
            set_session_financial_year(request, plan.financial_year)
        if body.get('plan_status'):
            valid = {c[0] for c in VillageDetailedPlan.PLAN_STATUS}
            if body['plan_status'] in valid:
                plan.plan_status = body['plan_status']
        if 'notes' in body:
            plan.notes = body.get('notes') or ''
        plan.save()
        return JsonResponse({
            'status': 'success',
            'success': True,
            'plan': serialize_village_plan(plan, prefer_district=district),
        }, status=201)

    region = _clean(request.GET.get('region'))
    district = _clean(request.GET.get('district'))
    ward = _clean(request.GET.get('ward'))
    village = _clean(request.GET.get('village'))
    status = _clean(request.GET.get('status'))

    flt = _location_filter(region, district, ward, village)

    merge_duplicate_village_plans(
        region=region,
        district=district,
        ward=ward,
        village=village,
        prefer_district=district,
    )

    qs = VillageDetailedPlan.objects.filter(flt).order_by(
        'region_name', 'district_name', 'ward_name', 'village_name'
    )
    if status:
        qs = qs.filter(plan_status__iexact=status)

    deduped = deduplicate_village_plan_list(list(qs[:500]), prefer_district=district)
    plans = [serialize_village_plan(p, prefer_district=district) for p in deduped]
    return JsonResponse({
        'status': 'success',
        'count': len(plans),
        'total_mpango_kinaa': len(plans),
        'plans': plans,
    })


@login_required
@require_http_methods(['GET', 'PUT', 'PATCH', 'DELETE'])
def api_village_plan_detail(request, plan_id):
    """Soma, sasisha au futa mpango wa kijiji."""
    try:
        plan = VillageDetailedPlan.objects.get(pk=plan_id)
    except VillageDetailedPlan.DoesNotExist:
        return JsonResponse({'error': 'Mpango haujapatikana'}, status=404)

    if request.method == 'GET':
        return JsonResponse({'status': 'success', 'plan': serialize_village_plan(plan)})

    if request.method == 'DELETE':
        denied = _upload_permission_denied(request)
        if denied:
            return denied
        plan_id_str = str(plan.id)
        plan.delete()
        return JsonResponse({'status': 'success', 'success': True, 'deleted': plan_id_str})

    try:
        body = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON si sahihi'}, status=400)

    int_fields = (
        'total_landowners', 'female_landowners', 'male_landowners',
        'children_under_18', 'identified_parcels', 'unidentified_parcels', 'plan_year',
    )
    for field in int_fields:
        if field in body and body[field] is not None:
            setattr(plan, field, max(0, int(body[field])))

    if 'plan_status' in body and body['plan_status']:
        valid = {c[0] for c in VillageDetailedPlan.PLAN_STATUS}
        if body['plan_status'] in valid:
            plan.plan_status = body['plan_status']

    if 'financial_year' in body:
        from dashboard.financial_year import normalize_financial_year, set_session_financial_year
        plan.financial_year = normalize_financial_year(body.get('financial_year') or '')
        set_session_financial_year(request, plan.financial_year)

    if 'notes' in body:
        plan.notes = body['notes']

    plan.save()
    return JsonResponse({'status': 'success', 'plan': serialize_village_plan(plan)})


@require_GET
def api_shapefiles(request):
    """Orodha ya shapefile zilizopakiwa kwa eneo lililochaguliwa."""
    region = _clean(request.GET.get('region'))
    district = _clean(request.GET.get('district'))
    ward = _clean(request.GET.get('ward'))
    village = _clean(request.GET.get('village'))

    if not region:
        return JsonResponse({'status': 'success', 'count': 0, 'shapefiles': []})

    shapefiles = list_uploaded_shapefiles(region, district, ward, village)
    if district:
        try:
            from dashboard.landuse_service import list_landuse_imports

            shapefiles.extend(list_landuse_imports(
                district=district,
                ward=ward or None,
                village=village or None,
            ))
            shapefiles.sort(key=lambda x: x.get('uploaded_at') or x.get('title') or '', reverse=True)
        except Exception:
            logger.exception('list_landuse_imports failed')
    return JsonResponse({'status': 'success', 'count': len(shapefiles), 'shapefiles': shapefiles})


@require_GET
def api_parcel_shapefiles(request):
    """Orodha ya viwanja vilivyoingizwa kutoka shapefile (planning_parcels), kwa jina la faili."""
    region = _clean(request.GET.get('region'))
    district = _clean(request.GET.get('district'))
    ward = _clean(request.GET.get('ward'))
    village = _clean(request.GET.get('village'))

    if not region:
        return JsonResponse({'status': 'success', 'count': 0, 'shapefiles': [], 'data_source': 'planning_parcels'})

    shapefiles = list_parcel_shapefile_imports(region, district, ward, village)
    return JsonResponse({
        'status': 'success',
        'count': len(shapefiles),
        'shapefiles': shapefiles,
        'data_source': 'planning_parcels',
    })


@login_required
@require_http_methods(['DELETE'])
def api_shapefile_delete(request, shapefile_id):
    """Futa shapefile iliyohifadhiwa kwenye planning_shapefiles."""
    denied = _upload_permission_denied(request)
    if denied:
        return denied

    try:
        shapefile = PlanningShapefile.objects.get(pk=shapefile_id)
    except PlanningShapefile.DoesNotExist:
        return JsonResponse({'error': 'Shapefile haijapatikana'}, status=404)

    delete_planning_shapefile(shapefile)
    return JsonResponse({'status': 'success', 'message': 'Shapefile imefutwa'})


@login_required
@require_http_methods(['DELETE'])
def api_shapefile_delete_parcel(request):
    """Futa viwanja kutoka planning_parcels kwa jina la shapefile (si mipaka wala planning_shapefiles)."""
    denied = _upload_permission_denied(request)
    if denied:
        return denied

    try:
        body = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON si sahihi'}, status=400)

    shapefile_name = _clean(body.get('shapefile_name'))
    region = _clean(body.get('region'))
    if not shapefile_name or not region:
        return JsonResponse({'error': 'Jina la shapefile na mkoa vinahitajika'}, status=400)

    deleted = delete_parcels_by_shapefile_name(
        shapefile_name,
        region=region,
        district=_clean(body.get('district')),
        ward=_clean(body.get('ward')),
        village=_clean(body.get('village')),
    )
    if deleted == 0:
        return JsonResponse({'error': 'Hakuna viwanja vilivyopatikana kwa shapefile hii'}, status=404)

    return JsonResponse({
        'status': 'success',
        'message': f'Viwanja {deleted} vimefutwa',
        'deleted': deleted,
    })


@login_required
@require_http_methods(['DELETE'])
def api_shapefile_delete_boundary(request, boundary_id):
    """Ondoa mipaka iliyopakiwa kutoka rekodi ya boundary."""
    denied = _upload_permission_denied(request)
    if denied:
        return denied

    level = _clean(request.GET.get('level'))
    if level not in ('district', 'ward', 'village'):
        return JsonResponse({'error': 'Kiwango cha boundary kinahitajika (district/ward/village)'}, status=400)

    try:
        cleared = clear_boundary_shapefile(boundary_id, level)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)

    if not cleared:
        return JsonResponse({'error': 'Mipaka haijapatikana'}, status=404)

    return JsonResponse({
        'status': 'success',
        'message': 'Mipaka ya shapefile imeondolewa',
    })


@login_required
@require_http_methods(['DELETE'])
def api_shapefile_delete_landuse(request):
    """Futa matumizi ya ardhi kwa wilaya/kata/kijiji."""
    denied = _upload_permission_denied(request)
    if denied:
        return denied

    try:
        body = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON si sahihi'}, status=400)

    district = _clean(body.get('district') or body.get('district_name'))
    ward = _clean(body.get('ward') or body.get('ward_name'))
    village = _clean(body.get('village') or body.get('village_name'))
    if not district:
        return JsonResponse({'error': 'Wilaya inahitajika'}, status=400)

    from dashboard.landuse_service import delete_landuse_for_location

    deleted = delete_landuse_for_location(
        district=district,
        ward=ward or None,
        village=village or None,
    )
    if deleted == 0:
        return JsonResponse({'error': 'Hakuna matumizi yaliyopatikana kwa eneo hili'}, status=404)

    return JsonResponse({
        'status': 'success',
        'message': f'Matumizi {deleted} yamefutwa',
        'deleted': deleted,
    })


@login_required
@require_http_methods(['DELETE'])
def api_report_delete(request, report_id):
    """Futa ripoti ya PDF na faili yake."""
    denied = _upload_permission_denied(request)
    if denied:
        return denied

    try:
        report = PlanningReport.objects.get(pk=report_id)
    except PlanningReport.DoesNotExist:
        return JsonResponse({'error': 'Ripoti haijapatikana'}, status=404)

    delete_planning_report(report)
    return JsonResponse({'status': 'success', 'message': 'Ripoti imefutwa'})


@require_GET
def api_reports(request):
    """Orodha ya PDF za ripoti au ramani."""
    region = _clean(request.GET.get('region'))
    district = _clean(request.GET.get('district'))
    ward = _clean(request.GET.get('ward'))
    village = _clean(request.GET.get('village'))
    report_type = _clean(request.GET.get('report_type'))

    flt = Q()
    if region:
        flt &= Q(region_name__iexact=region)
    if district:
        flt &= _district_name_q(district)
    if ward:
        flt &= Q(ward_name__iexact=ward)
    if village:
        flt &= Q(village_name__iexact=village)
    if report_type:
        flt &= Q(report_type__iexact=report_type)

    qs = PlanningReport.objects.filter(flt).order_by('-created_at')[:100]
    reports = [serialize_planning_report(r) for r in qs]
    return JsonResponse({'status': 'success', 'count': len(reports), 'reports': reports})


@login_required
@require_POST
def api_report_upload(request):
    """Pakia PDF ya ripoti (plan_summary) au ramani (boundary_map)."""
    uploaded = request.FILES.get('file')
    report_type = _clean(request.POST.get('report_type')) or 'plan_summary'
    region = _clean(request.POST.get('region'))
    district = _clean(request.POST.get('district'))
    ward = _clean(request.POST.get('ward'))
    village = _clean(request.POST.get('village'))
    title = _clean(request.POST.get('title'))
    plan_id = _clean(request.POST.get('plan_id'))

    if not uploaded or not region:
        return JsonResponse({'error': 'Faili na mkoa vinahitajika'}, status=400)

    if report_type in ('quarter_report', 'section_minutes'):
        return JsonResponse({
            'error': 'Tumia API maalum: /api/planning/quarter-reports/ au /api/planning/meeting-minutes/',
        }, status=400)

    if report_type not in ('plan_summary', 'boundary_map', 'pdf'):
        return JsonResponse({'error': 'Aina ya ripoti si sahihi'}, status=400)

    if not uploaded.name.lower().endswith(('.pdf', '.doc', '.docx')):
        return JsonResponse({'error': 'Faili lazima iwe PDF au Word'}, status=400)

    village_plan = None
    if plan_id:
        village_plan = VillageDetailedPlan.objects.filter(pk=plan_id).first()
    elif all([region, district, ward, village]):
        village_plan = get_or_create_village_plan(region, district, ward, village)

    report_year = None
    year_raw = request.POST.get('report_year')
    if year_raw:
        try:
            report_year = int(year_raw)
        except (TypeError, ValueError):
            pass

    try:
        report = save_planning_report_file(
            uploaded,
            report_type=report_type,
            region=region,
            district=district,
            ward=ward,
            village=village,
            title=title,
            report_year=report_year,
            village_plan=village_plan,
            generated_by=request.user,
        )
        return JsonResponse({
            'status': 'success',
            'report': serialize_planning_report(report),
        })
    except Exception as e:
        logger.exception('report upload failed')
        return JsonResponse({'error': str(e)}, status=500)


def _file_download_response(obj):
    """Pakua faili kutoka storage kwa QuarterReport / MeetingMinutes / PlanningReport."""
    content_map = {
        'pdf': 'application/pdf',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'csv': 'text/csv',
    }
    ctype = content_map.get(getattr(obj, 'file_format', '') or 'pdf', 'application/octet-stream')
    if not obj.file_path or not default_storage.exists(obj.file_path):
        abs_path = obj.file_path
        if abs_path and os.path.isfile(abs_path):
            return FileResponse(
                open(abs_path, 'rb'),
                content_type=ctype,
                as_attachment=True,
                filename=obj.original_filename,
            )
        return JsonResponse({'error': 'Faili haijapatikana'}, status=404)
    file_handle = default_storage.open(obj.file_path, 'rb')
    return FileResponse(
        file_handle,
        content_type=ctype,
        as_attachment=True,
        filename=obj.original_filename,
    )


@require_GET
def api_quarter_reports(request):
    """Orodha ya Quarter Reports kutoka jedwali quarter_reports."""
    fy = _clean(request.GET.get('financial_year') or request.GET.get('fy'))
    quarter = _clean(request.GET.get('quarter'))
    qs = QuarterReport.objects.all()
    if fy:
        qs = qs.filter(financial_year__iexact=fy)
    if quarter:
        qs = qs.filter(quarter__iexact=quarter.upper())
    rows = [serialize_quarter_report(r) for r in qs.order_by('-created_at')[:200]]
    return JsonResponse({'status': 'success', 'count': len(rows), 'reports': rows})


@login_required
@require_POST
def api_quarter_report_upload(request):
    """Pakia Quarter Report → detailed_planning.quarter_reports."""
    uploaded = request.FILES.get('file')
    if not uploaded:
        return JsonResponse({'error': 'Faili inahitajika'}, status=400)
    if not uploaded.name.lower().endswith(('.pdf', '.doc', '.docx')):
        return JsonResponse({'error': 'Faili lazima iwe PDF au Word'}, status=400)
    quarter = _clean(request.POST.get('quarter'))
    if quarter.upper() not in ('Q1', 'Q2', 'Q3', 'Q4'):
        return JsonResponse({'error': 'Chagua robo sahihi (Q1–Q4)'}, status=400)
    try:
        obj = save_quarter_report_file(
            uploaded,
            title=_clean(request.POST.get('title')) or None,
            financial_year=_clean(request.POST.get('financial_year')) or '',
            quarter=quarter,
            notes=_clean(request.POST.get('notes')) or '',
            generated_by=request.user,
        )
        return JsonResponse({'status': 'success', 'report': serialize_quarter_report(obj)}, status=201)
    except Exception as e:
        logger.exception('quarter report upload failed')
        return JsonResponse({'error': str(e)}, status=500)


@require_GET
def api_quarter_report_download(request, report_id):
    try:
        obj = QuarterReport.objects.get(pk=report_id)
    except QuarterReport.DoesNotExist:
        return JsonResponse({'error': 'Quarter Report haijapatikana'}, status=404)
    return _file_download_response(obj)


@login_required
@require_http_methods(['DELETE'])
def api_quarter_report_delete(request, report_id):
    denied = _upload_permission_denied(request)
    if denied:
        return denied
    try:
        obj = QuarterReport.objects.get(pk=report_id)
    except QuarterReport.DoesNotExist:
        return JsonResponse({'error': 'Quarter Report haijapatikana'}, status=404)
    delete_quarter_report(obj)
    return JsonResponse({'status': 'success', 'message': 'Quarter Report imefutwa'})


@require_GET
def api_meeting_minutes(request):
    """Orodha ya Minutes za Vikao kutoka jedwali meeting_minutes."""
    fy = _clean(request.GET.get('financial_year') or request.GET.get('fy'))
    qs = MeetingMinutes.objects.all()
    if fy:
        qs = qs.filter(financial_year__iexact=fy)
    rows = [serialize_meeting_minutes(r) for r in qs.order_by('-created_at')[:200]]
    return JsonResponse({'status': 'success', 'count': len(rows), 'reports': rows})


@login_required
@require_POST
def api_meeting_minutes_upload(request):
    """Pakia Minutes za Vikao → detailed_planning.meeting_minutes."""
    uploaded = request.FILES.get('file')
    if not uploaded:
        return JsonResponse({'error': 'Faili inahitajika'}, status=400)
    if not uploaded.name.lower().endswith(('.pdf', '.doc', '.docx')):
        return JsonResponse({'error': 'Faili lazima iwe PDF au Word'}, status=400)
    try:
        obj = save_meeting_minutes_file(
            uploaded,
            title=_clean(request.POST.get('title')) or None,
            financial_year=_clean(request.POST.get('financial_year')) or '',
            meeting_date=_clean(request.POST.get('meeting_date')) or None,
            notes=_clean(request.POST.get('notes')) or '',
            generated_by=request.user,
        )
        return JsonResponse({'status': 'success', 'report': serialize_meeting_minutes(obj)}, status=201)
    except Exception as e:
        logger.exception('meeting minutes upload failed')
        return JsonResponse({'error': str(e)}, status=500)


@require_GET
def api_meeting_minutes_download(request, report_id):
    try:
        obj = MeetingMinutes.objects.get(pk=report_id)
    except MeetingMinutes.DoesNotExist:
        return JsonResponse({'error': 'Minutes haijapatikana'}, status=404)
    return _file_download_response(obj)


@login_required
@require_http_methods(['DELETE'])
def api_meeting_minutes_delete(request, report_id):
    denied = _upload_permission_denied(request)
    if denied:
        return denied
    try:
        obj = MeetingMinutes.objects.get(pk=report_id)
    except MeetingMinutes.DoesNotExist:
        return JsonResponse({'error': 'Minutes haijapatikana'}, status=404)
    delete_meeting_minutes(obj)
    return JsonResponse({'status': 'success', 'message': 'Minutes zimefutwa'})


@require_GET
def api_report_download(request, report_id):
    """Pakua PDF ya ripoti."""
    try:
        report = PlanningReport.objects.get(pk=report_id)
    except PlanningReport.DoesNotExist:
        return JsonResponse({'error': 'Ripoti haijapatikana'}, status=404)

    if not report.file_path or not default_storage.exists(report.file_path):
        abs_path = report.file_path
        if abs_path and os.path.isfile(abs_path):
            return FileResponse(
                open(abs_path, 'rb'),
                content_type='application/pdf',
                as_attachment=True,
                filename=report.original_filename,
            )
        return JsonResponse({'error': 'Faili haijapatikana'}, status=404)

    file_handle = default_storage.open(report.file_path, 'rb')
    return FileResponse(
        file_handle,
        content_type='application/pdf',
        as_attachment=True,
        filename=report.original_filename,
    )


@require_GET
def api_ccro_landowners(request):
    """Orodha ya wamiliki kutoka sifa za shapefile (planning_parcels)."""
    region = _clean(request.GET.get('region'))
    district = _clean(request.GET.get('district'))
    ward = _clean(request.GET.get('ward'))
    village = _clean(request.GET.get('village'))
    gender = _clean(request.GET.get('gender'))
    age_category = _clean(request.GET.get('age_category'))
    identified = _clean(request.GET.get('identified'))
    search = _clean(request.GET.get('search'))

    flt = _location_filter(region, district, ward, village)
    qs = PlanningParcel.objects.filter(flt).order_by('village_name', 'parcel_number')

    if gender:
        qs = qs.filter(owner_gender__iexact=gender)
    if age_category:
        qs = qs.filter(owner_age_category__iexact=age_category)
    if identified is not None:
        if identified.lower() in ('true', '1', 'yes', 'imetambuliwa'):
            qs = qs.filter(is_identified=True)
        elif identified.lower() in ('false', '0', 'no', 'haijatambuliwa'):
            qs = qs.filter(is_identified=False)
    if search:
        search_q = Q()
        for field in CCRO_SEARCH_FIELDS:
            search_q |= Q(**{f'{field}__icontains': search})
        qs = qs.filter(search_q)

    total = qs.count()
    page = max(1, int(request.GET.get('page', 1)))
    show_all = _clean(request.GET.get('all')) in ('1', 'true', 'yes')
    if show_all:
        page_size = min(10000, total) or 1
        page = 1
    else:
        page_size = min(5000, max(1, int(request.GET.get('page_size', 50))))
    start = (page - 1) * page_size
    items = [serialize_ccro_landowner(p) for p in qs[start:start + page_size]]

    return JsonResponse({
        'status': 'success',
        'count': len(items),
        'total': total,
        'page': page,
        'page_size': page_size,
        'total_pages': (total + page_size - 1) // page_size if total else 0,
        'data_source': 'planning_parcels',
        'sources': parcel_source_summary(qs),
        'landowners': items,
    })
