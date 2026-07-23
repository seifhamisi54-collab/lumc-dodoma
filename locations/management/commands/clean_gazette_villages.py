"""Futa impurities + rekebisha majina ya wilaya yaliyokatwa."""
from django.core.management.base import BaseCommand
from django.db import transaction

from locations.gazette_models import GazetteVillage
from locations.gazette_quality import (
    is_clean_row,
    is_impurity,
    normalize_name,
)


class Command(BaseCommand):
    help = 'Remove impure rows and normalize truncated district/ward/village names'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        dry = options['dry_run']
        total = GazetteVillage.objects.count()
        delete_ids = []
        updates = []

        for g in GazetteVillage.objects.iterator(chunk_size=1000):
            region = normalize_name(g.region_name, kind='region')
            district = normalize_name(g.district_name, kind='district')
            ward = normalize_name(g.ward_name, kind='ward')
            village = normalize_name(g.village_name, kind='village')

            if not is_clean_row(region, district, ward, village):
                delete_ids.append(g.id)
                continue

            if (
                region != g.region_name
                or district != g.district_name
                or ward != g.ward_name
                or village != g.village_name
            ):
                g.region_name = region
                g.district_name = district
                g.ward_name = ward
                g.village_name = village
                updates.append(g)

        self.stdout.write(f'Total: {total}')
        self.stdout.write(f'To delete: {len(delete_ids)}')
        self.stdout.write(f'To normalize: {len(updates)}')

        if dry:
            for s in GazetteVillage.objects.filter(id__in=delete_ids[:25]):
                self.stdout.write(
                    f'  DEL {s.region_name} | {s.district_name} | {s.ward_name} | {s.village_name}'
                )
            self.stdout.write(self.style.WARNING('Dry-run'))
            return

        with transaction.atomic():
            for i in range(0, len(delete_ids), 1000):
                GazetteVillage.objects.filter(id__in=delete_ids[i:i + 1000]).delete()
            if updates:
                GazetteVillage.objects.bulk_update(
                    updates,
                    ['region_name', 'district_name', 'ward_name', 'village_name'],
                    batch_size=500,
                )

        # Drop case-insensitive duplicates
        seen = set()
        dup_ids = []
        for g in GazetteVillage.objects.order_by('created_at').iterator():
            key = (
                g.region_name.lower(),
                g.district_name.lower(),
                g.ward_name.lower(),
                g.village_name.lower(),
            )
            if key in seen:
                dup_ids.append(g.id)
            else:
                seen.add(key)
        for i in range(0, len(dup_ids), 1000):
            GazetteVillage.objects.filter(id__in=dup_ids[i:i + 1000]).delete()

        remaining = GazetteVillage.objects.count()
        impure = 0
        samples = []
        for g in GazetteVillage.objects.iterator():
            if (
                is_impurity(g.district_name, kind='district')
                or is_impurity(g.ward_name, kind='ward')
                or is_impurity(g.village_name, kind='village')
            ):
                impure += 1
                if len(samples) < 20:
                    samples.append(
                        f'{g.region_name}|{g.district_name}|{g.ward_name}|{g.village_name}'
                    )

        self.stdout.write(self.style.SUCCESS(
            f'Remaining: {remaining}; dups removed: {len(dup_ids)}; impure left: {impure}'
        ))
        for s in samples:
            self.stdout.write(f'  still: {s}')
