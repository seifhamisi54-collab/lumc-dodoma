from django.contrib import admin

from locations.gazette_models import GazetteVillage
from locations.models import District, Region, Village, Ward


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    search_fields = ('name', 'code')
    list_display = ('name', 'code')


@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    search_fields = ('name', 'region__name')
    list_display = ('name', 'region', 'code')
    list_filter = ('region',)


@admin.register(Ward)
class WardAdmin(admin.ModelAdmin):
    search_fields = ('name', 'district__name')
    list_display = ('name', 'district', 'code')


@admin.register(Village)
class VillageAdmin(admin.ModelAdmin):
    search_fields = ('name', 'ward__name')
    list_display = ('name', 'ward', 'code')


@admin.register(GazetteVillage)
class GazetteVillageAdmin(admin.ModelAdmin):
    list_display = ('village_name', 'ward_name', 'district_name', 'region_name', 'unit_type')
    list_filter = ('region_name', 'unit_type')
    search_fields = ('village_name', 'ward_name', 'district_name', 'region_name')
