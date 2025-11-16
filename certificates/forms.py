from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CertificateRequest, CertificateType, CustomUser, LocationImport
from .models import StolenLaptopCertificate

# 🔐 User Signup Form
class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=False)
    last_name = forms.CharField(required=False)

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'password1', 'password2')


# Certificate Request Form with Location Dropdowns and Stolen Laptop Fields
class CertificateRequestForm(forms.ModelForm):
    # Location fields for conduct certificates - NOT REQUIRED BY DEFAULT
    province = forms.IntegerField(required=False, widget=forms.HiddenInput())
    district = forms.IntegerField(required=False, widget=forms.HiddenInput())
    sector = forms.IntegerField(required=False, widget=forms.HiddenInput())
    cell = forms.IntegerField(required=False, widget=forms.HiddenInput())
    village = forms.IntegerField(required=False, widget=forms.HiddenInput())
    location_code = forms.IntegerField(required=False, widget=forms.HiddenInput())
    
    # Stolen Laptop/Computer Fields
    registration_number = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Registration number'
        })
    )
    national_id = forms.CharField(
        max_length=16,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'National ID'
        })
    )
    stolen_datetime = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={
            'type': 'datetime-local',
            'class': 'form-control'
        })
    )
    stolen_location = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Describe where the device was stolen'
        })
    )
    
    # Device details with choices from model
    DEVICE_TYPE_CHOICES = [('', 'Select Device Type')] + StolenLaptopCertificate.DEVICE_TYPE_CHOICES
    BRAND_CHOICES = [('', 'Select Brand')] + StolenLaptopCertificate.BRAND_CHOICES
    INTEL_CORE_CHOICES = [('', 'Select Intel Core')] + StolenLaptopCertificate.INTEL_CORE_CHOICES
    RAM_CHOICES = [('', 'Select RAM')] + StolenLaptopCertificate.RAM_CHOICES
    STORAGE_CHOICES = [('', 'Select Storage')] + StolenLaptopCertificate.STORAGE_CHOICES
    
    device_type = forms.ChoiceField(
        choices=DEVICE_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    brand = forms.ChoiceField(
        choices=BRAND_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    model = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., Latitude 5520'
        })
    )
    serial_number = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Serial number'
        })
    )
    intel_core = forms.ChoiceField(
        choices=INTEL_CORE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    ram = forms.ChoiceField(
        choices=RAM_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    storage = forms.ChoiceField(
        choices=STORAGE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Witnesses
    witness_1_name = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Witness 1 full name'
        })
    )
    witness_1_phone = forms.CharField(
        max_length=15,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Phone number'
        })
    )
    witness_2_name = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Witness 2 full name'
        })
    )
    witness_2_phone = forms.CharField(
        max_length=15,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Phone number'
        })
    )
    witness_3_name = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Witness 3 full name'
        })
    )
    witness_3_phone = forms.CharField(
        max_length=15,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Phone number'
        })
    )
    
    reported_to_police = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    laptop_other_description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Any additional information'
        })
    )

    class Meta:
        model = CertificateRequest
        fields = ['cert_type', 'other_description']
        widgets = {
            'cert_type': forms.Select(attrs={'class': 'form-control'}),
            'other_description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Please describe the certificate you need'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make other_description not required by default
        self.fields['other_description'].required = False

    def clean(self):
        cleaned_data = super().clean()
        cert_type = cleaned_data.get('cert_type')
        other_description = cleaned_data.get('other_description')

        # Validate 'other' certificate type
        if cert_type == 'other' and not other_description:
            self.add_error('other_description', 'Please describe the certificate you need.')
        
        # Clear other_description if not 'other' type
        if cert_type != 'other':
            cleaned_data['other_description'] = None

        # Validate stolen laptop fields if that certificate type is selected
        if cert_type in ['stolen_laptop', 'stolen_computer']:
            required_fields = {
                'registration_number': 'Registration number',
                'national_id': 'National ID',
                'stolen_datetime': 'Date and time stolen',
                'stolen_location': 'Location where stolen',
                'device_type': 'Device type',
                'brand': 'Brand',
                'model': 'Model',
                'serial_number': 'Serial number',
                'intel_core': 'Intel Core',
                'ram': 'RAM',
                'storage': 'Storage',
                'witness_1_name': 'Witness 1 name',
                'witness_1_phone': 'Witness 1 phone'
            }
            for field, label in required_fields.items():
                if not cleaned_data.get(field):
                    self.add_error(field, f'{label} is required for stolen laptop/computer certificate.')

        # Validate conduct certificate requires location
        if cert_type == 'conduct':
            if not cleaned_data.get('location_code'):
                self.add_error(None, 'Please select your location (Province, District, Sector, Cell).')

        return cleaned_data


# Separate Stolen Laptop Certificate Form (if needed for admin or other uses)
class StolenLaptopCertificateForm(forms.ModelForm):
    class Meta:
        model = StolenLaptopCertificate
        fields = '__all__'
        widgets = {
            'stolen_datetime': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control'
            }),
            'location': forms.Textarea(attrs={
                'rows': 2,
                'class': 'form-control'
            }),
            'other_description': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control'
            }),
        }