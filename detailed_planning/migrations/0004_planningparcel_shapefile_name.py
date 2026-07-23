from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('detailed_planning', '0003_planningparcel_ccro_shapefile_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='planningparcel',
            name='shapefile_name',
            field=models.CharField(blank=True, max_length=500, null=True, verbose_name='Jina la shapefile'),
        ),
    ]
