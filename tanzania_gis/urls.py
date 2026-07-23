import os

from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse, JsonResponse
from django.views.generic import RedirectView

# Import views from dashboard app
from dashboard import views as dashboard_views


def healthz(_request):
    return HttpResponse("ok", content_type="text/plain")


def diag_auth(request):
    """Temporary live diagnosis — remove after fix. ?k=lumc-diag&u=gisadmin&p=..."""
    import os
    import traceback
    from django.contrib.auth import authenticate, login
    from django.contrib.auth import get_user_model

    if request.GET.get('k') != os.environ.get('DIAG_KEY', 'lumc-diag'):
        return JsonResponse({'error': 'forbidden'}, status=403)

    username = request.GET.get('u', 'gisadmin')
    password = request.GET.get('p', '')
    out = {'username': username, 'steps': []}
    try:
        User = get_user_model()
        out['steps'].append('user_model_ok')
        exists = User.objects.filter(username=username).exists()
        out['exists'] = exists
        out['steps'].append(f'exists={exists}')
        if exists:
            u = User.objects.get(username=username)
            out['is_active'] = u.is_active
            out['is_superuser'] = u.is_superuser
            out['check_password'] = u.check_password(password) if password else None
            out['steps'].append('check_password_done')
        user = authenticate(request, username=username, password=password) if password else None
        out['authenticate'] = bool(user)
        out['steps'].append(f'authenticate={bool(user)}')
        if user is not None:
            login(request, user)
            out['steps'].append('login_ok')
            out['session_key'] = request.session.session_key
        return JsonResponse(out)
    except Exception as exc:
        out['error'] = repr(exc)
        out['traceback'] = traceback.format_exc()
        return JsonResponse(out, status=500)


urlpatterns = [
    path('healthz/', healthz, name='healthz'),
    path('diag/auth/', diag_auth, name='diag_auth'),
    path('admin/', admin.site.urls),
    
    # Authentication URLs - using dashboard views
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('signup/', dashboard_views.signup_view, name='signup'),
    path('password_reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),
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