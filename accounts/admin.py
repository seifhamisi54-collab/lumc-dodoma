from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from accounts.models import CustomUser, SectionAccessConfig, UserRole


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'get_name_display')
    search_fields = ('name',)


@admin.register(SectionAccessConfig)
class SectionAccessConfigAdmin(admin.ModelAdmin):
    list_display = ('registration_code', 'login_code', 'updated_at')
    fields = ('registration_code', 'login_code', 'updated_at')
    readonly_fields = ('updated_at',)

    def has_add_permission(self, request):
        try:
            return not SectionAccessConfig.objects.exists()
        except Exception:
            return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CustomUser)
class CustomUserAdmin(DjangoUserAdmin):
    list_display = (
        'username', 'email', 'first_name', 'role',
        'assigned_region', 'assigned_district',
        'is_staff', 'is_active', 'is_superuser', 'date_joined',
    )
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'role', 'assigned_region')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'phone')
    ordering = ('-date_joined',)

    fieldsets = DjangoUserAdmin.fieldsets + (
        ('GIS Portal', {
            'fields': ('phone', 'role', 'assigned_region', 'assigned_district', 'profile_picture'),
        }),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ('GIS Portal', {
            'fields': ('phone', 'role', 'assigned_region', 'assigned_district'),
        }),
    )

    actions = ['activate_users', 'deactivate_users', 'make_gis_officer']

    @admin.action(description='Amilisha watumiaji waliochaguliwa')
    def activate_users(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description='Zima watumiaji waliochaguliwa')
    def deactivate_users(self, request, queryset):
        queryset.update(is_active=False)

    @admin.action(description='Weka jukumu GIS Officer')
    def make_gis_officer(self, request, queryset):
        role, _ = UserRole.objects.get_or_create(name='gis_officer')
        queryset.update(role=role)
