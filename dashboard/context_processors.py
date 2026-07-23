from django.conf import settings


def integration_urls(request):
    return {
        "GIS_PORTAL_URL": getattr(settings, "GIS_PORTAL_URL", "http://localhost:8000"),
    }
