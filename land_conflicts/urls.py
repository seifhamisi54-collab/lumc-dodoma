from django.urls import path

from . import views

app_name = 'land_conflicts'

urlpatterns = [
    path('', views.migogoro_portal, name='portal'),
    path('api/lookups/', views.api_lookups, name='api_lookups'),
    path('api/summary/', views.api_summary, name='api_summary'),
    path('api/cases/', views.api_cases, name='api_cases'),
    path('api/cases/<uuid:case_id>/', views.api_case_detail, name='api_case_detail'),
]
