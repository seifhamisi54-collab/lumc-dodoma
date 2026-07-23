"""Legacy helper — Migogoro sasa ni jedwali moja kwenye Detailed Planning DB."""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Migogoro tayari iko kwenye detailed_planning.migogoro'

    def handle(self, *args, **options):
        from land_conflicts.models import LandConflictCase

        self.stdout.write(
            f'Jedwali: detailed_planning.migogoro | kesi={LandConflictCase.objects.count()}'
        )
