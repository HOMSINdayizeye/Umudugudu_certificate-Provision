import datetime

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
        ('cell_youth_leader', 'Cell Youth Leader'),
        ('sector_youth_leader', 'Sector Youth Leader'),
        ('security_volunteer', 'Security Volunteer'),
        ('cleaning_volunteer', 'Cleaning Service Volunteer'),
        ('system_admin', 'System Admin'),
    ]
    # Youth leaders see only the youth of their cell/sector and write announcements for them
    YOUTH_ROLES = ('cell_youth_leader', 'sector_youth_leader')

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
    # Admin overrides on top of the role's permissions: extra keys given, and role keys taken away
    permission_grants = models.JSONField(default=list, blank=True)
    permission_denies = models.JSONField(default=list, blank=True)

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
        if self.role in ('sector_leader', 'sector_youth_leader'):
            return self.sector
        if self.role in ('cell_leader', 'cell_youth_leader'):
            return self.cell
        if self.role in ('village_leader', 'isibo_leader', 'security_volunteer', 'cleaning_volunteer'):
            return self.village
        return None

class RolePolicy(models.Model):
    """Admin-edited permission set for one role; absent rows fall back to permissions.ROLE_DEFAULTS."""
    role = models.CharField(max_length=30, unique=True)
    permissions = models.JSONField(default=list, blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='role_policies_updated')
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.role}: {len(self.permissions)} permissions'


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
    national_id = models.CharField(max_length=20, blank=True, null=True)

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
        ('village_approved', 'Approved by Village · awaiting Cell'),
        ('cell_approved', 'Approved by Cell · awaiting Sector'),
        ('approved', 'Fully Approved'),
        ('denied', 'Denied'),
    ]
    # Letter exists and can be opened from these statuses onward
    ISSUED_STATUSES = ('village_approved', 'cell_approved', 'approved')

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='requests')
    cert_type = models.CharField(max_length=20, choices=CERT_TYPES)
    other_description = models.TextField(blank=True, null=True)
    # Type-specific applicant data used to fill the letter (names, ID, device, witnesses…)
    details = models.JSONField(default=dict, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='approved_requests')
    approved_at = models.DateTimeField(null=True, blank=True)
    generated_document = models.FileField(upload_to='generated/', blank=True, null=True)
    # Anti-forgery code printed in the letter footer (location code + running number); never shown to citizens
    verification_code = models.CharField(max_length=40, blank=True, default='', db_index=True)
    # Every code ever issued for this letter: [{level, prefix, code, by, at}], village → cell → sector
    code_history = models.JSONField(default=list, blank=True)
    # Cell / sector endorsements printed under the signature: [{level, name, at}]
    endorsements = models.JSONField(default=list, blank=True)

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
    ID_TYPE_CHOICES = [('national_id', 'National ID'), ('passport', 'Passport')]
    # Citizens aged 16 to 30 inclusive count as youth; everyone else is an ordinary citizen
    YOUTH_MIN, YOUTH_MAX = 16, 30
    CATEGORY_LABELS = {'youth': 'Youth', 'citizen': 'Citizen'}

    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.EmailField(blank=True, default='')
    phone = models.CharField(max_length=20, blank=True, default='')
    # A 16-digit national ID (its digits 2-5 are the birth year) or a passport number
    id_type = models.CharField(max_length=12, choices=ID_TYPE_CHOICES, default='national_id')
    national_id = models.CharField(max_length=20)
    age = models.PositiveIntegerField()
    village = models.IntegerField()
    isibo = models.CharField(max_length=100, blank=True, default='')
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                 null=True, related_name='citizens_added')
    created_at = models.DateTimeField(auto_now_add=True)
    # Set when a leader moves the citizen here from another village; cleared isibo means "awaiting placement"
    transferred_from_village = models.IntegerField(blank=True, null=True)
    transferred_from_isibo = models.CharField(max_length=100, blank=True, default='')
    transferred_at = models.DateTimeField(null=True, blank=True)
    # When the destination village leader assigned the transferred citizen to an isibo
    transfer_placed_at = models.DateTimeField(null=True, blank=True)
    # Deceased citizens keep their record (see DeathReport) but leave every living-citizen list and count
    STATUS_CHOICES = [('alive', 'Alive'), ('deceased', 'Deceased')]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='alive')

    @property
    def awaiting_isibo(self):
        return self.transferred_from_village is not None and self.transfer_placed_at is None

    @property
    def is_youth(self):
        return self.age is not None and self.YOUTH_MIN <= self.age <= self.YOUTH_MAX

    @property
    def category(self):
        return 'youth' if self.is_youth else 'citizen'

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.national_id})"


class DeathReport(models.Model):
    """Village leader's record that a registry citizen has died."""
    citizen = models.OneToOneField(Citizen, on_delete=models.CASCADE, related_name='death_report')
    date_of_death = models.DateField()
    place = models.CharField(max_length=200, blank=True, default='')
    note = models.TextField(blank=True, default='')
    # Village the citizen belonged to when reported (kept even if records move later)
    village = models.IntegerField()
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                    related_name='death_reports')
    reported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_of_death', '-reported_at']

    def __str__(self):
        return f'{self.citizen} † {self.date_of_death}'


class CitizenTransfer(models.Model):
    """One move of a registry citizen from a village to another, recorded by a village/cell leader."""
    # The citizen stays in the source village until the destination village leader accepts the transfer
    STATUS_CHOICES = [('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected'),
                      ('cancelled', 'Cancelled')]
    citizen = models.ForeignKey(Citizen, on_delete=models.CASCADE, related_name='transfers')
    from_village = models.IntegerField()
    from_isibo = models.CharField(max_length=100, blank=True, default='')
    to_village = models.IntegerField()
    # Isibo given by the destination village leader once the citizen is placed
    to_isibo = models.CharField(max_length=100, blank=True, default='')
    note = models.TextField(blank=True, default='')
    transferred_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                       related_name='citizen_transfers')
    transferred_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    # Who accepted/declined/cancelled the transfer and when; decision_note holds the reason for declining
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='citizen_transfer_decisions')
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True, default='')
    placed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='citizen_placements')
    placed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-transferred_at']

    def __str__(self):
        return f'{self.citizen} : {self.from_village} → {self.to_village}'


class Activity(models.Model):
    """Community activity (Umuganda, meeting, election…) a leader runs and takes attendance for."""
    KIND_CHOICES = [
        ('community_work', 'Community Work (Umuganda)'),
        ('meeting', 'Meeting'),
        ('election', 'Election'),
        ('training', 'Training / Sensitisation'),
        ('other', 'Other'),
    ]

    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default='community_work')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    date = models.DateField()
    # Area the activity belongs to: the creator's village, cell or sector code (prefix of citizen village ids)
    location_code = models.IntegerField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                   related_name='activities')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f'{self.title} ({self.date})'


class Attendance(models.Model):
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name='attendances')
    citizen = models.ForeignKey(Citizen, on_delete=models.CASCADE, related_name='attendances')
    marked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                  related_name='attendance_marked')
    marked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('activity', 'citizen')
        ordering = ['-marked_at']

    def __str__(self):
        return f'{self.citizen} @ {self.activity}'


class SystemSetting(models.Model):
    """Admin-set values such as the attendance count needed for a community engagement letter."""
    key = models.CharField(max_length=50, unique=True)
    value = models.JSONField(default=dict, blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='settings_updated')
    updated_at = models.DateTimeField(auto_now=True)

    MIN_ATTENDANCE_DEFAULT = 3

    @classmethod
    def min_attendance(cls):
        row = cls.objects.filter(key='min_attendance').first()
        try:
            return int(row.value.get('count')) if row else cls.MIN_ATTENDANCE_DEFAULT
        except (TypeError, ValueError, AttributeError):
            return cls.MIN_ATTENDANCE_DEFAULT

    def __str__(self):
        return f'{self.key} = {self.value}'


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
    # Written by a youth leader: addressed to the youth of the area and signed as youth leader
    for_youth = models.BooleanField(default=False)
    # The rendered letter is kept on disk so it can be downloaded again later
    generated_document = models.FileField(upload_to='announcements/', blank=True, null=True)
    generated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # A letter without an event date stays on other people's lists this many days after its letter date
    DAYS_VISIBLE = 30

    @property
    def visible_until(self):
        # Last day the letter is shown to people other than its author
        if self.event_date:
            return self.event_date
        return self.letter_date + datetime.timedelta(days=self.DAYS_VISIBLE) if self.letter_date else None

    class Meta:
        ordering = ['-letter_date', '-created_at']

    def __str__(self):
        return f'{self.get_kind_display()} – {self.letter_date}'


class LeaderNotice(models.Model):
    """Internal notice from a sector leader to the cell leaders of the sector, a cell leader to the village leaders of the cell,
    or a sector youth leader to the cell youth leaders of the sector."""
    AUDIENCE_CHOICES = [('cell_leader', 'Cell leaders'), ('village_leader', 'Village leaders'),
                        ('cell_youth_leader', 'Cell youth leaders')]

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                   related_name='leader_notices')
    # Sector (4-digit) or cell (6-digit) code whose leaders receive the notice
    area_code = models.IntegerField()
    audience = models.CharField(max_length=20, choices=AUDIENCE_CHOICES)
    title = models.CharField(max_length=200)
    body = models.TextField()
    # Leaders of the area the author chose to leave out; everyone else in the area sees the notice
    excluded = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='excluded_from_notices')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} → {self.get_audience_display()} of {self.area_code}'


class LeaderInquiry(models.Model):
    """Question a leader sends to the leader(s) of another area at the same level, optionally asking for their contact."""
    CONTACT_CHOICES = [('none', 'Not requested'), ('pending', 'Requested'), ('shared', 'Shared'), ('declined', 'Declined')]

    from_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='inquiries_sent')
    # Role addressed (the requester's own role) and the village/cell/sector code its leaders hold
    role = models.CharField(max_length=30)
    to_location = models.IntegerField()
    title = models.CharField(max_length=200)
    description = models.TextField()
    # The leader who answered; any leader of the role at that location may do so
    answered_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='inquiries_answered')
    reply = models.TextField(blank=True, default='')
    replied_at = models.DateTimeField(null=True, blank=True)
    # Contact request: the answering leader decides whether to share and which fields
    contact_status = models.CharField(max_length=10, choices=CONTACT_CHOICES, default='none')
    share_phone = models.BooleanField(default=False)
    share_email = models.BooleanField(default=False)
    contact_decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} → {self.role} of {self.to_location}'


class PopulationFigure(models.Model):
    """Population of one administrative area in one year: a census count, an NISR projection, or a local count a
    leader entered for a cell or village (NISR publishes nothing below sector level)."""
    KIND_CHOICES = [('census', 'Census'), ('projection', 'Projection'), ('manual', 'Local count')]
    LEVEL_CHOICES = [('country', 'Country'), ('province', 'Province'), ('district', 'District'), ('sector', 'Sector'),
                     ('cell', 'Cell'), ('village', 'Village')]

    location = models.IntegerField(db_index=True)   # LocationImport.location_id
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES)
    year = models.IntegerField()
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default='census')
    total = models.IntegerField()
    male = models.IntegerField(null=True, blank=True)
    female = models.IntegerField(null=True, blank=True)
    urban = models.IntegerField(null=True, blank=True)
    rural = models.IntegerField(null=True, blank=True)
    households = models.IntegerField(null=True, blank=True)
    source = models.CharField(max_length=200, blank=True, default='')
    note = models.TextField(blank=True, default='')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='population_figures')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('location', 'year', 'kind')
        ordering = ['location', 'year']

    def __str__(self):
        return f'{self.get_level_display()} {self.location} {self.year} ({self.kind}): {self.total}'


class CensusIndicator(models.Model):
    """One published statistic (count, percentage or index) for an area and year, keyed like `hh_electricity_pct`."""
    location = models.IntegerField(db_index=True)
    level = models.CharField(max_length=10, choices=PopulationFigure.LEVEL_CHOICES)
    year = models.IntegerField()
    key = models.CharField(max_length=50, db_index=True)
    value = models.FloatField()
    source = models.CharField(max_length=200, blank=True, default='')

    class Meta:
        unique_together = ('location', 'year', 'key')
        ordering = ['location', 'year', 'key']

    def __str__(self):
        return f'{self.location} {self.year} {self.key} = {self.value}'


class PasswordResetCode(models.Model):
    """One-time 6-digit code texted to an account's phone so the owner can set a new password."""
    LIFETIME_MINUTES = 10
    MAX_ATTEMPTS = 5
    RESEND_SECONDS = 60

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='password_reset_codes')
    phone = models.CharField(max_length=20)
    code_hash = models.CharField(max_length=128)   # the code itself is never stored
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveIntegerField(default=0)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def is_open(self):
        from django.utils import timezone as tz
        return self.used_at is None and self.attempts < self.MAX_ATTEMPTS and self.expires_at > tz.now()

    def __str__(self):
        return f'Reset code for {self.user} ({"open" if self.is_open else "closed"})'
