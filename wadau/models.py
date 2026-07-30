import uuid

from django.db import models

from dashboard.financial_year import DEFAULT_FINANCIAL_YEAR, FY_MAX_LENGTH


class Stakeholder(models.Model):
    """Mdau / Stakeholder â€” orodha ya wadau wa mradi / eneo."""

    class StakeholderType(models.TextChoices):
        GOVERNMENT = 'government', 'Serikali / Ofisi'
        LOCAL_GOVERNMENT = 'local_government', 'Serikali za Mitaa'
        COMMUNITY = 'community', 'Jamii / Kijiji'
        NGO = 'ngo', 'NGO / Asasi'
        PRIVATE = 'private', 'Sekta Binafsi'
        ACADEMIC = 'academic', 'Taasisi ya Elimu'
        DONOR = 'donor', 'Mfadhili / Mshirika'
        OTHER = 'other', 'Mwingine'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, verbose_name='Jina')
    organization = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Shirika / Taasisi'
    )
    stakeholder_type = models.CharField(
        max_length=40,
        choices=StakeholderType.choices,
        default=StakeholderType.COMMUNITY,
        db_index=True,
        verbose_name='Aina ya Mdau',
    )
    phone = models.CharField(max_length=40, blank=True, default='', verbose_name='Simu')
    email = models.EmailField(blank=True, default='', verbose_name='Barua pepe')
    role = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Wajibu / Maslahi'
    )
    financial_year = models.CharField(
        max_length=FY_MAX_LENGTH,
        default=DEFAULT_FINANCIAL_YEAR,
        db_index=True,
        verbose_name='Mwaka wa fedha',
    )

    region_name = models.CharField(max_length=100, blank=True, default='', db_index=True)
    district_name = models.CharField(max_length=100, blank=True, default='', db_index=True)
    ward_name = models.CharField(max_length=100, blank=True, default='', db_index=True)
    village_name = models.CharField(max_length=100, blank=True, default='', db_index=True)

    notes = models.TextField(blank=True, default='', verbose_name='Maelezo')
    is_active = models.BooleanField(default=True, db_index=True, verbose_name='Hai')

    created_by_id = models.IntegerField(null=True, blank=True, verbose_name='ID ya mtumiaji')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name', 'organization']
        verbose_name = 'Mdau'
        verbose_name_plural = 'Wadau'
        indexes = [
            models.Index(fields=['region_name', 'district_name', 'ward_name']),
            models.Index(fields=['financial_year']),
        ]

    def __str__(self):
        org = f' ({self.organization})' if self.organization else ''
        return f'{self.name}{org}'
