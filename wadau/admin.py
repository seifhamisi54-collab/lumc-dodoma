from django.contrib import admin

from .models import Stakeholder


@admin.register(Stakeholder)
class StakeholderAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'organization', 'financial_year', 'category', 'stakeholder_type',
        'phone', 'email', 'region_name', 'district_name', 'ward_name', 'is_active', 'updated_at',
    )
    list_filter = ('financial_year', 'category', 'stakeholder_type', 'is_active', 'region_name')
    search_fields = (
        'name', 'organization', 'phone', 'email', 'role', 'financial_year',
        'region_name', 'district_name', 'ward_name', 'village_name', 'notes',
    )
    readonly_fields = ('created_at', 'updated_at', 'created_by_id')
