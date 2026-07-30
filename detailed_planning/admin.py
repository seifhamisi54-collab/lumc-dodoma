from django.contrib import admin

from django.contrib.gis.admin import GISModelAdmin



from .models import (

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





@admin.register(DistrictPlanningBoundary)

class DistrictPlanningBoundaryAdmin(GISModelAdmin):

    list_display = ('district_name', 'region_name', 'area_ha', 'updated_at')

    search_fields = ('region_name', 'district_name')





@admin.register(WardPlanningBoundary)

class WardPlanningBoundaryAdmin(GISModelAdmin):

    list_display = ('ward_name', 'district_name', 'region_name', 'area_ha', 'updated_at')

    search_fields = ('region_name', 'district_name', 'ward_name')





@admin.register(VillagePlanningBoundary)

class VillagePlanningBoundaryAdmin(GISModelAdmin):

    list_display = ('village_name', 'ward_name', 'district_name', 'region_name', 'area_ha')

    search_fields = ('region_name', 'district_name', 'ward_name', 'village_name')





@admin.register(VillageDetailedPlan)

class VillageDetailedPlanAdmin(admin.ModelAdmin):

    list_display = (

        'village_name', 'ward_name', 'district_name', 'region_name',

        'total_landowners', 'identified_parcels', 'unidentified_parcels', 'plan_status',

    )

    search_fields = ('region_name', 'district_name', 'ward_name', 'village_name')

    list_filter = ('plan_status', 'region_name')





@admin.register(PlanningParcel)

class PlanningParcelAdmin(GISModelAdmin):

    list_display = (

        'parcel_number', 'village_name', 'is_identified',

        'owner_name', 'claim_no', 'land_use', 'ownership_type', 'area_ha',

    )

    search_fields = (

        'parcel_number', 'village_name', 'owner_name', 'parties',

        'claim_no', 'pid', 'hamlet', 'kitongoji',

    )

    list_filter = ('is_identified', 'owner_gender', 'region_name', 'land_use', 'ownership_type')

    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (

        ('Eneo', {

            'fields': (

                'parcel_number', 'plot_sequence', 'region_name', 'district_name',

                'ward_name', 'village_name', 'geom', 'area_ha', 'village_plan',

            ),

        }),

        ('Mmiliki', {

            'fields': (

                'is_identified', 'owner_name', 'owner_gender', 'owner_age_category',

                'owner_is_landowner',

            ),

        }),

        ('CCRO / Mpangokinaa', {

            'fields': (

                'pid', 'claim_no', 'claim_date', 'paras', 'parties', 'hamlet', 'kitongoji',

                'land_use', 'ownership_type', 'land_title_name', 'spouse', 'children', 'others',

                'neighbor_north', 'neighbor_south', 'neighbor_west', 'neighbor_east',

                'topography', 'season', 'right_of_way', 'witness_1', 'witness_2', 'remarks',

                'shp_village', 'source_layer', 'source_path',

            ),

        }),

        ('Nyingine', {

            'fields': ('notes', 'created_by_id', 'created_at', 'updated_at'),

        }),

    )





@admin.register(PlanningShapefile)

class PlanningShapefileAdmin(GISModelAdmin):

    list_display = (

        'title', 'boundary_level', 'region_name', 'district_name',

        'ward_name', 'village_name', 'file_format', 'status', 'uploaded_at',

    )

    search_fields = ('title', 'region_name', 'district_name', 'ward_name', 'village_name', 'original_filename')

    list_filter = ('boundary_level', 'status', 'file_format')





@admin.register(PlanningReport)

class PlanningReportAdmin(admin.ModelAdmin):

    list_display = (

        'title', 'report_type', 'region_name', 'district_name',

        'ward_name', 'village_name', 'report_year', 'file_format', 'status', 'created_at',

    )

    search_fields = ('title', 'region_name', 'district_name', 'ward_name', 'village_name')

    list_filter = ('report_type', 'status', 'file_format', 'report_year')


@admin.register(QuarterReport)
class QuarterReportAdmin(admin.ModelAdmin):
    list_display = ('title', 'financial_year', 'quarter', 'original_filename', 'created_at')
    list_filter = ('financial_year', 'quarter', 'file_format')
    search_fields = ('title', 'notes', 'original_filename')
    readonly_fields = ('created_at', 'updated_at', 'created_by_id')


@admin.register(MeetingMinutes)
class MeetingMinutesAdmin(admin.ModelAdmin):
    list_display = ('title', 'financial_year', 'meeting_date', 'original_filename', 'created_at')
    list_filter = ('financial_year', 'file_format')
    search_fields = ('title', 'notes', 'original_filename')
    readonly_fields = ('created_at', 'updated_at', 'created_by_id')

