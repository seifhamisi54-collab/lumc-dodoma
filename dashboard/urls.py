from django.urls import path, include
from . import views
from . import system_admin_views as sysadmin

app_name = 'dashboard'

urlpatterns = [
    # =====================================================
    # PAGE VIEWS
    # =====================================================
    path('', views.home, name='home'),
    path('map/', views.map_view, name='map_view'),
    path('map/tools/', views.gis_tools_view, name='gis_tools'),
    path('landuse/', views.landuse_home, name='landuse_home'),
    path('data-portal/', views.data_portal, name='data_portal'),
    path('migogoro/', include('land_conflicts.urls')),
    path('system-admin/', sysadmin.system_admin_page, name='system_admin'),
    path('system-admin/unlock/', sysadmin.admin_unlock_page, name='admin_unlock'),
    
    # System Administration API
    path('api/system-admin/gate-status/', sysadmin.api_gate_status, name='api_admin_gate_status'),
    path('api/system-admin/unlock/', sysadmin.api_admin_unlock, name='api_admin_unlock'),
    path('api/system-admin/lock/', sysadmin.api_admin_lock, name='api_admin_lock'),
    path('api/system-admin/passcode/', sysadmin.api_admin_passcode, name='api_admin_passcode'),
    path('api/system-admin/passcode/reset/', sysadmin.api_admin_passcode_reset, name='api_admin_passcode_reset'),
    path('api/system-admin/overview/', sysadmin.api_admin_overview, name='api_admin_overview'),
    path('api/system-admin/roles/', sysadmin.api_roles_matrix, name='api_roles_matrix'),
    path('api/system-admin/users/', sysadmin.api_users, name='api_admin_users'),
    path('api/system-admin/users/<int:user_id>/', sysadmin.api_user_detail, name='api_admin_user_detail'),
    path('api/system-admin/currencies/', sysadmin.api_currencies, name='api_currencies'),
    path('api/system-admin/currencies/<uuid:item_id>/', sysadmin.api_currency_detail, name='api_currency_detail'),
    path('api/system-admin/localities/', sysadmin.api_localities, name='api_localities'),
    path('api/system-admin/localities/boundaries/', sysadmin.api_locality_boundaries, name='api_locality_boundaries'),
    path('api/system-admin/localities/upload-boundary/', sysadmin.api_locality_upload_boundary, name='api_locality_upload_boundary'),
    path('api/system-admin/localities/boundaries/<uuid:boundary_id>/', sysadmin.api_locality_delete_boundary, name='api_locality_delete_boundary'),
    path('api/system-admin/localities/<uuid:item_id>/', sysadmin.api_locality_detail, name='api_locality_detail'),
    path('api/system-admin/mpango-shapefiles/', sysadmin.api_org_mpango_shapefiles, name='api_org_mpango_shapefiles'),
    path('api/system-admin/mpango-shapefiles/upload/', sysadmin.api_org_mpango_shapefile_upload, name='api_org_mpango_shapefile_upload'),
    path('api/system-admin/mpango-shapefiles/delete/', sysadmin.api_org_mpango_shapefile_delete, name='api_org_mpango_shapefile_delete'),
    path('api/system-admin/designations/', sysadmin.api_designations, name='api_designations'),
    path('api/system-admin/designations/<uuid:item_id>/', sysadmin.api_designation_detail, name='api_designation_detail'),
    path('api/system-admin/forms/', sysadmin.api_forms, name='api_forms'),
    path('api/system-admin/forms/<uuid:item_id>/', sysadmin.api_form_detail, name='api_form_detail'),
    path('api/system-admin/ccro-config/', sysadmin.api_ccro_config, name='api_ccro_config'),
    path('api/system-admin/ccro-config/<uuid:item_id>/', sysadmin.api_ccro_config_detail, name='api_ccro_config_detail'),
    
    # =====================================================
    # DATA MANAGEMENT PAGES
    # =====================================================
    path('data/add-village/', views.add_village_data, name='add_village_data'),
    path('data/village/<str:village_id>/', views.village_data_detail, name='village_data_detail'),
    path('data/village/<str:village_id>/edit/', views.edit_village_data, name='edit_village_data'),
    path('data/village/<str:village_id>/delete/', views.delete_village_data, name='delete_village_data'),
    
    # =====================================================
    # UPLOAD PAGES
    # =====================================================
    path('upload/landuse/', views.upload_landuse_shapefile, name='upload_landuse_shapefile'),
    path('upload/village-boundary/', views.upload_village_boundary, name='upload_village_boundary'),
    path('upload/hamlet-boundary/', views.upload_hamlet_boundary, name='upload_hamlet_boundary'),
    path('upload/social-services/', views.upload_social_services, name='upload_social_services'),
    path('upload/parcels/', views.upload_parcels, name='upload_parcels'),
    path('upload/infrastructure/', views.upload_infrastructure, name='upload_infrastructure'),
    path('upload/cco-data/', views.upload_cco_data, name='upload_cco_data'),
    
    # =====================================================
    # DOWNLOAD PAGES
    # =====================================================
    path('download/shapefile/', views.download_shapefile, name='download_shapefile'),
    path('download/report/', views.download_report, name='download_report'),

    # Michango wakati wa kupakua data
    path('donation/lipa/<str:reference>/', views.donation_checkout, name='donation_checkout'),
    path('donation/imethibitishwa/<str:reference>/', views.donation_success, name='donation_success'),
    path('donation/pesapal-callback/', views.donation_pesapal_callback, name='donation_pesapal_callback'),
    path('api/donation/initiate/', views.api_donation_initiate, name='api_donation_initiate'),
    path('api/donation/lipa-demo/<str:reference>/', views.api_donation_pay_demo, name='api_donation_pay_demo'),
    
    # =====================================================
    # DETAIL VIEWS
    # =====================================================
    path('district/<str:district_id>/', views.district_detail, name='district_detail'),
    path('village/<str:village_id>/', views.village_detail, name='village_detail'),
    
    # =====================================================
    # API - DETAILED PLANNING (integrated into portals)
    # =====================================================
    path('api/planning/', include('detailed_planning.urls')),

    # =====================================================
    # API - CORE (Django Models)
    # =====================================================
    path('api/regions/', views.api_regions, name='api_regions'),
    path('api/region/<str:region_id>/', views.api_region_detail, name='api_region_detail'),
    path('api/region_geometry/<str:region_id>/', views.api_region_geometry, name='api_region_geometry'),
    path('api/region_boundary/<str:region_id>/', views.api_region_boundary, name='api_region_boundary'),
    path('api/district/<str:district_id>/', views.api_district_detail, name='api_district_detail'),
    path('api/ward/<str:ward_id>/', views.api_ward_detail, name='api_ward_detail'),
    
    # =====================================================
    # API - FOR DROPDOWNS (Returns names only)
    # =====================================================
    path('api/districts-by-region/<str:region>/', views.api_districts_by_region, name='api_districts_by_region'),
    path('api/wards-by-district/<str:region>/<str:district>/', views.api_wards_by_district, name='api_wards_by_district'),
    
    # =====================================================
    # API - DATA PORTAL (STATISTICS & VILLAGE DATA)
    # =====================================================
    path('api/dashboard-stats/', views.api_dashboard_stats, name='api_dashboard_stats'),
    path('api/village-data/', views.api_village_data_list, name='api_village_data_list'),
    path('api/village-data/<str:village_id>/', views.api_village_data_detail, name='api_village_data_detail'),
    path('api/village-data/<str:id>/delete/', views.delete_village_data_api, name='delete_village_data_api'),
    path('api/district-landuse-summary/', views.api_district_landuse_summary, name='api_district_landuse_summary'),
    
    # =====================================================
    # API - SOCIAL SERVICES, PARCELS, INFRASTRUCTURE
    # =====================================================
    path('api/social-services/', views.api_social_services, name='api_social_services'),
    path('api/parcels/', views.api_parcels, name='api_parcels'),
    path('api/infrastructure/', views.api_infrastructure, name='api_infrastructure'),
    
    # =====================================================
    # API - UPLOAD & EXPORT
    # =====================================================
    path('api/upload/pdf/', views.upload_pdf_api, name='upload_pdf_api'),
    path('api/upload/shapefile/', views.upload_shapefile_api, name='upload_shapefile_api'),
    path('api/tools/upload-layer/', views.api_tools_upload_layer, name='api_tools_upload_layer'),
    path('api/tools/topology-check/', views.api_tools_topology_check, name='api_tools_topology_check'),
    path('api/tools/clean/', views.api_tools_clean, name='api_tools_clean'),
    path('api/tools/edit-command/', views.api_tools_edit_command, name='api_tools_edit_command'),
    path('api/export/excel/landuse/', views.export_excel_landuse, name='export_excel_landuse'),
    path('api/export/<str:data_type>/<str:fmt>/', views.api_export_data, name='api_export_data'),
    path('api/download/village-data/<str:format>/', views.api_download_village_data, name='api_download_village_data'),
    path('api/download/<str:data_type>/<str:fmt>/', views.api_download_shapefile_by_filter, name='api_download_by_filter'),
    
    # =====================================================
    # API - FOR MAP BOUNDARIES (Returns GeoJSON for display)
    # =====================================================
    path('api/region-shapefile/<str:region_name>/', views.api_get_region_boundary_from_shapefile, name='api_region_shapefile'),
    path('api/district-boundaries/<str:region_name>/', views.api_get_district_boundaries, name='api_district_boundaries'),
    path('api/ward-boundaries/<str:region_name>/<str:district_name>/', views.api_get_ward_boundaries, name='api_ward_boundaries'),
    path('api/villages-by-ward/<str:region_name>/<str:district_name>/<str:ward_name>/', views.api_get_villages_by_ward_from_shapefile, name='api_villages_by_ward'),
    
    # =====================================================
    # API - ADDITIONAL
    # =====================================================
    path('api/generate-demo/', views.generate_demo_data, name='generate_demo_data'),
    path('api/check-database/', views.api_check_database, name='api_check_database'),
    path('api/landuse-trends/', views.api_landuse_trends, name='api_landuse_trends'),
    path('api/landuse/geojson/', views.api_landuse_geojson, name='api_landuse_geojson'),
    path('api/import-logs/', views.api_import_logs, name='api_import_logs'),
    
    # =====================================================
    # SHAPEFILE ALIASES (For backward compatibility)
    # =====================================================
    path('api/wards-by-district-shapefile/<str:region_name>/<str:district_name>/', views.api_get_wards_by_district_from_shapefile, name='api_wards_by_district_shapefile'),
]