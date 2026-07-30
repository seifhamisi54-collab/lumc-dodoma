from django.conf import settings
from django.db import models
from django.contrib.auth.models import AbstractUser
from locations.models import Region, District

class UserRole(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Admin Mkuu'),
        ('manager', 'Meneja Mkoa'),
        ('officer', 'Afisa Wilaya'),
        ('viewer', 'Mtazamaji'),
    ]
    name = models.CharField(max_length=50, choices=ROLE_CHOICES, unique=True)
    def __str__(self):
        return self.get_name_display()

class CustomUser(AbstractUser):
    phone = models.CharField(max_length=15, blank=True)
    role = models.ForeignKey(UserRole, on_delete=models.SET_NULL, null=True, blank=True)
    assigned_region = models.ForeignKey(Region, on_delete=models.SET_NULL, null=True, blank=True)
    assigned_district = models.ForeignKey(District, on_delete=models.SET_NULL, null=True, blank=True)
    profile_picture = models.CharField(max_length=500, null=True, blank=True)  # Badala ya ImageField
    def __str__(self):
        return self.username


class SectionAccessConfig(models.Model):
    """Singleton: shared section registration + institution login codes."""

    registration_code = models.CharField(
        max_length=128,
        verbose_name='Nambari ya Usajili (Section)',
        help_text='Inahitajika wakati wa kujisajili. Shared kwa sehemu yote.',
    )
    login_code = models.CharField(
        max_length=128,
        verbose_name='Nambari ya Kuingia (Taasisi)',
        help_text='Inahitajika wakati wa login pamoja na username/password.',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Section Access Config'
        verbose_name_plural = 'Section Access Config'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    def __str__(self):
        return 'Section Access Config'

    @classmethod
    def get_solo(cls):
        defaults = {
            'registration_code': getattr(settings, 'LUMC_REGISTRATION_CODE', 'LUMC-REG-2026'),
            'login_code': getattr(settings, 'LUMC_LOGIN_CODE', 'LUMC-LOGIN-2026'),
        }
        obj, created = cls.objects.get_or_create(pk=1, defaults=defaults)
        # Repair empty codes on existing rows (e.g. partial admin save).
        if not created:
            dirty = False
            if not (obj.registration_code or '').strip():
                obj.registration_code = defaults['registration_code']
                dirty = True
            if not (obj.login_code or '').strip():
                obj.login_code = defaults['login_code']
                dirty = True
            if dirty:
                obj.save(update_fields=['registration_code', 'login_code', 'updated_at'])
        return obj


def get_registration_code() -> str:
    try:
        return (SectionAccessConfig.get_solo().registration_code or '').strip()
    except Exception:
        return (getattr(settings, 'LUMC_REGISTRATION_CODE', 'LUMC-REG-2026') or '').strip()


def get_login_code() -> str:
    try:
        return (SectionAccessConfig.get_solo().login_code or '').strip()
    except Exception:
        return (getattr(settings, 'LUMC_LOGIN_CODE', 'LUMC-LOGIN-2026') or '').strip()


def section_code_matches(provided: str, expected: str) -> bool:
    """Case-sensitive compare after trim. Never log codes."""
    return (provided or '').strip() == (expected or '').strip()