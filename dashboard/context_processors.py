from django.conf import settings

from dashboard.financial_year import (
    DEFAULT_FINANCIAL_YEAR,
    suggested_financial_years,
    session_financial_year,
)


def integration_urls(request):
    return {
        "GIS_PORTAL_URL": getattr(settings, "GIS_PORTAL_URL", "http://localhost:8000"),
    }


def financial_year_context(request):
    """Mwaka wa fedha kwa moduli zote (session + mapendekezo)."""
    current = session_financial_year(request)
    extra = []
    try:
        from land_conflicts.models import LandConflictCase
        extra.extend(
            LandConflictCase.objects.exclude(financial_year='')
            .values_list('financial_year', flat=True)
            .distinct()[:50]
        )
    except Exception:
        pass
    try:
        from wadau.models import Stakeholder
        if hasattr(Stakeholder, 'financial_year'):
            extra.extend(
                Stakeholder.objects.exclude(financial_year='')
                .values_list('financial_year', flat=True)
                .distinct()[:50]
            )
    except Exception:
        pass
    try:
        from detailed_planning.schema_ensure import ensure_village_plans_schema
        ensure_village_plans_schema()
        from detailed_planning.models import VillageDetailedPlan
        if hasattr(VillageDetailedPlan, 'financial_year'):
            extra.extend(
                VillageDetailedPlan.objects.exclude(financial_year='')
                .values_list('financial_year', flat=True)
                .distinct()[:50]
            )
    except Exception:
        pass

    years = suggested_financial_years(extra=extra)
    if current not in years:
        years = [current] + years

    return {
        'default_financial_year': DEFAULT_FINANCIAL_YEAR,
        'current_financial_year': current,
        'financial_years': years,
    }
