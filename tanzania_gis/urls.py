import os

from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

# Import views from dashboard app
from dashboard import views as dashboard_views

urlpatterns = [
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