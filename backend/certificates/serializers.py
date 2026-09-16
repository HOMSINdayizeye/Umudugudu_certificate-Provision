import re

from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import (
    CustomUser, CertificateRequest, StolenLaptopCertificate, LocationImport,
    ServicePayment, Citizen, RequestAttachment, Announcement,
)


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
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = CustomUser
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'display_name', 'phone',
            'is_eligible', 'is_superuser', 'role', 'role_display', 'is_admin_role',
            'province', 'district', 'sector', 'cell', 'village', 'village_name', 'isibo',
        ]

    def get_village_name(self, obj):
        if not obj.village:
            return ''
        loc = LocationImport.objects.filter(location_id=obj.village).first()
        return loc.name if loc else ''


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
            'attachments', 'approved_by_name', 'approved_at', 'has_document',
        ]
        read_only_fields = ['status', 'admin_message', 'created_at', 'approved_at']

    def get_approved_by_name(self, obj):
        return obj.approved_by.display_name if obj.approved_by else ''

    def get_has_document(self, obj):
        return bool(obj.generated_document)

    def get_village_name(self, obj):
        code = obj.village or obj.location_code or obj.user.village
        loc = LocationImport.objects.filter(location_id=code).first() if code else None
        return loc.name if loc else ''


class AnnouncementSerializer(serializers.ModelSerializer):
    kind_display = serializers.CharField(source='get_kind_display', read_only=True)
    language_display = serializers.CharField(source='get_language_display', read_only=True)
    created_by_name = serializers.SerializerMethodField()
    village_name = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = [
            'id', 'kind', 'kind_display', 'language', 'language_display', 'title', 'letter_date', 'event_date',
            'start_time', 'venue', 'gathering_point', 'partner', 'audience', 'body', 'note', 'published',
            'village', 'village_name', 'created_by', 'created_by_name', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']

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

    class Meta:
        model = Citizen
        fields = [
            'id', 'first_name', 'last_name', 'name', 'email', 'phone', 'national_id',
            'age', 'village', 'village_name', 'isibo', 'added_by_name', 'created_at',
        ]
        read_only_fields = ['village', 'created_at']

    def get_name(self, obj):
        return f'{obj.first_name} {obj.last_name}'.strip()

    def get_village_name(self, obj):
        loc = LocationImport.objects.filter(location_id=obj.village).first()
        return loc.name if loc else ''

    def get_added_by_name(self, obj):
        if not obj.added_by:
            return ''
        return f'{obj.added_by.first_name} {obj.added_by.last_name}'.strip() or obj.added_by.username

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
