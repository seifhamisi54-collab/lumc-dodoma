import uuid

from django.contrib.gis.db import models as gis_models
from django.db import models
from django.db.models import Q

from dashboard.financial_year import DEFAULT_FINANCIAL_YEAR, FY_MAX_LENGTH

GENDER_CHOICES = [
    ('M', 'Mwanaume'),
    ('F', 'Mwanamke'),
    ('U', 'Haijulikani'),
]

AGE_CATEGORY_CHOICES = [
    ('adult', 'Mtu mzima (18+)'),
    ('child', 'Mtoto (chini ya 18)'),
]


class DistrictPlanningBoundary(gis_models.Model):
    """Mipaka ya wilaya — schema detailed_planning."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    region_name = models.CharField(max_length=255, db_index=True, verbose_name='Mkoa')
    district_name = models.CharField(max_length=255, db_index=True, verbose_name='Wilaya')
    geom = gis_models.MultiPolygonField(srid=32736, null=True, blank=True)
    shapefile_name = models.CharField(max_length=500, blank=True, null=True)
    area_ha = models.FloatField(null=True, blank=True)
    created_by_id = models.IntegerField(null=True, blank=True, verbose_name='ID ya mtumiaji')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = '"detailed_planning"."district_boundaries"'
        verbose_name = 'Mipaka ya Wilaya'
        verbose_name_plural = 'Mipaka ya Wilaya'
        unique_together = [('region_name', 'district_name')]
        indexes = [
            models.Index(fields=['region_name', 'district_name']),
        ]

    def __str__(self):
        return f'{self.district_name} ({self.region_name})'


class WardPlanningBoundary(gis_models.Model):
    """Mipaka ya kata — schema detailed_planning."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    region_name = models.CharField(max_length=255, db_index=True, verbose_name='Mkoa')
    district_name = models.CharField(max_length=255, db_index=True, verbose_name='Wilaya')
    ward_name = models.CharField(max_length=255, db_index=True, verbose_name='Kata')
    geom = gis_models.MultiPolygonField(srid=32736, null=True, blank=True)
    shapefile_name = models.CharField(max_length=500, blank=True, null=True)
    area_ha = models.FloatField(null=True, blank=True)
    created_by_id = models.IntegerField(null=True, blank=True, verbose_name='ID ya mtumiaji')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = '"detailed_planning"."ward_boundaries"'
        verbose_name = 'Mipaka ya Kata'
        verbose_name_plural = 'Mipaka ya Kata'
        unique_together = [('region_name', 'district_name', 'ward_name')]
        indexes = [
            models.Index(fields=['region_name', 'district_name', 'ward_name']),
        ]

    def __str__(self):
        return f'{self.ward_name} — {self.district_name}'


class VillagePlanningBoundary(gis_models.Model):
    """Mipaka ya kijiji — schema detailed_planning."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    region_name = models.CharField(max_length=255, db_index=True, verbose_name='Mkoa')
    district_name = models.CharField(max_length=255, db_index=True, verbose_name='Wilaya')
    ward_name = models.CharField(max_length=255, db_index=True, verbose_name='Kata')
    village_name = models.CharField(max_length=255, db_index=True, verbose_name='Kijiji')
    geom = gis_models.MultiPolygonField(srid=32736, null=True, blank=True)
    shapefile_name = models.CharField(max_length=500, blank=True, null=True)
    area_ha = models.FloatField(null=True, blank=True)
    created_by_id = models.IntegerField(null=True, blank=True, verbose_name='ID ya mtumiaji')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = '"detailed_planning"."village_boundaries"'
        verbose_name = 'Mipaka ya Kijiji'
        verbose_name_plural = 'Mipaka ya Kijiji'
        unique_together = [('region_name', 'district_name', 'ward_name', 'village_name')]
        indexes = [
            models.Index(fields=['region_name', 'district_name', 'ward_name', 'village_name']),
        ]

    def __str__(self):
        return f'{self.village_name} — {self.ward_name}'


class VillageDetailedPlan(models.Model):
    """Takwimu za detailed planning kwa kijiji."""
    PLAN_STATUS = [
        ('draft', 'Rasimu'),
        ('prepared', 'Imeandaliwa'),
        ('approved', 'Imeidhinishwa'),
        ('completed', 'Imekamilika'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    region_name = models.CharField(max_length=255, db_index=True, verbose_name='Mkoa')
    district_name = models.CharField(max_length=255, db_index=True, verbose_name='Wilaya')
    ward_name = models.CharField(max_length=255, db_index=True, verbose_name='Kata')
    village_name = models.CharField(max_length=255, db_index=True, verbose_name='Kijiji')

    total_landowners = models.PositiveIntegerField(default=0, verbose_name='Waliomiliki (jumla)')
    female_landowners = models.PositiveIntegerField(default=0, verbose_name='Wanawake')
    male_landowners = models.PositiveIntegerField(default=0, verbose_name='Wanaume')
    children_under_18 = models.PositiveIntegerField(default=0, verbose_name='Watoto chini ya 18')
    identified_parcels = models.PositiveIntegerField(default=0, verbose_name='Viwanja vilivyotambuliwa')
    unidentified_parcels = models.PositiveIntegerField(default=0, verbose_name='Viwanja visivyotambuliwa')

    plan_status = models.CharField(max_length=50, choices=PLAN_STATUS, default='draft')
    plan_year = models.PositiveIntegerField(null=True, blank=True)
    financial_year = models.CharField(
        max_length=FY_MAX_LENGTH,
        default=DEFAULT_FINANCIAL_YEAR,
        blank=True,
        db_index=True,
        verbose_name='Mwaka wa fedha',
    )
    notes = models.TextField(blank=True, null=True)

    created_by_id = models.IntegerField(null=True, blank=True, verbose_name='ID ya mtumiaji')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = '"detailed_planning"."village_plans"'
        verbose_name = 'Mpango wa Kijiji'
        verbose_name_plural = 'Mipango ya Vijiji'
        unique_together = [('region_name', 'district_name', 'ward_name', 'village_name')]
        indexes = [
            models.Index(fields=['region_name', 'district_name', 'ward_name', 'village_name']),
        ]

    def __str__(self):
        return f'DP — {self.village_name}'

    def sync_parcel_counts(self, *, recalculate_identification: bool = False):
        from detailed_planning.services import apply_identification_to_parcel
        from dashboard.boundary_service import _district_search_names

        district_names = _district_search_names(self.district_name)
        parcels = PlanningParcel.objects.filter(
            region_name__iexact=self.region_name,
            ward_name__iexact=self.ward_name,
            village_name__iexact=self.village_name,
        )
        if district_names:
            district_q = Q()
            for name in district_names:
                district_q |= Q(district_name__iexact=name)
            parcels = parcels.filter(district_q)

        if recalculate_identification:
            for parcel in parcels.iterator():
                apply_identification_to_parcel(parcel, save=True)

        self.identified_parcels = parcels.filter(is_identified=True).count()
        self.unidentified_parcels = parcels.filter(is_identified=False).count()
        self.total_landowners = parcels.filter(owner_is_landowner=True).count()
        self.female_landowners = parcels.filter(owner_is_landowner=True, owner_gender='F').count()
        self.male_landowners = parcels.filter(owner_is_landowner=True, owner_gender='M').count()
        self.children_under_18 = parcels.filter(owner_is_landowner=True, owner_age_category='child').count()
        self.save(update_fields=[
            'identified_parcels', 'unidentified_parcels',
            'total_landowners', 'female_landowners', 'male_landowners', 'children_under_18',
            'updated_at',
        ])


class PlanningParcel(gis_models.Model):
    """Kiwanja cha detailed planning — namba inatengenezwa kiotomatiki."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parcel_number = models.CharField(max_length=100, unique=True, db_index=True, verbose_name='Namba ya Kiwanja')
    plot_sequence = models.PositiveIntegerField(default=0)

    region_name = models.CharField(max_length=255, db_index=True)
    district_name = models.CharField(max_length=255, db_index=True)
    ward_name = models.CharField(max_length=255, db_index=True)
    village_name = models.CharField(max_length=255, db_index=True)

    geom = gis_models.MultiPolygonField(srid=32736, null=True, blank=True)
    area_ha = models.FloatField(null=True, blank=True)

    is_identified = models.BooleanField(default=False, verbose_name='Imetambuliwa')
    owner_name = models.CharField(max_length=255, blank=True, null=True, verbose_name='Jina la Mmiliki')
    owner_gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True, null=True)
    owner_age_category = models.CharField(max_length=10, choices=AGE_CATEGORY_CHOICES, blank=True, null=True)
    owner_is_landowner = models.BooleanField(default=True, verbose_name='Ni mmiliki')

    village_plan = models.ForeignKey(
        VillageDetailedPlan,
        on_delete=models.CASCADE,
        related_name='parcels',
        null=True,
        blank=True,
    )

    notes = models.TextField(blank=True, null=True)
    created_by_id = models.IntegerField(null=True, blank=True, verbose_name='ID ya mtumiaji')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Sifa za CCRO / Mpangokinaa (kutoka shapefile)
    pid = models.CharField(max_length=50, blank=True, null=True, db_index=True, verbose_name='PID')
    claim_no = models.CharField(max_length=100, blank=True, null=True, verbose_name='Claim No')
    claim_date = models.CharField(max_length=50, blank=True, null=True, verbose_name='Tarehe (DATE_)')
    paras = models.CharField(max_length=255, blank=True, null=True, verbose_name='PARAS')
    hamlet = models.CharField(max_length=255, blank=True, null=True, verbose_name='HAMLET')
    parties = models.TextField(blank=True, null=True, verbose_name='PARTIES')
    neighbor_north = models.CharField(max_length=255, blank=True, null=True, verbose_name='Kaskazini')
    neighbor_south = models.CharField(max_length=255, blank=True, null=True, verbose_name='Kusini')
    neighbor_west = models.CharField(max_length=255, blank=True, null=True, verbose_name='Magharibi')
    neighbor_east = models.CharField(max_length=255, blank=True, null=True, verbose_name='Mashariki')
    spouse = models.CharField(max_length=255, blank=True, null=True, verbose_name='Wenza')
    children = models.TextField(blank=True, null=True, verbose_name='Watoto')
    others = models.CharField(max_length=255, blank=True, null=True, verbose_name='Wengineo')
    kitongoji = models.CharField(max_length=255, blank=True, null=True, verbose_name='Kitongoji')
    topography = models.CharField(max_length=255, blank=True, null=True, verbose_name='Topolijia')
    season = models.CharField(max_length=255, blank=True, null=True, verbose_name='Majira ya')
    right_of_way = models.CharField(max_length=255, blank=True, null=True, verbose_name='Haki ya Njia')
    witness_1 = models.CharField(max_length=255, blank=True, null=True, verbose_name='Shahidi 1')
    witness_2 = models.CharField(max_length=255, blank=True, null=True, verbose_name='Shahidi 2')
    remarks = models.TextField(blank=True, null=True, verbose_name='Toa maoni')
    shp_village = models.CharField(max_length=255, blank=True, null=True, verbose_name='VILLAGE (SHP)')
    land_title_name = models.CharField(max_length=255, blank=True, null=True, verbose_name='Jina la Ta')
    land_use = models.CharField(max_length=255, blank=True, null=True, verbose_name='Matumizi ya ardhi')
    ownership_type = models.CharField(max_length=255, blank=True, null=True, verbose_name='Umiliki')
    source_layer = models.CharField(max_length=255, blank=True, null=True, verbose_name='Layer')
    source_path = models.CharField(max_length=500, blank=True, null=True, verbose_name='Path')
    shapefile_name = models.CharField(max_length=500, blank=True, null=True, verbose_name='Jina la shapefile')

    class Meta:
        db_table = '"detailed_planning"."planning_parcels"'
        verbose_name = 'Kiwanja cha Mpango'
        verbose_name_plural = 'Viwanja vya Mpango'
        indexes = [
            models.Index(fields=['region_name', 'district_name', 'ward_name', 'village_name']),
            models.Index(fields=['is_identified']),
            models.Index(fields=['parcel_number']),
        ]

    def __str__(self):
        return self.parcel_number


BOUNDARY_LEVEL_CHOICES = [
    ('district', 'Wilaya'),
    ('ward', 'Kata'),
    ('village', 'Kijiji'),
    ('parcel', 'Kiwanja'),
    ('landuse', 'Matumizi ya Ardhi'),
    ('other', 'Nyingine'),
]

SHAPEFILE_FORMAT_CHOICES = [
    ('zip', 'ZIP (Shapefile)'),
    ('shp', 'SHP'),
    ('geojson', 'GeoJSON'),
    ('gpkg', 'GeoPackage'),
    ('kml', 'KML'),
]

SHAPEFILE_STATUS_CHOICES = [
    ('uploaded', 'Imepakiwa'),
    ('processed', 'Imeshughulikiwa'),
    ('failed', 'Imeshindwa'),
    ('archived', 'Imehifadhiwa'),
]


class PlanningShapefile(gis_models.Model):
    """Uhifadhi wa shapefile za detailed planning."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255, verbose_name='Kichwa')
    boundary_level = models.CharField(max_length=20, choices=BOUNDARY_LEVEL_CHOICES, db_index=True)
    region_name = models.CharField(max_length=255, db_index=True, verbose_name='Mkoa')
    district_name = models.CharField(max_length=255, blank=True, null=True, db_index=True, verbose_name='Wilaya')
    ward_name = models.CharField(max_length=255, blank=True, null=True, db_index=True, verbose_name='Kata')
    village_name = models.CharField(max_length=255, blank=True, null=True, db_index=True, verbose_name='Kijiji')
    original_filename = models.CharField(max_length=500, verbose_name='Jina la faili')
    stored_filename = models.CharField(max_length=500)
    file_path = models.CharField(max_length=1000, verbose_name='Njia ya faili')
    file_format = models.CharField(max_length=20, choices=SHAPEFILE_FORMAT_CHOICES, default='zip')
    file_size_bytes = models.BigIntegerField(null=True, blank=True)
    feature_count = models.PositiveIntegerField(null=True, blank=True)
    srid = models.IntegerField(default=32736)
    geom = gis_models.MultiPolygonField(srid=32736, null=True, blank=True)
    status = models.CharField(max_length=20, choices=SHAPEFILE_STATUS_CHOICES, default='uploaded')
    district_boundary = models.ForeignKey(
        DistrictPlanningBoundary, on_delete=models.SET_NULL, null=True, blank=True, related_name='shapefiles',
    )
    ward_boundary = models.ForeignKey(
        WardPlanningBoundary, on_delete=models.SET_NULL, null=True, blank=True, related_name='shapefiles',
    )
    village_boundary = models.ForeignKey(
        VillagePlanningBoundary, on_delete=models.SET_NULL, null=True, blank=True, related_name='shapefiles',
    )
    village_plan = models.ForeignKey(
        VillageDetailedPlan, on_delete=models.SET_NULL, null=True, blank=True, related_name='shapefiles',
    )
    notes = models.TextField(blank=True, null=True)
    uploaded_by_id = models.IntegerField(null=True, blank=True, verbose_name='ID ya mtumiaji')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = '"detailed_planning"."planning_shapefiles"'
        verbose_name = 'Shapefile ya Mpango'
        verbose_name_plural = 'Shapefile za Mpango'
        indexes = [
            models.Index(fields=['boundary_level']),
            models.Index(fields=['region_name', 'district_name', 'ward_name', 'village_name']),
        ]

    def __str__(self):
        return f'{self.title} ({self.boundary_level})'


REPORT_TYPE_CHOICES = [
    ('plan_summary', 'Muhtasari wa Mpango'),
    ('parcel_list', 'Orodha ya Viwanja'),
    ('boundary_map', 'Ramani ya Mipaka'),
    ('statistics', 'Takwimu'),
    ('quarter_report', 'Quarter Report'),
    ('section_minutes', 'Minutes za Vikao'),
    ('pdf', 'PDF'),
    ('excel', 'Excel'),
    ('other', 'Nyingine'),
]

REPORT_FORMAT_CHOICES = [
    ('pdf', 'PDF'),
    ('docx', 'Word'),
    ('xlsx', 'Excel'),
    ('csv', 'CSV'),
    ('html', 'HTML'),
]

REPORT_STATUS_CHOICES = [
    ('draft', 'Rasimu'),
    ('generated', 'Imetengenezwa'),
    ('approved', 'Imeidhinishwa'),
    ('archived', 'Imehifadhiwa'),
]


class PlanningReport(models.Model):
    """Ripoti za detailed planning — PDF, Excel, n.k."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255, verbose_name='Kichwa')
    report_type = models.CharField(max_length=30, choices=REPORT_TYPE_CHOICES, default='plan_summary', db_index=True)
    region_name = models.CharField(max_length=255, db_index=True, verbose_name='Mkoa')
    district_name = models.CharField(max_length=255, blank=True, null=True, db_index=True, verbose_name='Wilaya')
    ward_name = models.CharField(max_length=255, blank=True, null=True, db_index=True, verbose_name='Kata')
    village_name = models.CharField(max_length=255, blank=True, null=True, db_index=True, verbose_name='Kijiji')
    report_year = models.PositiveIntegerField(null=True, blank=True, verbose_name='Mwaka')
    original_filename = models.CharField(max_length=500, verbose_name='Jina la faili')
    stored_filename = models.CharField(max_length=500)
    file_path = models.CharField(max_length=1000, verbose_name='Njia ya faili')
    file_format = models.CharField(max_length=20, choices=REPORT_FORMAT_CHOICES, default='pdf')
    file_size_bytes = models.BigIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=REPORT_STATUS_CHOICES, default='generated')
    village_plan = models.ForeignKey(
        VillageDetailedPlan, on_delete=models.SET_NULL, null=True, blank=True, related_name='reports',
    )
    shapefile = models.ForeignKey(
        PlanningShapefile, on_delete=models.SET_NULL, null=True, blank=True, related_name='reports',
    )
    summary = models.TextField(blank=True, null=True, verbose_name='Muhtasari')
    notes = models.TextField(blank=True, null=True)
    generated_by_id = models.IntegerField(null=True, blank=True, verbose_name='ID ya mtumiaji')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = '"detailed_planning"."planning_reports"'
        verbose_name = 'Ripoti ya Mpango'
        verbose_name_plural = 'Ripoti za Mpango'
        indexes = [
            models.Index(fields=['report_type']),
            models.Index(fields=['region_name', 'district_name', 'ward_name', 'village_name']),
            models.Index(fields=['report_year']),
        ]

    def __str__(self):
        return f'{self.title} ({self.report_year or "—"})'


QUARTER_CHOICES = [
    ('Q1', 'Q1 (Jul–Sep)'),
    ('Q2', 'Q2 (Oct–Dec)'),
    ('Q3', 'Q3 (Jan–Mar)'),
    ('Q4', 'Q4 (Apr–Jun)'),
]


class QuarterReport(models.Model):
    """Quarter Report — ripoti za robo mwaka (jedwali maalum)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255, verbose_name='Kichwa')
    financial_year = models.CharField(
        max_length=32, default='2026/2027', db_index=True, verbose_name='Mwaka wa fedha',
    )
    quarter = models.CharField(
        max_length=2, choices=QUARTER_CHOICES, db_index=True, verbose_name='Robo',
    )
    notes = models.TextField(blank=True, default='', verbose_name='Maelezo')
    original_filename = models.CharField(max_length=500, verbose_name='Jina la faili')
    stored_filename = models.CharField(max_length=500)
    file_path = models.CharField(max_length=1000, verbose_name='Njia ya faili')
    file_format = models.CharField(max_length=20, choices=REPORT_FORMAT_CHOICES, default='pdf')
    file_size_bytes = models.BigIntegerField(null=True, blank=True)
    created_by_id = models.IntegerField(null=True, blank=True, verbose_name='ID ya mtumiaji')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = '"detailed_planning"."quarter_reports"'
        verbose_name = 'Quarter Report'
        verbose_name_plural = 'Quarter Reports'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['financial_year', 'quarter']),
        ]

    def __str__(self):
        return f'{self.title} ({self.financial_year} {self.quarter})'


class MeetingMinutes(models.Model):
    """Minutes za Vikao — kumbukumbu za mikutano (jedwali maalum)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255, verbose_name='Kichwa')
    financial_year = models.CharField(
        max_length=32, blank=True, default='', db_index=True, verbose_name='Mwaka wa fedha',
    )
    meeting_date = models.DateField(null=True, blank=True, db_index=True, verbose_name='Tarehe ya kikao')
    notes = models.TextField(blank=True, default='', verbose_name='Maelezo')
    original_filename = models.CharField(max_length=500, verbose_name='Jina la faili')
    stored_filename = models.CharField(max_length=500)
    file_path = models.CharField(max_length=1000, verbose_name='Njia ya faili')
    file_format = models.CharField(max_length=20, choices=REPORT_FORMAT_CHOICES, default='pdf')
    file_size_bytes = models.BigIntegerField(null=True, blank=True)
    created_by_id = models.IntegerField(null=True, blank=True, verbose_name='ID ya mtumiaji')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = '"detailed_planning"."meeting_minutes"'
        verbose_name = 'Minutes za Vikao'
        verbose_name_plural = 'Minutes za Vikao'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['financial_year', 'meeting_date']),
        ]

    def __str__(self):
        d = self.meeting_date.isoformat() if self.meeting_date else '—'
        return f'{self.title} ({d})'
