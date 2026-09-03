from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import CustomUser, CertificateRequest, StolenLaptopCertificate, LocationImport


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'password']

    def validate_email(self, value):
        if CustomUser.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value

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
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'is_eligible', 'is_superuser']


class StolenLaptopCertificateSerializer(serializers.ModelSerializer):
    class Meta:
        model = StolenLaptopCertificate
        fields = '__all__'


class CertificateRequestSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    cert_type_display = serializers.CharField(source='get_cert_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = CertificateRequest
        fields = [
            'id', 'user', 'cert_type', 'cert_type_display', 'other_description',
            'province', 'district', 'sector', 'cell', 'village', 'location_code',
            'created_at', 'status', 'status_display', 'admin_message',
        ]
        read_only_fields = ['status', 'admin_message', 'created_at']


class LocationImportSerializer(serializers.ModelSerializer):
    class Meta:
        model = LocationImport
        fields = ['location_id', 'name', 'type']
