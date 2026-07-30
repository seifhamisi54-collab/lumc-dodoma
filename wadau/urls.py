from django.urls import path

from . import views

app_name = 'wadau'

urlpatterns = [
    path('', views.wadau_portal, name='portal'),
    path('api/stakeholders/', views.api_stakeholders, name='api_stakeholders'),
    path('api/stakeholders/<uuid:stakeholder_id>/', views.api_stakeholder_detail, name='api_stakeholder_detail'),
]
