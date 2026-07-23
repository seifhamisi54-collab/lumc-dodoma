from django.db import models
from django.contrib.gis.db import models as gis_models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth import get_user_model
import uuid
from datetime import datetime

User = get_user_model()

# =====================================================
# TANZANIA ADMINISTRATIVE (Existing table - no changes)
# =====================================================

class TanzaniaAdministrative(gis_models.Model):
    """Existing table - don't modify"""
    region_nam = models.CharField(max_length=100, db_index=True)
    district_n = models.CharField(max_length=100, db_index=True, null=True, blank=True)
    ward_name = models.CharField(max_length=100, db_index=True, null=True, blank=True)
    vil_mtaa_n = models.CharField(max_length=100, null=True, blank=True)
    geom = gis_models.MultiPolygonField(srid=32736, null=True, blank=True)
    
    class Meta:
        db_table = '"boundaries"."tanzania_administrative"'
        managed = False
    
    def __str__(self):
        return f"{self.district_n} - {self.ward_name}"


# =====================================================
# BASE ABSTRACT MODEL (Kwa kuepuka kurudia fields)
# =====================================================

class BaseSpatialModel(gis_models.Model):
    """Abstract base model for all spatial data"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, verbose_name="Jina", db_index=True)
    ward_name = models.CharField(max_length=255, verbose_name="Jina la Kata", db_index=True)
    district_name = models.CharField(max_length=255, verbose_name="Jina la Wilaya", db_index=True)
    region_name = models.CharField(max_length=255, verbose_name="Jina la Mkoa", db_index=True)
    geom = gis_models.MultiPolygonField(srid=32736, null=True, blank=True)
    geom_point = gis_models.PointField(srid=32736, null=True, blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['region_name', 'district_name', 'ward_name']),
            models.Index(fields=['name']),
        ]
    
    @property
    def geometry(self):
        return self.geom or self.geom_point


# =====================================================
# VILLAGE BOUNDARY - ILIYOREKEBISHWA KWA DATABASE ILIYOPO
# =====================================================

class VillageBoundary(models.Model):
    """Village boundaries - INALINGANA NA DATABASE TABLE ILIYOPO"""
    
    # Hizi ndizo columns ZILIZOPO kwenye database yako (10 columns)
    id = models.CharField(max_length=255, primary_key=True, verbose_name="Kitambulisho")
    name = models.CharField(max_length=255, verbose_name="Jina la Kijiji", db_index=True, blank=True, null=True)
    ward_name = models.CharField(max_length=255, verbose_name="Jina la Kata", db_index=True, blank=True, null=True)
    district_name = models.CharField(max_length=255, verbose_name="Jina la Wilaya", db_index=True, blank=True, null=True)
    region_name = models.CharField(max_length=255, verbose_name="Jina la Mkoa", db_index=True, blank=True, null=True)
    sponsor = models.CharField(max_length=255, blank=True, null=True, verbose_name="Mfadhili")
    date_prepared = models.DateField(blank=True, null=True, verbose_name="Tarehe Iliyoandaliwa")
    date_end = models.DateField(blank=True, null=True, verbose_name="Tarehe ya Mwisho")
    status = models.CharField(max_length=100, blank=True, null=True, verbose_name="Hali")
    iv = models.TextField(blank=True, null=True, verbose_name="Maelezo ya Ziada")
    
    class Meta:
        db_table = '"landuse"."village_boundaries"'
        managed = False  # MUHIMU! Usiruhusu Django kubadilisha table
        verbose_name = 'Village Boundary'
        verbose_name_plural = 'Village Boundaries'
        indexes = [
            models.Index(fields=['region_name', 'district_name', 'ward_name']),
            models.Index(fields=['name']),
        ]
    
    def __str__(self):
        return self.name or f"Kijiji {self.id}"
    
    @property
    def plan_preparation_year(self):
        """Get year from date_prepared"""
        return self.date_prepared.year if self.date_prepared else None
    
    @property
    def plan_expiry_year(self):
        """Mwaka wa kuisha: date_end au mwaka wa kuandaa + 10."""
        if self.date_end:
            return self.date_end.year
        if self.date_prepared:
            return self.date_prepared.year + 10
        return None
    
    @property
    def plan_status(self):
        """Alias for status"""
        return self.status if self.status else 'not_prepared'
    
    @property
    def approval_status(self):
        """Alias for status"""
        return self.status if self.status else 'draft'


# =====================================================
# HAMLET BOUNDARY (Vitongoji)
# =====================================================

class HamletBoundary(gis_models.Model):
    """Hamlet/Sub-village/Mitaa boundaries"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, verbose_name="Jina la Mtaa/Hamlet", db_index=True)
    village_name = models.CharField(max_length=255, verbose_name="Jina la Kijiji", db_index=True)
    ward_name = models.CharField(max_length=255, verbose_name="Jina la Kata", db_index=True)
    district_name = models.CharField(max_length=255, verbose_name="Jina la Wilaya", db_index=True)
    region_name = models.CharField(max_length=255, verbose_name="Jina la Mkoa", db_index=True)
    geom = gis_models.MultiPolygonField(srid=32736, verbose_name="Geometry", null=True, blank=True)
    
    area_ha = models.FloatField(null=True, blank=True)
    population = models.IntegerField(null=True, blank=True)
    hamlet_code = models.CharField(max_length=50, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = '"landuse"."hamlet_boundaries"'
        managed = False
        verbose_name = 'Hamlet Boundary'
        indexes = [
            models.Index(fields=['region_name', 'district_name', 'ward_name', 'village_name']),
            models.Index(fields=['name']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.village_name}"


# =====================================================
# LAND USE DATA
# =====================================================

class LandUse(gis_models.Model):
    """Polygoni za matumizi ya ardhi — jedwali landuse.land_use (PostGIS)."""

    id = models.AutoField(primary_key=True)
    geom = gis_models.MultiPolygonField(srid=32736, null=True, blank=True)
    objectid = models.IntegerField(null=True, blank=True)
    area_ha = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    jina = models.CharField(max_length=255, blank=True, null=True)
    tumiz = models.CharField(max_length=255, blank=True, null=True)
    tumizi_2 = models.CharField(max_length=255, blank=True, null=True)
    ha_1 = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    acres_1 = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    kijiji = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    kata = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    wilaya = models.CharField(max_length=255, blank=True, null=True, db_index=True)

    class Meta:
        db_table = '"landuse"."land_use"'
        managed = False
        verbose_name = 'Land Use'
        verbose_name_plural = 'Land Use'

    def __str__(self):
        label = self.tumiz or self.jina or 'Matumizi'
        place = self.kijiji or self.kata or self.wilaya or ''
        return f"{label} — {place}".strip(' —')


# =====================================================
# SOCIAL SERVICES (Huduma za Kijamii)
# =====================================================

class SocialService(gis_models.Model):
    """Social services facilities"""
    
    SERVICE_CATEGORIES = [
        ('education', '📚 Elimu'),
        ('health', '🏥 Afya'),
        ('water', '💧 Maji'),
        ('market', '🛒 Masoko'),
        ('government', '🏛️ Serikali'),
        ('religious', '⛪ Dini'),
        ('sports', '⚽ Michezo'),
        ('security', '👮 Usalama'),
        ('infrastructure', '🏗️ Miundombinu'),
        ('other', '📌 Nyingine'),
    ]
    
    SERVICE_TYPES = [
        ('school_primary', 'Shule ya Msingi'),
        ('school_secondary', 'Shule ya Sekondari'),
        ('school_vocational', 'Shule ya Ufundi'),
        ('health_dispensary', 'Zahanati'),
        ('health_center', 'Kituo cha Afya'),
        ('health_hospital', 'Hospitali'),
        ('water_well', 'Kisima'),
        ('water_tap', 'Bomba la Maji'),
        ('water_dam', 'Bwawa'),
        ('market', 'Soko'),
        ('market_livestock', 'Soko la Mifugo'),
        ('government_office', 'Ofisi ya Serikali'),
        ('police', 'Kituo cha Polisi'),
        ('religious_church', 'Kanisa'),
        ('religious_mosque', 'Msikiti'),
        ('sports_field', 'Uwanja wa Michezo'),
        ('other', 'Nyingine'),
    ]
    
    CONDITION_CHOICES = [
        ('excellent', 'Nzuri Sana'),
        ('good', 'Nzuri'),
        ('average', 'Wastani'),
        ('poor', 'Dhaifu'),
        ('damaged', 'Imeharibika'),
        ('non_functional', 'Haifanyi Kazi'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, verbose_name="Jina la Huduma")
    service_category = models.CharField(max_length=50, choices=SERVICE_CATEGORIES, db_index=True)
    service_type = models.CharField(max_length=50, choices=SERVICE_TYPES, db_index=True)
    
    village_name = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    ward_name = models.CharField(max_length=255, db_index=True)
    district_name = models.CharField(max_length=255, db_index=True)
    region_name = models.CharField(max_length=255, db_index=True)
    
    geom_point = gis_models.PointField(srid=32736, null=True, blank=True)
    geom_polygon = gis_models.MultiPolygonField(srid=32736, null=True, blank=True)
    
    capacity = models.CharField(max_length=100, blank=True, null=True)
    condition = models.CharField(max_length=50, choices=CONDITION_CHOICES, default='average')
    year_established = models.IntegerField(null=True, blank=True)
    contact_person = models.CharField(max_length=255, blank=True, null=True)
    contact_phone = models.CharField(max_length=20, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    
    photo = models.ImageField(upload_to='social_services/', null=True, blank=True)
    document_pdf = models.FileField(upload_to='social_services_docs/', null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = '"landuse"."social_services"'
        managed = False
        verbose_name = 'Social Service'
        verbose_name_plural = 'Social Services'
        indexes = [
            models.Index(fields=['region_name', 'district_name', 'ward_name', 'service_category']),
            models.Index(fields=['service_type']),
        ]
    
    @property
    def geom(self):
        return self.geom_point or self.geom_polygon
    
    def __str__(self):
        return f"{self.get_service_type_display()} - {self.name}"


# =====================================================
# PARCELS / CCO PARCELS (Vipande vya Ardhi)
# =====================================================

class Parcel(gis_models.Model):
    """Land parcels / CCO managed parcels"""
    
    PARCEL_STATUS = [
        ('registered', 'Imesajiliwa ✅'),
        ('pending', 'Inaendelea ⏳'),
        ('disputed', 'Ina Mgogoro ⚠️'),
        ('reserved', 'Hifadhi 🛡️'),
        ('expired', 'Muda Umeisha ⏰'),
    ]
    
    LANDUSE_TYPES = [
        ('agriculture', 'Kilimo'),
        ('pasture', 'Malisho'),
        ('forest', 'Misitu'),
        ('conservation', 'Uhifadhi'),
        ('residential', 'Makazi'),
        ('commercial', 'Biashara'),
        ('other', 'Nyingine'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parcel_number = models.CharField(max_length=100, unique=True, db_index=True, verbose_name="Namba ya Kiwanja")
    owner_name = models.CharField(max_length=255, blank=True, null=True, verbose_name="Jina la Mmiliki")
    owner_id = models.CharField(max_length=100, blank=True, null=True, verbose_name="Kitambulisho cha Mmiliki")
    
    village_name = models.CharField(max_length=255, db_index=True)
    ward_name = models.CharField(max_length=255, db_index=True)
    district_name = models.CharField(max_length=255, db_index=True)
    region_name = models.CharField(max_length=255, db_index=True)
    
    geom = gis_models.MultiPolygonField(srid=32736, null=True, blank=True)
    area_ha = models.FloatField(null=True, blank=True, verbose_name="Eneo (Hekta)")
    
    landuse_type = models.CharField(max_length=50, choices=LANDUSE_TYPES, blank=True, null=True)
    status = models.CharField(max_length=50, choices=PARCEL_STATUS, default='registered')
    
    cco_name = models.CharField(max_length=255, blank=True, null=True, verbose_name="CCO Anayesimamia")
    cco_id = models.CharField(max_length=50, blank=True, null=True)
    
    registration_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    
    certificate_pdf = models.FileField(upload_to='parcel_certificates/', null=True, blank=True)
    survey_plan = models.FileField(upload_to='survey_plans/', null=True, blank=True)
    
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = '"landuse"."parcels"'
        managed = False
        verbose_name = 'Parcel'
        verbose_name_plural = 'Parcels'
        indexes = [
            models.Index(fields=['parcel_number']),
            models.Index(fields=['region_name', 'district_name', 'ward_name', 'village_name']),
            models.Index(fields=['cco_name', 'cco_id']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.parcel_number} - {self.village_name}"


# =====================================================
# INFRASTRUCTURE
# =====================================================

class Infrastructure(gis_models.Model):
    """Infrastructure facilities"""
    
    INFRA_CHOICES = [
        ('road', '🛣️ Barabara'),
        ('bridge', '🌉 Daraja'),
        ('electricity', '⚡ Umeme'),
        ('telecom', '📡 Mawasiliano'),
        ('railway', '🚂 Reli'),
        ('port', '⚓ Bandari'),
        ('airport', '✈️ Uwanja wa Ndege'),
        ('water_supply', '💧 Usambazaji Maji'),
        ('sewage', '🚽 Maji Taka'),
        ('other', '📌 Nyingine'),
    ]
    
    STATUS_CHOICES = [
        ('planned', 'Iliopangwa'),
        ('under_construction', 'Inajengwa'),
        ('operational', 'Inafanya Kazi'),
        ('damaged', 'Imeharibika'),
        ('non_functional', 'Haifanyi Kazi'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, verbose_name="Jina", db_index=True)
    infra_type = models.CharField(max_length=50, choices=INFRA_CHOICES, db_index=True)
    
    village_name = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    ward_name = models.CharField(max_length=255, db_index=True)
    district_name = models.CharField(max_length=255, db_index=True)
    region_name = models.CharField(max_length=255, db_index=True)
    
    geom_line = gis_models.LineStringField(srid=32736, null=True, blank=True)
    geom_point = gis_models.PointField(srid=32736, null=True, blank=True)
    geom_polygon = gis_models.MultiPolygonField(srid=32736, null=True, blank=True)
    
    length_km = models.FloatField(null=True, blank=True, verbose_name="Urefu (Km)")
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='operational')
    year_built = models.IntegerField(null=True, blank=True)
    condition = models.CharField(max_length=50, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = '"landuse"."infrastructure_facilities"'
        managed = False
        verbose_name = 'Infrastructure'
        indexes = [
            models.Index(fields=['region_name', 'district_name', 'ward_name', 'infra_type']),
            models.Index(fields=['status']),
        ]
    
    @property
    def geom(self):
        return self.geom_line or self.geom_point or self.geom_polygon
    
    def __str__(self):
        return f"{self.get_infra_type_display()} - {self.name}"


# =====================================================
# LAND USE REPORT (Statistics)
# =====================================================

class LandUseReport(models.Model):
    """Model for land use statistics"""
    
    village_name = models.CharField(max_length=255, db_index=True)
    ward_name = models.CharField(max_length=255, db_index=True)
    district_name = models.CharField(max_length=255, db_index=True)
    region_name = models.CharField(max_length=255, db_index=True)
    
    has_landuse_plan = models.BooleanField(default=False)
    landuse_plan_year = models.IntegerField(null=True, blank=True)
    plan_status = models.CharField(max_length=50, blank=True, null=True)
    approval_status = models.CharField(max_length=50, blank=True, null=True)
    
    agriculture_area_ha = models.FloatField(default=0)
    forest_area_ha = models.FloatField(default=0)
    urban_area_ha = models.FloatField(default=0)
    water_area_ha = models.FloatField(default=0)
    wetland_area_ha = models.FloatField(default=0)
    pasture_area_ha = models.FloatField(default=0)
    commercial_area_ha = models.FloatField(default=0)
    industrial_area_ha = models.FloatField(default=0)
    other_area_ha = models.FloatField(default=0)
    total_area_ha = models.FloatField(default=0)
    
    agriculture_percentage = models.FloatField(default=0)
    forest_percentage = models.FloatField(default=0)
    urban_percentage = models.FloatField(default=0)
    
    cco_count = models.IntegerField(default=0)
    cco_percentage = models.FloatField(default=0)
    
    population = models.IntegerField(default=0)
    households = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = '"landuse"."land_use_reports"'
        managed = False
        verbose_name = 'Land Use Report'
        indexes = [
            models.Index(fields=['region_name', 'district_name', 'ward_name']),
            models.Index(fields=['has_landuse_plan']),
        ]
    
    def __str__(self):
        return f"{self.village_name} - {self.district_name}"


# =====================================================
# CCO REPORT
# =====================================================

class CCOReport(models.Model):
    """CCO (Community Conservation Officer) records"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cco_id = models.CharField(max_length=50, unique=True, verbose_name="Kitambulisho cha CCO")
    cco_name = models.CharField(max_length=255, verbose_name="Jina la CCO")
    
    village_name = models.CharField(max_length=255, db_index=True)
    ward_name = models.CharField(max_length=255, db_index=True)
    district_name = models.CharField(max_length=255, db_index=True)
    region_name = models.CharField(max_length=255, db_index=True)
    
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    
    training_date = models.DateField(null=True, blank=True)
    certification_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    villages_covered = models.TextField(blank=True, null=True, help_text="Vijiji anavyosimamia (tenganisha kwa koma)")
    coverage_percentage = models.FloatField(default=0)
    
    certificate_pdf = models.FileField(upload_to='cco_certificates/', null=True, blank=True)
    photo = models.ImageField(upload_to='cco_photos/', null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = '"landuse"."cco_reports"'
        managed = False
        verbose_name = 'CCO Report'
        indexes = [
            models.Index(fields=['cco_id', 'cco_name']),
            models.Index(fields=['district_name', 'ward_name', 'village_name']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.cco_name} - {self.district_name}"


# =====================================================
# IMPORT LOGS
# =====================================================

class ImportLog(models.Model):
    """Track all imported files (shapefiles, excel, etc.)"""
    
    IMPORT_TYPES = [
        ('landuse', 'Land Use Shapefile'),
        ('village_boundary', 'Village Boundary Shapefile'),
        ('hamlet_boundary', 'Hamlet Boundary Shapefile'),
        ('social_services', 'Social Services Shapefile'),
        ('parcels', 'Parcels Shapefile'),
        ('infrastructure', 'Infrastructure Shapefile'),
        ('cco_data', 'CCO Excel Data'),
        ('other', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    import_type = models.CharField(max_length=50, choices=IMPORT_TYPES)
    filename = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)
    records_imported = models.IntegerField(default=0)
    records_updated = models.IntegerField(default=0)
    records_failed = models.IntegerField(default=0)
    
    status = models.CharField(max_length=50, choices=[
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('partial', 'Partial Success'),
    ], default='pending')
    
    error_message = models.TextField(blank=True, null=True)
    import_summary = models.JSONField(default=dict, blank=True, null=True)
    imported_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        db_column='imported_by',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = '"landuse"."import_logs"'
        managed = False
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_import_type_display()} - {self.filename} ({self.status})"


# =====================================================
# DOWNLOAD DONATION
# =====================================================

class DownloadDonation(models.Model):
    """Michango ya hiari wakati wa kupakua data."""

    CURRENCY_CHOICES = [
        ('TZS', 'Tanzanian Shilling (TSH)'),
        ('USD', 'US Dollar'),
    ]
    PAYMENT_METHOD_CHOICES = [
        ('card', 'Kadi (Card)'),
        ('merchant', 'Pay Merchant'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Inasubiri'),
        ('paid', 'Imelipwa'),
        ('failed', 'Imeshindwa'),
        ('cancelled', 'Imefutwa'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=32, unique=True, db_index=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='TZS')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    provider = models.CharField(max_length=30, blank=True, default='demo')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    provider_reference = models.CharField(max_length=255, blank=True, default='')

    download_data_type = models.CharField(max_length=50)
    download_format = models.CharField(max_length=30)
    download_region = models.CharField(max_length=255, blank=True, default='')
    download_district = models.CharField(max_length=255, blank=True, default='')
    download_ward = models.CharField(max_length=255, blank=True, default='')

    payer_name = models.CharField(max_length=255, blank=True, default='')
    payer_email = models.EmailField(blank=True, default='')
    payer_phone = models.CharField(max_length=30, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Mchango wa Kupakua'
        verbose_name_plural = 'Michango ya Kupakua'

    def __str__(self):
        return f'{self.reference} — {self.amount} {self.currency} ({self.status})'

    def download_url(self):
        from urllib.parse import urlencode
        params = {}
        if self.download_region:
            params['region'] = self.download_region
        if self.download_district:
            params['district'] = self.download_district
        if self.download_ward:
            params['ward'] = self.download_ward
        qs = ('?' + urlencode(params)) if params else ''
        return f'/api/export/{self.download_data_type}/{self.download_format}/{qs}'


# =====================================================
# SYSTEM ADMINISTRATION
# =====================================================

class Currency(models.Model):
    """Sarafu za mfumo — TZS, USD, n.k."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=10, unique=True, verbose_name='Msimbo')
    name = models.CharField(max_length=100, verbose_name='Jina')
    symbol = models.CharField(max_length=10, blank=True, default='', verbose_name='Alama')
    exchange_rate = models.DecimalField(
        max_digits=14, decimal_places=4, default=1,
        validators=[MinValueValidator(0)],
        verbose_name='Kiwango dhidi ya TZS',
    )
    is_default = models.BooleanField(default=False, verbose_name='Chaguo-msingi')
    is_active = models.BooleanField(default=True, verbose_name='Inatumika')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['code']
        verbose_name = 'Sarafu'
        verbose_name_plural = 'Sarafu'

    def __str__(self):
        return f'{self.code} — {self.name}'

    def save(self, *args, **kwargs):
        if self.is_default:
            Currency.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class Locality(models.Model):
    """Maeneo ya utawala / vituo vya kazi."""

    LOCALITY_TYPES = [
        ('region', 'Mkoa'),
        ('district', 'Wilaya'),
        ('ward', 'Kata'),
        ('village', 'Kijiji'),
        ('hamlet', 'Kitongoji'),
        ('office', 'Ofisi'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    locality_type = models.CharField(max_length=20, choices=LOCALITY_TYPES, db_index=True)
    name = models.CharField(max_length=255, db_index=True)
    code = models.CharField(max_length=50, blank=True, default='')
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL, related_name='children',
    )
    region_name = models.CharField(max_length=255, blank=True, default='')
    district_name = models.CharField(max_length=255, blank=True, default='')
    ward_name = models.CharField(max_length=255, blank=True, default='')
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['locality_type', 'name']
        verbose_name = 'Eneo'
        verbose_name_plural = 'Maeneo (Locality)'

    def __str__(self):
        return f'{self.get_locality_type_display()} — {self.name}'


class Designation(models.Model):
    """Cheo / jina la kazi."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    code = models.CharField(max_length=50, blank=True, default='')
    category = models.CharField(max_length=100, blank=True, default='', verbose_name='Kategoria')
    description = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name = 'Cheo'
        verbose_name_plural = 'Majina ya Kazi (Designation)'

    def __str__(self):
        return self.name


class SystemFormTemplate(models.Model):
    """Fomu za mfumo — CCRO, VLUP, n.k."""

    FORM_CATEGORIES = [
        ('ccro', 'CCRO'),
        ('vlup', 'VLUP / Mpango Kinaa'),
        ('general', 'Jumla'),
        ('report', 'Ripoti'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    category = models.CharField(max_length=30, choices=FORM_CATEGORIES, default='general')
    description = models.TextField(blank=True, default='')
    fields_schema = models.JSONField(default=list, blank=True, verbose_name='Muundo wa sehemu')
    version = models.CharField(max_length=20, blank=True, default='1.0')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category', 'name']
        verbose_name = 'Fomu ya Mfumo'
        verbose_name_plural = 'Fomu za Mfumo'

    def __str__(self):
        return f'{self.name} ({self.code})'


class CcroConfigOption(models.Model):
    """Chaguo za CCRO — matumizi ya ardhi, umiliki, n.k."""

    CATEGORIES = [
        ('land_use', 'Matumizi ya Ardhi'),
        ('ownership_type', 'Aina ya Umiliki'),
        ('topography', 'Mkao wa Ardhi'),
        ('season', 'Msimu'),
        ('field_label', 'Lebo ya Sehemu'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.CharField(max_length=50, choices=CATEGORIES, db_index=True)
    value = models.CharField(max_length=255)
    label = models.CharField(max_length=255, blank=True, default='')
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['category', 'sort_order', 'value']
        unique_together = [('category', 'value')]
        verbose_name = 'Chaguo la CCRO'
        verbose_name_plural = 'Usimamizi wa CCRO'

    def __str__(self):
        return f'{self.get_category_display()}: {self.label or self.value}'


class SystemSetting(models.Model):
    """Mipangilio ya mfumo (mf. passcode ya System Administration)."""

    key = models.CharField(max_length=100, unique=True, db_index=True)
    value = models.TextField(blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
    )

    class Meta:
        ordering = ['key']
        verbose_name = 'Mpangilio wa Mfumo'
        verbose_name_plural = 'Mipangilio ya Mfumo'

    def __str__(self):
        return self.key