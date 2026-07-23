from django.db import migrations, models


def remap_conflict_types(apps, schema_editor):
    LandConflictCase = apps.get_model('land_conflicts', 'LandConflictCase')
    mapping = {
        'boundary': 'village_boundary',
        'encroachment': 'village_boundary',
        'ownership': 'village_boundary',
        'inheritance': 'village_boundary',
        'land_use': 'village_boundary',
        'multiple': 'village_boundary',
        'other': 'village_boundary',
        'investor': 'resources',
        'water': 'resources',
        'grazing': 'farmers_pastoralists',
    }
    for old, new in mapping.items():
        LandConflictCase.objects.filter(conflict_type=old).update(conflict_type=new)
    LandConflictCase.objects.exclude(
        conflict_type__in=['village_boundary', 'farmers_pastoralists', 'resources']
    ).update(conflict_type='village_boundary')


class Migration(migrations.Migration):

    dependencies = [
        ('land_conflicts', '0002_alter_landconflictcase_options_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='landconflictcase',
            name='conflict_type',
            field=models.CharField(
                choices=[
                    ('village_boundary', '1. Migogoro wa Mipaka wa Vijiji'),
                    ('farmers_pastoralists', '2. Mgogoro wa Wakulima na Wafugaji'),
                    ('resources', '3. Mgogoro wa Rasilimali'),
                ],
                db_index=True,
                default='village_boundary',
                max_length=40,
            ),
        ),
        migrations.RunPython(remap_conflict_types, migrations.RunPython.noop),
    ]
