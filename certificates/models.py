from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings

# Custom user model
class CustomUser(AbstractUser):
    is_eligible = models.BooleanField(default=False)

# Profile model linked to custom user
class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    is_eligible = models.BooleanField(default=False)

class LocationImport(models.Model):
    location_id = models.IntegerField(primary_key=True)
    type = models.CharField(max_length=50)
    name = models.CharField(max_length=150)
    status = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.name} ({self.type})"


# Eligible person registry
class EligiblePerson(models.Model):
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    national_id = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} <{self.email}>"

# Certificate type model
class CertificateType(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

# Certificate request model
class CertificateRequest(models.Model):
    CERT_TYPES = [
        ('conduct', 'Conduct'),
        ('residence', 'Residence Recognition'),
        ('community', 'Community Engagement'),
        ('stolen_computer', 'Stolen Computer'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('denied', 'Denied'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='requests')
    cert_type = models.CharField(max_length=20, choices=CERT_TYPES)
    other_description = models.TextField(blank=True, null=True)
    
    # Location fields (only required for 'conduct' certificate)
    province = models.IntegerField(blank=True, null=True)
    district = models.IntegerField(blank=True, null=True)
    sector = models.IntegerField(blank=True, null=True)
    cell = models.IntegerField(blank=True, null=True)
    village = models.IntegerField(blank=True, null=True)
    location_code = models.IntegerField(blank=True, null=True)  # Final selected location_id
    
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    eligible = models.BooleanField(default=False)
    email = models.EmailField(default='umudugudu@gmail.com')
    admin_message = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.email} - {self.cert_type} ({self.status})"

# Location model for hierarchical geographical data
class Location(models.Model):
    province = models.CharField(max_length=100)
    district = models.CharField(max_length=100)
    sector = models.CharField(max_length=100)
    cell = models.CharField(max_length=100)
    village = models.CharField(max_length=100)
    code = models.IntegerField()

    def __str__(self):
        return f"{self.province} > {self.district} > {self.sector} > {self.cell} > {self.village}"