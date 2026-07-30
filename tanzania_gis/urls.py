import os

from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse
from django.views.generic import RedirectView

# Import views from dashboard app
from dashboard import views as dashboard_views
from accounts import views as accounts_views
from accounts.forms import SectionLoginForm


def healthz(_request):
    return HttpResponse("ok", content_type="text/plain")


def robots_txt(_request):
    body = "\n".join([
        "User-agent: *",
        "Allow: /login/",
        "Allow: /map/",
        "Allow: /static/",
        "Disallow: /admin/",
        "Disallow: /system-admin/",
        "Disallow: /api/",
        "Sitemap: https://lumc-dodoma.onrender.com/sitemap.xml",
        "",
    ])
    return HttpResponse(body, content_type="text/plain")


def sitemap_xml(_request):
    urls = [
        ("https://lumc-dodoma.onrender.com/login/", "1.0", "weekly"),
        ("https://lumc-dodoma.onrender.com/map/", "0.8", "weekly"),
    ]
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for loc, priority, freq in urls:
        parts.append("  <url>")
        parts.append(f"    <loc>{loc}</loc>")
        parts.append(f"    <changefreq>{freq}</changefreq>")
        parts.append(f"    <priority>{priority}</priority>")
        parts.append("  </url>")
    parts.append("</urlset>")
    return HttpResponse("\n".join(parts), content_type="application/xml")


urlpatterns = [
    path('healthz/', healthz, name='healthz'),
    path('robots.txt', robots_txt, name='robots_txt'),
    path('sitemap.xml', sitemap_xml, name='sitemap_xml'),
    path('admin/', admin.site.urls),
    
    # Authentication URLs - using dashboard views
    path(
        'login/',
        auth_views.LoginView.as_view(
            template_name='login.html',
            authentication_form=SectionLoginForm,
        ),
        name='login',
    ),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('signup/', dashboard_views.signup_view, name='signup'),
    path('password_reset/', accounts_views.password_reset_view, name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    
    # Dashboard URLs
    path('', include('dashboard.urls')),
    # Legacy: redirect standalone UI to integrated Data Portal
    path('detailed-planning/', RedirectView.as_view(url='/data-portal/?tab=mpango', permanent=False)),
    path('detailed-planning/api/', include('detailed_planning.urls')),
]

# Media: DEBUG, or SERVE_MEDIA=1 (Render / containers without nginx)
_serve_media = settings.DEBUG or os.environ.get('SERVE_MEDIA', '').strip().lower() in (
    '1', 'true', 'yes', 'on',
)
if _serve_media:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)