import re

from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import (
    CustomUser, CertificateRequest, StolenLaptopCertificate, LocationImport,
    ServicePayment, Citizen, CitizenTransfer, RequestAttachment, Announcement, Notification,
    Activity, Attendance,
)
from .permissions import effective_permissions, role_permissions


def location_name(code):
    loc = LocationImport.objects.filter(location_id=code).first() if code else None
    return loc.name if loc else ''


def location_path(village_id):
    """'Village, Cell, Sector' for an 8-digit village id so a place in another sector is unambiguous."""
    s = str(village_id or '')
    parts = [location_name(int(s[:n])) for n in (8, 6, 4) if len(s) >= n]
    return ', '.join(p for p in parts if p)


def user_name(user):
    if not user:
        return ''
    return f'{user.first_name} {user.last_name}'.strip() or user.username

# Roles allowed to see verification codes
CODE_ROLES = ('village_leader', 'cell_leader', 'sector_leader', 'system_admin')


def can_see_codes(user):
    return bool(user) and (user.is_superuser or user.role in CODE_ROLES)


def validate_strong_password(value):
    problems = []
    if len(value) < 8:
        problems.append('at least 8 characters')
    if not re.search(r'[A-Z]', value):
        problems.append('an uppercase letter')
    if not re.search(r'[a-z]', value):
        problems.append('a lowercase letter')
    if not re.search(r'\d', value):
        problems.append('a number')
    if not re.search(r'[^A-Za-z0-9]', value):
        problems.append('a special character')
    if problems:
        raise serializers.ValidationError('Password must contain ' + ', '.join(problems) + '.')
    return value


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_strong_password])

    class Meta:
        model = CustomUser
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'password', 'phone',
            'province', 'district', 'sector', 'cell', 'village', 'isibo',
        ]

    def validate_email(self, value):
        if CustomUser.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value

    def validate(self, attrs):
        if not attrs.get('village'):
            raise serializers.ValidationError({'village': 'Please select your full location down to the village.'})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = CustomUser(**validated_data)
        user.role = 'citizen'  # public registration only creates citizens
        user.set_password(password)
        user.save()
        return user


class AdminCreateUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_strong_password])

    class Meta:
        model = CustomUser
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'password', 'role', 'phone',
            'province', 'district', 'sector', 'cell', 'village', 'isibo',
        ]

    def validate_email(self, value):
        if CustomUser.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value

    def validate(self, attrs):
        role = attrs.get('role', 'citizen')
        required_by_role = {
            'sector_leader': 'sector',
            'cell_leader': 'cell',
            'village_leader': 'village',
            'isibo_leader': 'village',
            'security_volunteer': 'village',
            'cleaning_volunteer': 'village',
            'citizen': 'village',
        }
        needed = required_by_role.get(role)
        if needed and not attrs.get(needed):
            raise serializers.ValidationError({needed: f'A {role.replace("_", " ")} must have a {needed} assigned.'})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = CustomUser(**validated_data)
        user.set_password(password)
        user.save()
        return user


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Fields a signed-in user may change about themselves (email is fixed; the admin changes it)."""
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'phone']


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_strong_password])

    def validate_current_password(self, value):
        if not self.context['user'].check_password(value):
            raise serializers.ValidationError('Your current password is not correct.')
        return value

    def validate(self, attrs):
        if attrs['current_password'] == attrs['new_password']:
            raise serializers.ValidationError({'new_password': 'Choose a password different from the current one.'})
        return attrs


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        # Accept either username or email in the username field
        username = attrs['username']
        user_obj = CustomUser.objects.filter(email__iexact=username).first()
        if user_obj:
            username = user_obj.username
        user = authenticate(username=username, password=attrs['password'])
        if not user:
            raise serializers.ValidationError('Invalid username/email or password.')
        attrs['user'] = user
        return attrs


class UserSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    is_admin_role = serializers.BooleanField(read_only=True)
    village_name = serializers.SerializerMethodField()
    location_name = serializers.SerializerMethodField()
    display_name = serializers.CharField(read_only=True)
    permissions = serializers.SerializerMethodField()
    role_permissions = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'display_name', 'phone',
            'is_eligible', 'is_superuser', 'is_active', 'date_joined', 'last_login', 'role', 'role_display',
            'is_admin_role', 'province', 'district', 'sector', 'cell', 'village', 'village_name', 'location_name', 'isibo',
            'permissions', 'role_permissions', 'permission_grants', 'permission_denies',
        ]
        read_only_fields = ['permission_grants', 'permission_denies']

    def get_permissions(self, obj):
        return effective_permissions(obj)

    def get_role_permissions(self, obj):
        return role_permissions(obj.role)

    def get_village_name(self, obj):
        return location_name(obj.village)

    def get_location_name(self, obj):
        # Most specific place the account is attached to, e.g. "Kiyovu (Cell), Nyarugenge" for a cell leader
        for field, label in (('village', 'Village'), ('cell', 'Cell'), ('sector', 'Sector'), ('district', 'District'),
                             ('province', 'Province')):
            code = getattr(obj, field)
            if code:
                s = str(code)
                parent = location_name(int(s[:-2])) if len(s) > 2 else ''
                return f'{location_name(code)} ({label})' + (f', {parent}' if parent else '')
        return ''


class StolenLaptopCertificateSerializer(serializers.ModelSerializer):
    class Meta:
        model = StolenLaptopCertificate
        fields = '__all__'


class RequestAttachmentSerializer(serializers.ModelSerializer):
    kind_display = serializers.CharField(source='get_kind_display', read_only=True)
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = RequestAttachment
        fields = ['id', 'kind', 'kind_display', 'original_name', 'size', 'uploaded_at', 'download_url']

    def get_download_url(self, obj):
        return f'/api/attachments/{obj.id}/download/'


class CertificateRequestSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    cert_type_display = serializers.CharField(source='get_cert_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    details = serializers.JSONField(required=False)
    attachments = RequestAttachmentSerializer(many=True, read_only=True)
    approved_by_name = serializers.SerializerMethodField()
    has_document = serializers.SerializerMethodField()
    village_name = serializers.SerializerMethodField()

    class Meta:
        model = CertificateRequest
        fields = [
            'id', 'user', 'cert_type', 'cert_type_display', 'other_description', 'details',
            'province', 'district', 'sector', 'cell', 'village', 'village_name', 'location_code',
            'created_at', 'status', 'status_display', 'admin_message',
            'attachments', 'approved_by_name', 'approved_at', 'has_document', 'verification_code',
            'code_history', 'endorsements',
        ]
        read_only_fields = ['status', 'admin_message', 'created_at', 'approved_at', 'verification_code',
                            'code_history', 'endorsements']

    def to_representation(self, obj):
        data = super().to_representation(obj)
        # Codes are for leaders only; without a known leader in context they are withheld
        if not can_see_codes(self.context.get('user')):
            data['verification_code'] = ''
            data['code_history'] = []
        return data

    def get_approved_by_name(self, obj):
        return obj.approved_by.display_name if obj.approved_by else ''

    def get_has_document(self, obj):
        return bool(obj.generated_document)

    def get_village_name(self, obj):
        code = obj.village or obj.location_code or obj.user.village
        loc = LocationImport.objects.filter(location_id=code).first() if code else None
        return loc.name if loc else ''


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'title', 'message', 'link', 'request', 'created_at', 'read_at']


class AnnouncementSerializer(serializers.ModelSerializer):
    kind_display = serializers.CharField(source='get_kind_display', read_only=True)
    language_display = serializers.CharField(source='get_language_display', read_only=True)
    created_by_name = serializers.SerializerMethodField()
    village_name = serializers.SerializerMethodField()
    has_document = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = [
            'id', 'kind', 'kind_display', 'language', 'language_display', 'title', 'letter_date', 'event_date',
            'start_time', 'venue', 'gathering_point', 'partner', 'audience', 'meeting_points', 'location_details',
            'activities', 'reminder', 'body', 'note', 'published',
            'village', 'village_name', 'created_by', 'created_by_name', 'created_at', 'updated_at',
            'has_document', 'generated_at',
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at', 'generated_at']

    def get_has_document(self, obj):
        return bool(obj.generated_document)

    def get_created_by_name(self, obj):
        return obj.created_by.display_name if obj.created_by else ''

    def get_village_name(self, obj):
        loc = LocationImport.objects.filter(location_id=obj.village).first() if obj.village else None
        return loc.name if loc else ''


class LocationImportSerializer(serializers.ModelSerializer):
    class Meta:
        model = LocationImport
        fields = ['location_id', 'name', 'type']


class CitizenSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    village_name = serializers.SerializerMethodField()
    added_by_name = serializers.SerializerMethodField()
    transferred_from_village_name = serializers.SerializerMethodField()
    awaiting_isibo = serializers.BooleanField(read_only=True)

    class Meta:
        model = Citizen
        fields = [
            'id', 'first_name', 'last_name', 'name', 'email', 'phone', 'national_id',
            'age', 'village', 'village_name', 'isibo', 'added_by_name', 'created_at',
            'transferred_from_village', 'transferred_from_village_name', 'transferred_from_isibo',
            'transferred_at', 'transfer_placed_at', 'awaiting_isibo',
        ]
        read_only_fields = ['village', 'created_at', 'transferred_from_village', 'transferred_from_isibo',
                            'transferred_at', 'transfer_placed_at']

    def get_name(self, obj):
        return f'{obj.first_name} {obj.last_name}'.strip()

    def get_village_name(self, obj):
        return location_name(obj.village)

    def get_added_by_name(self, obj):
        return user_name(obj.added_by)

    def get_transferred_from_village_name(self, obj):
        return location_path(obj.transferred_from_village)

    def validate_national_id(self, value):
        qs = Citizen.objects.filter(national_id=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('A citizen with this ID number is already registered.')
        return value

    def validate_age(self, value):
        if value < 1 or value > 130:
            raise serializers.ValidationError('Enter a valid age.')
        return value


class CitizenTransferSerializer(serializers.ModelSerializer):
    citizen_name = serializers.SerializerMethodField()
    national_id = serializers.CharField(source='citizen.national_id', read_only=True)
    phone = serializers.CharField(source='citizen.phone', read_only=True)
    from_village_name = serializers.SerializerMethodField()
    to_village_name = serializers.SerializerMethodField()
    # Where the citizen lives now (may differ from to_village after a later transfer)
    current_village = serializers.IntegerField(source='citizen.village', read_only=True)
    current_village_name = serializers.SerializerMethodField()
    current_isibo = serializers.CharField(source='citizen.isibo', read_only=True)
    transferred_by_name = serializers.SerializerMethodField()
    placed_by_name = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = CitizenTransfer
        fields = [
            'id', 'citizen', 'citizen_name', 'national_id', 'phone',
            'from_village', 'from_village_name', 'from_isibo', 'to_village', 'to_village_name', 'to_isibo',
            'current_village', 'current_village_name', 'current_isibo', 'note',
            'transferred_by_name', 'transferred_at', 'placed_by_name', 'placed_at', 'status',
        ]

    def get_citizen_name(self, obj):
        return f'{obj.citizen.first_name} {obj.citizen.last_name}'.strip()

    def get_from_village_name(self, obj):
        return location_path(obj.from_village)

    def get_to_village_name(self, obj):
        return location_path(obj.to_village)

    def get_current_village_name(self, obj):
        return location_path(obj.citizen.village)

    def get_transferred_by_name(self, obj):
        return user_name(obj.transferred_by)

    def get_placed_by_name(self, obj):
        return user_name(obj.placed_by)

    def get_status(self, obj):
        # moved_on: transferred again from the destination before/after being placed there
        if obj.citizen.village != obj.to_village:
            return 'moved_on'
        return 'placed' if obj.placed_at else 'awaiting_isibo'


class ActivitySerializer(serializers.ModelSerializer):
    kind_display = serializers.CharField(source='get_kind_display', read_only=True)
    location_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    attendance_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Activity
        fields = [
            'id', 'kind', 'kind_display', 'title', 'description', 'date', 'location_code', 'location_name',
            'created_by_name', 'created_at', 'attendance_count',
        ]
        read_only_fields = ['location_code', 'created_at']

    def get_location_name(self, obj):
        s = str(obj.location_code)
        level = {8: 'Village', 6: 'Cell', 4: 'Sector'}.get(len(s), 'Area')
        return f'{location_name(obj.location_code)} ({level})'

    def get_created_by_name(self, obj):
        return user_name(obj.created_by)


class AttendanceSerializer(serializers.ModelSerializer):
    citizen_name = serializers.SerializerMethodField()
    national_id = serializers.CharField(source='citizen.national_id', read_only=True)
    isibo = serializers.CharField(source='citizen.isibo', read_only=True)
    village_name = serializers.SerializerMethodField()
    marked_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Attendance
        fields = ['id', 'citizen', 'citizen_name', 'national_id', 'isibo', 'village_name', 'marked_by_name', 'marked_at']

    def get_citizen_name(self, obj):
        return f'{obj.citizen.first_name} {obj.citizen.last_name}'.strip()

    def get_village_name(self, obj):
        return location_name(obj.citizen.village)

    def get_marked_by_name(self, obj):
        return user_name(obj.marked_by)


class ServicePaymentSerializer(serializers.ModelSerializer):
    citizen_name = serializers.SerializerMethodField()
    citizen_isibo = serializers.CharField(source='citizen.isibo', read_only=True)
    recorded_by_name = serializers.SerializerMethodField()
    service_display = serializers.CharField(source='get_service_display', read_only=True)

    class Meta:
        model = ServicePayment
        fields = [
            'id', 'citizen', 'citizen_name', 'citizen_isibo', 'service', 'service_display',
            'trimester', 'year', 'amount', 'paid_at', 'recorded_by_name',
        ]
        read_only_fields = ['paid_at']

    def get_citizen_name(self, obj):
        return f'{obj.citizen.first_name} {obj.citizen.last_name}'.strip()

    def get_recorded_by_name(self, obj):
        if not obj.recorded_by:
            return ''
        return f'{obj.recorded_by.first_name} {obj.recorded_by.last_name}'.strip() or obj.recorded_by.username
