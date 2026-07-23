# Generated manually for System Administration models

import uuid
from django.core.validators import MinValueValidator
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0005_download_donation'),
    ]

    operations = [
        migrations.CreateModel(
            name='Currency',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('code', models.CharField(max_length=10, unique=True, verbose_name='Msimbo')),
                ('name', models.CharField(max_length=100, verbose_name='Jina')),
                ('symbol', models.CharField(blank=True, default='', max_length=10, verbose_name='Alama')),
                ('exchange_rate', models.DecimalField(decimal_places=4, default=1, max_digits=14, validators=[MinValueValidator(0)], verbose_name='Kiwango dhidi ya TZS')),
                ('is_default', models.BooleanField(default=False, verbose_name='Chaguo-msingi')),
                ('is_active', models.BooleanField(default=True, verbose_name='Inatumika')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Sarafu',
                'verbose_name_plural': 'Sarafu',
                'ordering': ['code'],
            },
        ),
        migrations.CreateModel(
            name='Designation',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255, unique=True)),
                ('code', models.CharField(blank=True, default='', max_length=50)),
                ('category', models.CharField(blank=True, default='', max_length=100, verbose_name='Kategoria')),
                ('description', models.TextField(blank=True, default='')),
                ('is_active', models.BooleanField(default=True)),
                ('sort_order', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Cheo',
                'verbose_name_plural': 'Majina ya Kazi (Designation)',
                'ordering': ['sort_order', 'name'],
            },
        ),
        migrations.CreateModel(
            name='SystemFormTemplate',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('code', models.CharField(max_length=50, unique=True)),
                ('category', models.CharField(choices=[('ccro', 'CCRO'), ('vlup', 'VLUP / Mpango Kinaa'), ('general', 'Jumla'), ('report', 'Ripoti')], default='general', max_length=30)),
                ('description', models.TextField(blank=True, default='')),
                ('fields_schema', models.JSONField(blank=True, default=list, verbose_name='Muundo wa sehemu')),
                ('version', models.CharField(blank=True, default='1.0', max_length=20)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Fomu ya Mfumo',
                'verbose_name_plural': 'Fomu za Mfumo',
                'ordering': ['category', 'name'],
            },
        ),
        migrations.CreateModel(
            name='CcroConfigOption',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('category', models.CharField(choices=[('land_use', 'Matumizi ya Ardhi'), ('ownership_type', 'Aina ya Umiliki'), ('topography', 'Mkao wa Ardhi'), ('season', 'Msimu'), ('field_label', 'Lebo ya Sehemu')], db_index=True, max_length=50)),
                ('value', models.CharField(max_length=255)),
                ('label', models.CharField(blank=True, default='', max_length=255)),
                ('sort_order', models.PositiveIntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Chaguo la CCRO',
                'verbose_name_plural': 'Usimamizi wa CCRO',
                'ordering': ['category', 'sort_order', 'value'],
                'unique_together': {('category', 'value')},
            },
        ),
        migrations.CreateModel(
            name='Locality',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('locality_type', models.CharField(choices=[('region', 'Mkoa'), ('district', 'Wilaya'), ('ward', 'Kata'), ('village', 'Kijiji'), ('hamlet', 'Kitongoji'), ('office', 'Ofisi')], db_index=True, max_length=20)),
                ('name', models.CharField(db_index=True, max_length=255)),
                ('code', models.CharField(blank=True, default='', max_length=50)),
                ('region_name', models.CharField(blank=True, default='', max_length=255)),
                ('district_name', models.CharField(blank=True, default='', max_length=255)),
                ('ward_name', models.CharField(blank=True, default='', max_length=255)),
                ('is_active', models.BooleanField(default=True)),
                ('notes', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='children', to='dashboard.locality')),
            ],
            options={
                'verbose_name': 'Eneo',
                'verbose_name_plural': 'Maeneo (Locality)',
                'ordering': ['locality_type', 'name'],
            },
        ),
    ]
