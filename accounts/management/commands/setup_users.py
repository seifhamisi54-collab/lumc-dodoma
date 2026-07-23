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
    ('admin', 'Admin Mkuu'),
    ('manager', 'Meneja Mkoa'),
    ('officer', 'Afisa Wilaya'),
    ('viewer', 'Mtazamaji'),
]

DEFAULT_USERS = [
    {
        'username': 'gisadmin',
        'email': 'gisadmin@nlupc.go.tz',
        'password': 'GisAdmin2026!',
        'first_name': 'GIS Admin',
        'role': 'admin',
        'is_staff': True,
        'is_superuser': True,
    },
    {
        'username': 'seif.hamisi',
        'email': 'seif@nlupc.go.tz',
        'password': 'Nlupc2026',
        'first_name': 'Seif Hamisi',
        'role': 'manager',
        'is_staff': True,
        'is_superuser': False,
    },
    {
        'username': 'afisa.wilaya',
        'email': 'afisa@example.go.tz',
        'password': 'Afisa2026!',
        'first_name': 'Afisa Wilaya',
        'role': 'officer',
        'is_staff': False,
        'is_superuser': False,
    },
    {
        'username': 'mtazamaji',
        'email': 'viewer@example.go.tz',
        'password': 'Viewer2026!',
        'first_name': 'Mtazamaji',
        'role': 'viewer',
        'is_staff': False,
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
        self.stdout.write('Django Admin: http://localhost:8000/admin/')
        self.stdout.write('Ingia kwa gisadmin / GisAdmin2026!')
