import uuid
from datetime import date

from django.db import models


# Mwaka wa fedha Tanzania: Julai 1 → Juni 30
DEFAULT_FINANCIAL_YEAR = '2026/2027'
FY_START_YEAR = 2020
FY_YEARS_AHEAD = 15


def financial_year_from_date(value=None) -> str:
    """Rudisha FY kama 2026/2027 kutoka tarehe (Jul–Jun)."""
    d = value or date.today()
    if hasattr(d, 'year'):
        year, month = d.year, d.month
    else:
        try:
            parsed = date.fromisoformat(str(d)[:10])
            year, month = parsed.year, parsed.month
        except ValueError:
            return DEFAULT_FINANCIAL_YEAR
    if month >= 7:
        return f'{year}/{year + 1}'
    return f'{year - 1}/{year}'


def available_financial_years(extra=None) -> list[str]:
    """Orodha ya FY (kutoka hesabu + miaka iliyotumika kwenye kesi)."""
    years: set[str] = set()
    current = financial_year_from_date()
    try:
        current_start = int(current.split('/')[0])
    except (ValueError, IndexError):
        current_start = date.today().year
    end_start = max(
        current_start + FY_YEARS_AHEAD,
        int(DEFAULT_FINANCIAL_YEAR.split('/')[0]) + FY_YEARS_AHEAD,
    )
    for y in range(FY_START_YEAR, end_start + 1):
        years.add(f'{y}/{y + 1}')
    if extra:
        years |= set(extra)
    try:
        years |= set(
            LandConflictCase.objects.exclude(financial_year='')
            .values_list('financial_year', flat=True)
            .distinct()
        )
    except Exception:
        pass
    return sorted(years, reverse=True)


AVAILABLE_FINANCIAL_YEARS = []  # filled lazily via available_financial_years()


class LandConflictCase(models.Model):
    """Jedwali moja: Migogoro ya Ardhi (kesi zote + sehemu za orodha)."""

    class Status(models.TextChoices):
        OPEN = 'open', 'Wazi / bado haujatatuliwa'
        INVESTIGATING = 'investigating', 'Inachunguzwa'
        MEDIATION = 'mediation', 'Usuluhishi unaendelea'
        RESOLVED = 'resolved', 'Umetatuliwa'
        CLOSED = 'closed', 'Imefungwa'

    class ConflictType(models.TextChoices):
        VILLAGE_BOUNDARY = 'village_boundary', '1. Migogoro wa Mipaka wa Vijiji'
        FARMERS_PASTORALISTS = 'farmers_pastoralists', '2. Mgogoro wa Wakulima na Wafugaji'
        RESOURCES = 'resources', '3. Mgogoro wa Rasilimali'
        OTHER = 'other', '4. Mingineyo'

    class ConflictSource(models.TextChoices):
        UNCLEAR_BOUNDARY = 'unclear_boundary', 'Mipaka isiyoeleweka'
        NO_DOCUMENTS = 'no_documents', 'Ukosefu wa hati / usajili'
        INHERITANCE_DISPUTE = 'inheritance_dispute', 'Mgogoro wa urithi'
        LAND_GRABBING = 'land_grabbing', 'Kunyakua ardhi'
        POPULATION_PRESSURE = 'population_pressure', 'Msongamano wa watu'
        RESOURCE_COMPETITION = 'resource_competition', 'Ushindani wa rasilimali'
        RESETTLEMENT = 'resettlement', 'Uhamishaji / makazi mapya'
        INVESTOR_PROJECT = 'investor_project', 'Mradi wa uwekezaji'
        ADMIN_DECISION = 'admin_decision', 'Uamuzi wa utawala'
        OTHER = 'other', 'Chanzo kingine'

    class ResolutionMethod(models.TextChoices):
        MEDIATION = 'mediation', 'Usuluhishi wa kijamii'
        VILLAGE_COUNCIL = 'village_council', 'Baraza la Kijiji'
        WARD_TRIBUNAL = 'ward_tribunal', 'Baraza la Kata'
        DISTRICT_LAND = 'district_land', 'Ofisi ya Ardhi ya Wilaya'
        COURT = 'court', 'Mahakama'
        NEGOTIATION = 'negotiation', 'Majadiliano'
        SURVEY = 'survey', 'Upimaji / mipaka mpya'
        COMPENSATION = 'compensation', 'Fidia'
        OTHER = 'other', 'Nyingine'
        NONE = 'none', 'Bado hakuna'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case_number = models.CharField(max_length=40, unique=True, db_index=True)
    title = models.CharField(max_length=255, blank=True, default='')

    financial_year = models.CharField(
        max_length=9,
        default=DEFAULT_FINANCIAL_YEAR,
        db_index=True,
        verbose_name='Mwaka wa fedha',
    )

    conflict_type = models.CharField(
        max_length=40,
        choices=ConflictType.choices,
        default=ConflictType.VILLAGE_BOUNDARY,
        db_index=True,
    )
    conflict_type_other = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name='Aina nyingine (eleza)',
        help_text='Jaza ikiwa aina ni Mingineyo',
    )

    conflict_source = models.CharField(
        max_length=40,
        choices=ConflictSource.choices,
        default=ConflictSource.OTHER,
        db_index=True,
    )

    status = models.CharField(
        max_length=30, choices=Status.choices, default=Status.OPEN, db_index=True
    )
    is_resolved = models.BooleanField(default=False, db_index=True)

    region_name = models.CharField(max_length=100, blank=True, default='', db_index=True)
    district_name = models.CharField(max_length=100, blank=True, default='', db_index=True)
    ward_name = models.CharField(max_length=100, blank=True, default='', db_index=True)
    village_name = models.CharField(max_length=100, blank=True, default='', db_index=True)
    village_name_other = models.CharField(
        max_length=100,
        blank=True,
        default='',
        db_index=True,
    )

    complainant = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name='Mlalamikaji',
        help_text='Mfano: Ifunde',
    )
    respondent = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name='Mlalamikiwa',
        help_text='Mfano: Njaro',
    )
    description = models.TextField(blank=True, default='')

    started_date = models.DateField(null=True, blank=True, verbose_name='Tarehe mgogoro ulipoanzia')
    resolved_date = models.DateField(null=True, blank=True)
    filed_date = models.DateField(null=True, blank=True)

    resolution_method = models.CharField(
        max_length=40, choices=ResolutionMethod.choices, default=ResolutionMethod.NONE
    )
    resolution_details = models.TextField(blank=True, default='', verbose_name='Maelezo ya mbinu za utatuzi')
    unresolved_reason = models.TextField(
        blank=True, default='', verbose_name='Kwanini bado haujatatuliwa'
    )

    created_by_id = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='ID ya mtumiaji',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = '"detailed_planning"."migogoro"'
        ordering = ['-started_date', '-created_at']
        verbose_name = 'Mgogoro wa Ardhi'
        verbose_name_plural = 'Migogoro ya Ardhi'
        indexes = [
            models.Index(fields=['region_name', 'district_name', 'ward_name', 'village_name']),
            models.Index(fields=['financial_year', 'conflict_type']),
        ]

    def __str__(self):
        return f'{self.case_number} — {self.village_name or self.title or "Mgogoro"}'

    def get_conflict_type_display(self):
        if self.conflict_type == self.ConflictType.OTHER and self.conflict_type_other:
            return f'4. Mingineyo — {self.conflict_type_other}'
        return dict(self.ConflictType.choices).get(self.conflict_type, self.conflict_type)

    def get_conflict_source_display(self):
        return dict(self.ConflictSource.choices).get(self.conflict_source, self.conflict_source)

    def get_resolution_method_display(self):
        return dict(self.ResolutionMethod.choices).get(self.resolution_method, self.resolution_method)

    def parties_label(self) -> str:
        """Mfano: Ifunde - Njaro (kutoka Mlalamikaji na Mlalamikiwa)."""
        a = (self.complainant or '').strip()
        b = (self.respondent or '').strip()
        if a and b:
            return f'{a} - {b}'
        return a or b or ''

    def save(self, *args, **kwargs):
        self.is_resolved = self.status in (self.Status.RESOLVED, self.Status.CLOSED)
        if self.is_resolved and not self.resolution_method:
            self.resolution_method = self.ResolutionMethod.OTHER
        if not self.financial_year:
            self.financial_year = financial_year_from_date(self.started_date or self.filed_date)
        if self.conflict_type != self.ConflictType.OTHER:
            self.conflict_type_other = ''
        # Title kutoka Mlalamikaji - Mlalamikiwa (mfano: Ifunde - Njaro)
        label = self.parties_label()
        if label:
            self.title = label
        elif not self.title:
            type_label = self.get_conflict_type_display()
            parts = [type_label, self.village_name or self.ward_name or self.district_name]
            self.title = ' — '.join(p for p in parts if p)
        super().save(*args, **kwargs)
