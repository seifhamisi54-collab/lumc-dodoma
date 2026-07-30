from django.urls import path

from . import views

app_name = 'detailed_planning'

urlpatterns = [
    path('regions/', views.api_regions, name='api_regions'),
    path('districts/<str:region>/', views.api_districts, name='api_districts'),
    path('wards/<str:region>/<str:district>/', views.api_wards, name='api_wards'),
    path('villages/<str:region>/<str:district>/<str:ward>/', views.api_villages, name='api_villages'),
    path('stats/', views.api_stats, name='api_stats'),
    path('region-boundary/<str:region>/', views.api_region_boundary, name='api_region_boundary'),
    path('district-boundaries/<str:region>/', views.api_district_boundaries, name='api_district_boundaries'),
    path('ward-boundaries/<str:region>/<str:district>/', views.api_ward_boundaries, name='api_ward_boundaries'),
    path('boundary/', views.api_boundary, name='api_boundary'),
    path('parcels/', views.api_parcels, name='api_parcels'),
    path('parcels/geojson/', views.api_parcels_geojson, name='api_parcels_geojson'),
    path('upload-shapefile/', views.api_upload_shapefile, name='api_upload_shapefile'),
    path('parcels/create/', views.api_create_parcel, name='api_create_parcel'),
    path('parcels/generate/', views.api_generate_plot_numbers, name='api_generate_plot_numbers'),
    path('village-plans/', views.api_village_plans, name='api_village_plans'),
    path('village-plans/<uuid:plan_id>/', views.api_village_plan_detail, name='api_village_plan_detail'),
    path('reports/', views.api_reports, name='api_reports'),
    path('reports/upload/', views.api_report_upload, name='api_report_upload'),
    path('reports/<uuid:report_id>/download/', views.api_report_download, name='api_report_download'),
    path('reports/<uuid:report_id>/', views.api_report_delete, name='api_report_delete'),
    path('quarter-reports/', views.api_quarter_reports, name='api_quarter_reports'),
    path('quarter-reports/upload/', views.api_quarter_report_upload, name='api_quarter_report_upload'),
    path('quarter-reports/<uuid:report_id>/download/', views.api_quarter_report_download, name='api_quarter_report_download'),
    path('quarter-reports/<uuid:report_id>/', views.api_quarter_report_delete, name='api_quarter_report_delete'),
    path('meeting-minutes/', views.api_meeting_minutes, name='api_meeting_minutes'),
    path('meeting-minutes/upload/', views.api_meeting_minutes_upload, name='api_meeting_minutes_upload'),
    path('meeting-minutes/<uuid:report_id>/download/', views.api_meeting_minutes_download, name='api_meeting_minutes_download'),
    path('meeting-minutes/<uuid:report_id>/', views.api_meeting_minutes_delete, name='api_meeting_minutes_delete'),
    path('shapefiles/', views.api_shapefiles, name='api_shapefiles'),
    path('shapefiles/parcels/', views.api_parcel_shapefiles, name='api_parcel_shapefiles'),
    path('shapefiles/parcel/', views.api_shapefile_delete_parcel, name='api_shapefile_delete_parcel'),
    path('shapefiles/landuse/', views.api_shapefile_delete_landuse, name='api_shapefile_delete_landuse'),
    path('shapefiles/boundary/<uuid:boundary_id>/', views.api_shapefile_delete_boundary, name='api_shapefile_delete_boundary'),
    path('shapefiles/<uuid:shapefile_id>/', views.api_shapefile_delete, name='api_shapefile_delete'),
    path('ccro/landowners/', views.api_ccro_landowners, name='api_ccro_landowners'),
]
