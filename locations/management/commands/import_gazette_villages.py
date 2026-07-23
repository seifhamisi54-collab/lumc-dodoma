"""
Ingiza vijiji/mitaa kutoka PDF za gazeti.
Mfano:
  python manage.py import_gazette_villages --path "D:\\MFUMO LUMC\\Vijiji" --replace
"""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from locations.gazette_models import GazetteVillage
from locations.gazette_parser import parse_gazette_folder, parse_gazette_pdf
from locations.gazette_quality import is_clean_row


class Command(BaseCommand):
    help = 'Import Tanzania village/mtaa list from GN gazette PDFs into GazetteVillage'

    def add_arguments(self, parser):
        parser.add_argument(
            '--path',
            default=r'D:\MFUMO LUMC\Vijiji',
            help='Folder yenye PDF za vijiji',
        )
        parser.add_argument(
            '--replace',
            action='store_true',
            help='Futa orodha ya zamani kabla ya kuingiza',
        )
        parser.add_argument(
            '--file',
            default='',
            help='PDF moja pekee (hiari)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Onyesha idadi bila kuandika DB',
        )

    def handle(self, *args, **options):
        root = Path(options['path'])
        if not root.exists():
            raise CommandError(f'Path haipo: {root}')

        if options['file']:
            pdf = Path(options['file'])
            if not pdf.exists():
                pdf = root / options['file']
            if not pdf.exists():
                raise CommandError(f'PDF haipo: {options["file"]}')
            self.stdout.write(f'Inachanganua {pdf.name} ...')
            rows = parse_gazette_pdf(pdf)
        else:
            self.stdout.write(f'Inachanganua PDF kutoka {root} ...')
            rows = parse_gazette_folder(root)

        self.stdout.write(f'Imepatikana: {len(rows)} vijiji/mitaa (unique)')
        if not rows:
            raise CommandError('Hakuna data iliyotolewa kutoka PDF. Angalia pdfplumber / muundo.')

        by_region: dict[str, int] = {}
        for r in rows:
            by_region[r.region_name] = by_region.get(r.region_name, 0) + 1
        for name, count in sorted(by_region.items()):
            self.stdout.write(f'  {name}: {count}')

        if options['dry_run']:
            self.stdout.write(self.style.WARNING('Dry-run — hakuna kuandika DB'))
            return

        with transaction.atomic():
            if options['replace']:
                deleted, _ = GazetteVillage.objects.all().delete()
                self.stdout.write(f'Imefutwa zamani: {deleted}')

            existing = {
                (g.region_name.lower(), g.district_name.lower(), g.ward_name.lower(), g.village_name.lower())
                for g in GazetteVillage.objects.all().only(
                    'region_name', 'district_name', 'ward_name', 'village_name'
                )
            }
            to_create = []
            skipped = 0
            for r in rows:
                if not is_clean_row(r.region_name, r.district_name, r.ward_name, r.village_name):
                    skipped += 1
                    continue
                key = (
                    r.region_name.lower(),
                    r.district_name.lower(),
                    r.ward_name.lower(),
                    r.village_name.lower(),
                )
                if key in existing:
                    skipped += 1
                    continue
                existing.add(key)
                to_create.append(
                    GazetteVillage(
                        region_name=r.region_name,
                        district_name=r.district_name,
                        ward_name=r.ward_name,
                        village_name=r.village_name,
                        unit_type=r.unit_type,
                        source_file=r.source_file,
                    )
                )
            if to_create:
                GazetteVillage.objects.bulk_create(to_create, batch_size=1000)

        total = GazetteVillage.objects.count()
        self.stdout.write(self.style.SUCCESS(
            f'Imeingizwa {len(to_create)} mpya, zilirukwa {skipped}. Jumla DB: {total}'
        ))
