from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Hakuna seed tena — orodha zimo kwenye jedwali moja (migogoro) kama choices'

    def handle(self, *args, **options):
        self.stdout.write(
            'Orodha za Migogoro sasa ni TextChoices kwenye jedwali moja: detailed_planning.migogoro'
        )
