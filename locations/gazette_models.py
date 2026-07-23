"""Master list ya vijiji/mitaa kutoka gazeti za Mgawanyo wa Maeneo (GN)."""
import uuid

from django.db import models


class GazetteVillage(models.Model):
    """Kijiji au Mtaa — orodha rasmi kwa dropdown (mkoa → wilaya → kata → kijiji)."""

    class UnitType(models.TextChoices):
        VILLAGE = 'village', 'Kijiji'
        STREET = 'mtaa', 'Mtaa'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    region_name = models.CharField(max_length=100, db_index=True)
    district_name = models.CharField(max_length=150, db_index=True)
    ward_name = models.CharField(max_length=150, db_index=True)
    village_name = models.CharField(max_length=150, db_index=True)
    unit_type = models.CharField(
        max_length=20, choices=UnitType.choices, default=UnitType.VILLAGE
    )
    source_file = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'locations_gazette_village'
        verbose_name = 'Kijiji (Gazeti)'
        verbose_name_plural = 'Vijiji (Gazeti)'
        ordering = ['region_name', 'district_name', 'ward_name', 'village_name']
        constraints = [
            models.UniqueConstraint(
                fields=['region_name', 'district_name', 'ward_name', 'village_name'],
                name='uniq_gazette_village_hierarchy',
            ),
        ]
        indexes = [
            models.Index(fields=['region_name', 'district_name', 'ward_name']),
        ]

    def __str__(self):
        return f'{self.village_name} / {self.ward_name} / {self.district_name} / {self.region_name}'
