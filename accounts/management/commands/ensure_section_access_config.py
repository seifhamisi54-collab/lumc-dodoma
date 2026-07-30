"""
Sync SectionAccessConfig login/registration codes from env/settings.

  python manage.py ensure_section_access_config
  python manage.py ensure_section_access_config --no-force   # only fill blanks
"""
from django.core.management.base import BaseCommand

from accounts.models import SectionAccessConfig


class Command(BaseCommand):
    help = 'Ensure SectionAccessConfig codes match LUMC_LOGIN_CODE / LUMC_REGISTRATION_CODE'

    def add_arguments(self, parser):
        parser.add_argument(
            '--no-force',
            action='store_true',
            help='Only repair empty codes; do not overwrite non-empty DB values',
        )

    def handle(self, *args, **options):
        force = not options['no_force']
        obj, changed = SectionAccessConfig.ensure_from_settings(force=force)
        if changed:
            self.stdout.write(self.style.SUCCESS(
                'SectionAccessConfig synced from settings '
                f'(force={force}).'
            ))
        else:
            self.stdout.write(
                f'SectionAccessConfig already matches settings (force={force}).'
            )
        # Never print the actual codes.
        self.stdout.write(
            f'Codes present: login={bool((obj.login_code or "").strip())}, '
            f'registration={bool((obj.registration_code or "").strip())}'
        )
