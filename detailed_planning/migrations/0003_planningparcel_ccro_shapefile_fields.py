# Generated manually for Mpangokinaa1 mwande shapefile attributes

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('detailed_planning', '0002_remove_districtplanningboundary_created_by_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='planningparcel',
            name='pid',
            field=models.CharField(blank=True, db_index=True, max_length=50, null=True, verbose_name='PID'),
        ),
        migrations.AddField(
            model_name='planningparcel',
            name='claim_no',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='Claim No'),
        ),
        migrations.AddField(
            model_name='planningparcel',
            name='claim_date',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Tarehe (DATE_)'),
        ),
        migrations.AddField(
            model_name='planningparcel',
            name='paras',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='PARAS'),
        ),
        migrations.AddField(
            model_name='planningparcel',
            name='hamlet',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='HAMLET'),
        ),
        migrations.AddField(
            model_name='planningparcel',
            name='parties',
            field=models.TextField(blank=True, null=True, verbose_name='PARTIES'),
        ),
        migrations.AddField(
            model_name='planningparcel',
            name='neighbor_north',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Kaskazini'),
        ),
        migrations.AddField(
            model_name='planningparcel',
            name='neighbor_south',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Kusini'),
        ),
        migrations.AddField(
            model_name='planningparcel',
            name='neighbor_west',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Magharibi'),
        ),
        migrations.AddField(
            model_name='planningparcel',
            name='neighbor_east',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Mashariki'),
        ),
        migrations.AddField(
            model_name='planningparcel',
            name='spouse',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Wenza'),
        ),
        migrations.AddField(
            model_name='planningparcel',
            name='children',
            field=models.TextField(blank=True, null=True, verbose_name='Watoto'),
        ),
        migrations.AddField(
            model_name='planningparcel',
            name='others',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Wengineo'),
        ),
        migrations.AddField(
            model_name='planningparcel',
            name='kitongoji',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Kitongoji'),
        ),
        migrations.AddField(
            model_name='planningparcel',
            name='topography',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Topolijia'),
        ),
        migrations.AddField(
            model_name='planningparcel',
            name='season',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Majira ya'),
        ),
        migrations.AddField(
            model_name='planningparcel',
            name='right_of_way',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Haki ya Njia'),
        ),
        migrations.AddField(
            model_name='planningparcel',
            name='witness_1',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Shahidi 1'),
        ),
        migrations.AddField(
            model_name='planningparcel',
            name='witness_2',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Shahidi 2'),
        ),
        migrations.AddField(
            model_name='planningparcel',
            name='remarks',
            field=models.TextField(blank=True, null=True, verbose_name='Toa maoni'),
        ),
        migrations.AddField(
            model_name='planningparcel',
            name='shp_village',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='VILLAGE (SHP)'),
        ),
        migrations.AddField(
            model_name='planningparcel',
            name='land_title_name',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Jina la Ta'),
        ),
        migrations.AddField(
            model_name='planningparcel',
            name='land_use',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Matumizi ya ardhi'),
        ),
        migrations.AddField(
            model_name='planningparcel',
            name='ownership_type',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Umiliki'),
        ),
        migrations.AddField(
            model_name='planningparcel',
            name='source_layer',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Layer'),
        ),
        migrations.AddField(
            model_name='planningparcel',
            name='source_path',
            field=models.CharField(blank=True, max_length=500, null=True, verbose_name='Path'),
        ),
    ]
