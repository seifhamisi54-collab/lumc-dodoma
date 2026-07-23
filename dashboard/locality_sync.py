"""Sync Locality records kutoka majina ya mipaka (Wilaya / Kata)."""
from __future__ import annotations

from dashboard.models import Locality


def sync_locality_from_names(
    *,
    level: str,
    region: str,
    district: str,
    ward: str | None = None,
) -> Locality | None:
    """Hakikisha Locality ya wilaya/kata ipo baada ya pakia mipaka."""
    region = (region or '').strip()
    district = (district or '').strip()
    ward = (ward or '').strip() if ward else ''
    if level == 'district' and district:
        obj = Locality.objects.filter(
            locality_type='district',
            name__iexact=district,
            region_name__iexact=region,
        ).first()
        if not obj:
            obj = Locality.objects.filter(
                locality_type='district',
                name__iexact=district,
            ).first()
        if obj:
            obj.region_name = region or obj.region_name
            obj.district_name = district
            obj.is_active = True
            obj.save(update_fields=['region_name', 'district_name', 'is_active', 'updated_at'])
            return obj
        return Locality.objects.create(
            locality_type='district',
            name=district,
            region_name=region,
            district_name=district,
            is_active=True,
        )
    if level == 'ward' and ward and district:
        obj = Locality.objects.filter(
            locality_type='ward',
            name__iexact=ward,
            district_name__iexact=district,
        ).first()
        if obj:
            obj.region_name = region or obj.region_name
            obj.ward_name = ward
            obj.district_name = district
            obj.is_active = True
            obj.save(update_fields=['region_name', 'ward_name', 'district_name', 'is_active', 'updated_at'])
            return obj
        return Locality.objects.create(
            locality_type='ward',
            name=ward,
            region_name=region,
            district_name=district,
            ward_name=ward,
            is_active=True,
        )
    return None
