from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CertificateRequest, CertificateType, CustomUser, Location

# 🔐 User Signup Form
class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=False)
    last_name = forms.CharField(required=False)

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'password1', 'password2')

# Certificate Request Form with Location Dropdowns
class CertificateRequestForm(forms.ModelForm):
    province = forms.ChoiceField(choices=[], required=False)
    district = forms.ChoiceField(choices=[], required=False)
    sector = forms.ChoiceField(choices=[], required=False)
    cell = forms.ChoiceField(choices=[], required=False)
    village = forms.ChoiceField(choices=[], required=False)

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

        # Optional description unless cert_type is 'other'
        self.fields['other_description'].required = False

        #  Populate province dropdown from Location model
        provinces = Location.objects.values_list('province', flat=True).distinct()
        self.fields['province'].choices = [('', '--- Select Province ---')] + [(p, p) for p in provinces]

        # You can extend this with dynamic filtering for district, sector, etc.
        # For now, leave them empty or populate similarly if needed

    def clean(self):
        cleaned_data = super().clean()
        cert_type = cleaned_data.get('cert_type')
        other_description = cleaned_data.get('other_description')

        if cert_type == 'other' and not other_description:
            self.add_error('other_description', 'Please describe the certificate you need.')
        elif cert_type != 'other':
            cleaned_data['other_description'] = None

        return cleaned_data
