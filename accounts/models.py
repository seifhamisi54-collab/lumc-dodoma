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