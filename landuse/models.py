from django.db import models
from django.conf import settings
from locations.models import Region, District, Ward, Village
import uuid

class LandUseType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)
    color = models.CharField(max_length=20, default='#28a745')
    def __str__(self):
        return self.name

class LandUseRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    region = models.ForeignKey(Region, on_delete=models.CASCADE)
    district = models.ForeignKey(District, on_delete=models.CASCADE)
    ward = models.ForeignKey(Ward, on_delete=models.SET_NULL, null=True, blank=True)
    village = models.ForeignKey(Village, on_delete=models.SET_NULL, null=True, blank=True)
    landuse_type = models.ForeignKey(LandUseType, on_delete=models.CASCADE)
    area_hectares = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    survey_year = models.IntegerField()
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"{self.landuse_type.name} - {self.district.name} ({self.survey_year})"