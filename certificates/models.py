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
    from django.db import models

class StolenLaptopCertificate(models.Model):
    registration_number = models.CharField(max_length=50)
    national_id = models.CharField(max_length=16)
    stolen_datetime = models.DateTimeField()
    location = models.TextField()

    # Device description
    DEVICE_TYPE_CHOICES = [('Laptop', 'Laptop'), ('Tablet', 'Tablet')]
    BRAND_CHOICES = [('Lenovo', 'Lenovo'), ('HP', 'HP'), ('Dell', 'Dell'), ('Mac', 'Mac')]
    INTEL_CORE_CHOICES = [('i3', 'Intel Core i3'), ('i5', 'Intel Core i5'), ('i7', 'Intel Core i7')]
    RAM_CHOICES = [('4GB', '4GB'), ('8GB', '8GB'), ('16GB', '16GB')]
    STORAGE_CHOICES = [('SSD', 'SSD'), ('HDD', 'Hard Disk')]

    device_type = models.CharField(max_length=20, choices=DEVICE_TYPE_CHOICES)
    brand = models.CharField(max_length=20, choices=BRAND_CHOICES)
    model = models.CharField(max_length=50)
    serial_number = models.CharField(max_length=50)
    intel_core = models.CharField(max_length=10, choices=INTEL_CORE_CHOICES)
    ram = models.CharField(max_length=10, choices=RAM_CHOICES)
    storage = models.CharField(max_length=10, choices=STORAGE_CHOICES)

    # Witnesses
    witness_1_name = models.CharField(max_length=100)
    witness_1_phone = models.CharField(max_length=15)
    witness_2_name = models.CharField(max_length=100)
    witness_2_phone = models.CharField(max_length=15)
    witness_3_name = models.CharField(max_length=100)
    witness_3_phone = models.CharField(max_length=15)

    # Additional info
    reported_to_police = models.BooleanField(default=False)
    other_description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Stolen Laptop Certificate - {self.registration_number}"
