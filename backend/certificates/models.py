from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings




# Custom user model
class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('citizen', 'Citizen'),
        ('isibo_leader', 'Isibo Leader'),
        ('village_leader', 'Village Leader'),
        ('cell_leader', 'Cell Leader'),
        ('sector_leader', 'Sector Leader'),
        ('security_volunteer', 'Security Volunteer'),
        ('cleaning_volunteer', 'Cleaning Service Volunteer'),
        ('system_admin', 'System Admin'),
    ]

    is_eligible = models.BooleanField(default=False)
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default='citizen')

    # Residence / jurisdiction (LocationImport location_id values)
    province = models.IntegerField(blank=True, null=True)
    district = models.IntegerField(blank=True, null=True)
    sector = models.IntegerField(blank=True, null=True)
    cell = models.IntegerField(blank=True, null=True)
    village = models.IntegerField(blank=True, null=True)
    isibo = models.CharField(max_length=100, blank=True, default='')
    phone = models.CharField(max_length=20, blank=True, default='')

    @property
    def display_name(self):
        # Official letters write the surname first: "NDAYIZEYE Amos"
        if self.last_name or self.first_name:
            return f'{self.last_name.upper()} {self.first_name}'.strip()
        return self.username

    @property
    def is_admin_role(self):
        return self.is_superuser or self.role == 'system_admin'

    @property
    def scope_code(self):
        # Location code this user's authority covers (prefix of child location ids)
        if self.role == 'sector_leader':
            return self.sector
        if self.role == 'cell_leader':
            return self.cell
        if self.role in ('village_leader', 'isibo_leader', 'security_volunteer', 'cleaning_volunteer'):
            return self.village
        return None

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
        ('conduct', 'Certificate of Conduct'),
        ('residence', 'Residence Recognition'),
        ('community', 'Community Engagement Referral'),
        ('stolen_computer', 'Stolen Laptop / Electronic Device Report'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending Village Leader Review'),
        ('village_approved', 'Pending Cell Approval'),
        ('cell_approved', 'Pending Sector Approval'),
        ('approved', 'Approved'),
        ('denied', 'Denied'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='requests')
    cert_type = models.CharField(max_length=20, choices=CERT_TYPES)
    other_description = models.TextField(blank=True, null=True)
    # Type-specific applicant data used to fill the letter (names, ID, device, witnesses…)
    details = models.JSONField(default=dict, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='approved_requests')
    approved_at = models.DateTimeField(null=True, blank=True)
    generated_document = models.FileField(upload_to='generated/', blank=True, null=True)
    # Anti-forgery code printed in the letter footer: <village id>-<year>-<sequence>; never shown to citizens
    verification_code = models.CharField(max_length=40, blank=True, default='', db_index=True)

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

class Citizen(models.Model):
    """Citizen registry record maintained by the isibo leader (not a login account)."""
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.EmailField(blank=True, default='')
    phone = models.CharField(max_length=20, blank=True, default='')
    national_id = models.CharField(max_length=16)
    age = models.PositiveIntegerField()
    village = models.IntegerField()
    isibo = models.CharField(max_length=100, blank=True, default='')
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                 null=True, related_name='citizens_added')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.national_id})"


class ServicePayment(models.Model):
    SERVICE_CHOICES = [
        ('cleaning', 'Cleaning Service'),
        ('security', 'Security Service'),
    ]
    TRIMESTER_CHOICES = [(1, 'Trimester 1'), (2, 'Trimester 2'), (3, 'Trimester 3')]

    citizen = models.ForeignKey(Citizen, on_delete=models.CASCADE, related_name='payments')
    service = models.CharField(max_length=20, choices=SERVICE_CHOICES)
    trimester = models.IntegerField(choices=TRIMESTER_CHOICES)
    year = models.IntegerField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid_at = models.DateTimeField(auto_now_add=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, related_name='recorded_payments')

    class Meta:
        # One payment per citizen per service per trimester per year
        unique_together = ('citizen', 'service', 'trimester', 'year')

    def __str__(self):
        return f"{self.citizen} - {self.service} T{self.trimester}/{self.year} ({self.amount} RWF)"


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


class Notification(models.Model):
    """In-app notice for one user, e.g. a cell leader told that a letter was issued."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True, default='')
    link = models.CharField(max_length=200, blank=True, default='')
    request = models.ForeignKey(CertificateRequest, on_delete=models.CASCADE, null=True, blank=True,
                                related_name='notifications')
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user} – {self.title}'


def attachment_upload_path(instance, filename):
    return f'attachments/request_{instance.request_id}/{filename}'


class RequestAttachment(models.Model):
    """Supporting file a citizen uploads with a request (ID copy, student card, proof…)."""
    KIND_CHOICES = [
        ('national_id', 'National ID / Passport'),
        ('student_card', 'Student Card'),
        ('proof', 'Proof / Supporting Document'),
        ('photo', 'Photo'),
        ('other', 'Other'),
    ]

    request = models.ForeignKey(CertificateRequest, on_delete=models.CASCADE, related_name='attachments')
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default='other')
    file = models.FileField(upload_to=attachment_upload_path)
    original_name = models.CharField(max_length=255)
    size = models.PositiveIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.original_name} ({self.get_kind_display()})'


class Announcement(models.Model):
    """Leader-authored notice (e.g. Umuganda communique) rendered to a downloadable letter."""
    KIND_CHOICES = [
        ('umuganda', 'Community Work (Umuganda)'),
        ('meeting', 'Meeting / Gathering'),
        ('general', 'General Announcement'),
    ]
    LANGUAGE_CHOICES = [('en', 'English'), ('rw', 'Kinyarwanda')]

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                   related_name='announcements')
    village = models.IntegerField(blank=True, null=True)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default='umuganda')
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default='en')
    title = models.CharField(max_length=200, blank=True, default='')
    letter_date = models.DateField()
    event_date = models.DateField(blank=True, null=True)
    start_time = models.CharField(max_length=30, blank=True, default='')
    venue = models.CharField(max_length=200, blank=True, default='')
    gathering_point = models.CharField(max_length=200, blank=True, default='')
    partner = models.CharField(max_length=200, blank=True, default='')
    audience = models.CharField(max_length=200, blank=True, default='')
    # Optional list of {"audience", "place", "time"} entries; supersedes gathering_point/audience when present
    meeting_points = models.JSONField(default=list, blank=True)
    # Bracketed detail after the gathering sentence, e.g. "Outside Campus with NYARUGENGE SECTOR Citizens, APE Rugunga"
    location_details = models.CharField(max_length=300, blank=True, default='')
    # Closing reminder sentence, e.g. the "Whoever neglects their duty…" line
    reminder = models.TextField(blank=True, default='')
    # What will be done; when empty the letter says further details will be shared at the gathering point
    activities = models.TextField(blank=True, default='')
    # Free text; when empty the body is generated from the fields above
    body = models.TextField(blank=True, default='')
    note = models.TextField(blank=True, default='')
    published = models.BooleanField(default=False)
    # The rendered letter is kept on disk so it can be downloaded again later
    generated_document = models.FileField(upload_to='announcements/', blank=True, null=True)
    generated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-letter_date', '-created_at']

    def __str__(self):
        return f'{self.get_kind_display()} – {self.letter_date}'
