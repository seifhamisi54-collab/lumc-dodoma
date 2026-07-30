# Generated manually — Core System User Roles

from django.db import migrations, models


NEW_ROLES = [
    'section_head',
    'gis_officer',
    'data_management_officer',
    'land_dispute_officer',
]

# Old business role → new Core System role
LEGACY_MAP = {
    'admin': 'section_head',
    'manager': 'data_management_officer',
    'officer': 'gis_officer',
    'viewer': 'gis_officer',
}


def migrate_roles_forward(apps, schema_editor):
    UserRole = apps.get_model('accounts', 'UserRole')
    User = apps.get_model('accounts', 'CustomUser')

    role_by_name = {}
    for code in NEW_ROLES:
        obj, _ = UserRole.objects.get_or_create(name=code)
        role_by_name[code] = obj

    for old_code, new_code in LEGACY_MAP.items():
        old_role = UserRole.objects.filter(name=old_code).first()
        if not old_role:
            continue
        User.objects.filter(role_id=old_role.pk).update(role_id=role_by_name[new_code].pk)
        # Drop legacy role row (only if it is not somehow also a new code)
        if old_code not in NEW_ROLES:
            old_role.delete()

    # Any remaining unknown role codes → GIS Officer
    known = set(NEW_ROLES)
    for leftover in UserRole.objects.exclude(name__in=known):
        User.objects.filter(role_id=leftover.pk).update(role_id=role_by_name['gis_officer'].pk)
        leftover.delete()


def migrate_roles_backward(apps, schema_editor):
    UserRole = apps.get_model('accounts', 'UserRole')
    User = apps.get_model('accounts', 'CustomUser')

    reverse_map = {
        'section_head': 'admin',
        'data_management_officer': 'manager',
        'gis_officer': 'officer',
        'land_dispute_officer': 'viewer',
    }
    old_roles = ['admin', 'manager', 'officer', 'viewer']
    role_by_name = {}
    for code in old_roles:
        obj, _ = UserRole.objects.get_or_create(name=code)
        role_by_name[code] = obj

    for new_code, old_code in reverse_map.items():
        new_role = UserRole.objects.filter(name=new_code).first()
        if not new_role:
            continue
        User.objects.filter(role_id=new_role.pk).update(role_id=role_by_name[old_code].pk)
        if new_code not in old_roles:
            new_role.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_section_access_config'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userrole',
            name='name',
            field=models.CharField(
                choices=[
                    ('section_head', 'Section Head'),
                    ('gis_officer', 'GIS Officer'),
                    ('data_management_officer', 'Data Management Officer'),
                    ('land_dispute_officer', 'Land Dispute Officer'),
                ],
                max_length=50,
                unique=True,
            ),
        ),
        migrations.RunPython(migrate_roles_forward, migrate_roles_backward),
    ]
