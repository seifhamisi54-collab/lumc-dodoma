from django.db import models
import uuid

# Re-export gazette master list (GN PDFs) for dropdowns
from locations.gazette_models import GazetteVillage  # noqa: E402,F401

class Region(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=5, unique=True)
    description = models.TextField(blank=True)
    boundary_geojson = models.JSONField(null=True, blank=True)
    center_lat = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    center_lon = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name

class District(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name='districts')
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10)
    population = models.BigIntegerField(null=True, blank=True)
    area_km2 = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    boundary_geojson = models.JSONField(null=True, blank=True)
    center_lat = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    center_lon = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['region', 'name']
    
    def __str__(self):
        return f"{self.name} - {self.region.name}"

class Ward(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    district = models.ForeignKey(District, on_delete=models.CASCADE, related_name='wards')
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=15)
    population = models.IntegerField(null=True, blank=True)
    boundary_geojson = models.JSONField(null=True, blank=True)
    center_lat = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    center_lon = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['district', 'name']
    
    def __str__(self):
        return f"{self.name} - {self.district.name}"

class Village(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ward = models.ForeignKey(Ward, on_delete=models.CASCADE, related_name='villages')
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    population = models.IntegerField(null=True, blank=True)
    households = models.IntegerField(null=True, blank=True)
    area_hectares = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    boundary_geojson = models.JSONField(null=True, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['ward', 'name']
    
    def __str__(self):
        return f"{self.name} - {self.ward.name}"