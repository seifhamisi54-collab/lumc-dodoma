from django.contrib import admin

from dashboard.models import (
    CcroConfigOption,
    Currency,
    Designation,
    Locality,
    SystemFormTemplate,
)


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'symbol', 'exchange_rate', 'is_default', 'is_active')
    list_filter = ('is_active', 'is_default')
    search_fields = ('code', 'name')


@admin.register(Locality)
class LocalityAdmin(admin.ModelAdmin):
    list_display = ('name', 'locality_type', 'region_name', 'district_name', 'is_active')
    list_filter = ('locality_type', 'is_active')
    search_fields = ('name', 'code', 'region_name', 'district_name')


@admin.register(Designation)
class DesignationAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'category', 'sort_order', 'is_active')
    list_filter = ('category', 'is_active')
    search_fields = ('name', 'code')


@admin.register(SystemFormTemplate)
class SystemFormTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'category', 'version', 'is_active')
    list_filter = ('category', 'is_active')
    search_fields = ('name', 'code')


@admin.register(CcroConfigOption)
class CcroConfigOptionAdmin(admin.ModelAdmin):
    list_display = ('category', 'value', 'label', 'sort_order', 'is_active')
    list_filter = ('category', 'is_active')
    search_fields = ('value', 'label')
