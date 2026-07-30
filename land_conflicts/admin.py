from django.contrib import admin

from .models import LandConflictCase


@admin.register(LandConflictCase)
class LandConflictCaseAdmin(admin.ModelAdmin):
    list_display = (
        'case_number', 'financial_year', 'village_name', 'ward_name', 'district_name',
        'region_name', 'conflict_type', 'is_resolved', 'started_date', 'status',
    )
    list_filter = (
        'financial_year', 'is_resolved', 'status', 'conflict_type',
        'region_name',
    )
    search_fields = (
        'case_number', 'title', 'village_name', 'ward_name', 'district_name',
        'complainant', 'respondent', 'unresolved_reason', 'financial_year',
        'conflict_type_other', 'conflict_source', 'resolution_method',
    )
    readonly_fields = ('created_at', 'updated_at', 'is_resolved')
