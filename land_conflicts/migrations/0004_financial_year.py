from django.db import migrations, models


def backfill_fy(apps, schema_editor):
    LandConflictCase = apps.get_model('land_conflicts', 'LandConflictCase')
    LandConflictCase.objects.all().update(financial_year='2026/2027')


class Migration(migrations.Migration):

    dependencies = [
        ('land_conflicts', '0003_conflict_types_three'),
    ]

    operations = [
        migrations.AddField(
            model_name='landconflictcase',
            name='financial_year',
            field=models.CharField(
                db_index=True,
                default='2026/2027',
                help_text='Mfano: 2026/2027',
                max_length=9,
                verbose_name='Mwaka wa fedha',
            ),
        ),
        migrations.RunPython(backfill_fy, migrations.RunPython.noop),
    ]
