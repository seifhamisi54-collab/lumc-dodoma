# Generated manually — remove Maandalizi ya Jukwaa la Wadau category

from django.db import migrations, models


def reassign_stakeholder_platform(apps, schema_editor):
    Stakeholder = apps.get_model('wadau', 'Stakeholder')
    Stakeholder.objects.filter(category='stakeholder_platform').update(
        category='public_institutions',
    )


def noop_reverse(apps, schema_editor):
    # Cannot restore original categories after merge.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('wadau', '0003_stakeholder_category'),
    ]

    operations = [
        migrations.RunPython(reassign_stakeholder_platform, noop_reverse),
        migrations.AlterField(
            model_name='stakeholder',
            name='category',
            field=models.CharField(
                choices=[
                    ('planning_companies', 'Kampuni za Upangaji (Planning Companies)'),
                    ('ngos', 'NGOs — Local and International'),
                    ('higher_education', 'Taasisi za Elimu ya Juu (Higher Education Institutions)'),
                    ('financial_institutions', 'Taasisi za Kifedha (Financial Institutions)'),
                    ('public_institutions', 'Taasisi, Mashirika ya Umma (Institutions / Public Corporations)'),
                    ('sectoral_ministries', 'Wizara za Kisekta (Sectoral Ministries)'),
                ],
                db_index=True,
                default='public_institutions',
                max_length=40,
                verbose_name='Kundi la Wadau',
            ),
        ),
    ]
