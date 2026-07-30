"""
Weka majukumu na watumiaji wa msingi — GIS Portal.

Mfano:
  python manage.py setup_users
  python manage.py setup_users --reset-passwords
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from accounts.models import UserRole

User = get_user_model()

DEFAULT_ROLES = [
    ('section_head', 'Section Head'),
    ('gis_officer', 'GIS Officer'),
    ('data_management_officer', 'Data Management Officer'),
    ('land_dispute_officer', 'Land Dispute Officer'),
]

DEFAULT_USERS = [
    {
        'username': 'seif17',
        'email': 'seifhamisi54@gmail.com',
        'password': 'Nlupc2026!',
        'first_name': 'Seif',
        'role': 'section_head',
        'is_staff': True,
        'is_superuser': True,
    },
    {
        'username': 'gisadmin',
        'email': 'gisadmin@nlupc.go.tz',
        'password': 'Nlupc2026!',
        'first_name': 'GIS Admin',
        'role': 'section_head',
        'is_staff': True,
        'is_superuser': True,
    },
    {
        'username': 'seif.hamisi',
        'email': 'seif@nlupc.go.tz',
        'password': 'Nlupc2026!',
        'first_name': 'Seif Hamisi',
        'role': 'data_management_officer',
        'is_staff': True,
        'is_superuser': True,
    },
    {
        'username': 'afisa.wilaya',
        'email': 'afisa@example.go.tz',
        'password': 'Nlupc2026!',
        'first_name': 'Afisa Wilaya',
        'role': 'gis_officer',
        'is_staff': False,
        'is_superuser': False,
    },
    {
        'username': 'mtazamaji',
        'email': 'viewer@example.go.tz',
        'password': 'Nlupc2026!',
        'first_name': 'Mtazamaji',
        'role': 'gis_officer',
        'is_staff': False,
        'is_superuser': False,
    },
    {
        'username': 'Joseph.Ndalu',
        'email': '',
        'password': 'Nlupc2026!',
        'first_name': 'Joseph Ndalu',
        'role': 'data_management_officer',
        'is_staff': True,
        'is_superuser': False,
    },
]


class Command(BaseCommand):
    help = 'Weka majukumu na watumiaji wa msingi wa GIS Portal'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset-passwords',
            action='store_true',
            help='Weka upya password za watumiaji wa msingi',
        )

    def handle(self, *args, **options):
        reset = options['reset_passwords']
        roles = {}
        for code, _label in DEFAULT_ROLES:
            role, created = UserRole.objects.get_or_create(name=code)
            roles[code] = role
            if created:
                self.stdout.write(self.style.SUCCESS(f'Jukumu limeundwa: {code}'))

        for spec in DEFAULT_USERS:
            username = spec['username']
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': spec['email'],
                    'first_name': spec['first_name'],
                    'is_staff': spec['is_staff'],
                    'is_superuser': spec['is_superuser'],
                    'is_active': True,
                    'role': roles[spec['role']],
                },
            )
            if created or reset:
                user.set_password(spec['password'])
            user.email = spec['email']
            user.first_name = spec['first_name']
            user.is_staff = spec['is_staff']
            user.is_superuser = spec['is_superuser']
            user.is_active = True
            user.role = roles[spec['role']]
            user.save()

            action = 'Imeundwa' if created else 'Imesasishwa'
            self.stdout.write(self.style.SUCCESS(
                f'{action}: {username} ({spec["role"]}) — password: {spec["password"]}'
            ))

        self.stdout.write('')
        self.stdout.write('Login: /login/  —  seif17 / Nlupc2026!  (au gisadmin)')
