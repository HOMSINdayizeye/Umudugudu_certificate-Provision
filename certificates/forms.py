
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import CertificateRequest, CertificateType
from .models import CustomUser


from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=False)
    last_name = forms.CharField(required=False)

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'password1', 'password2')



# class CertificateRequestForm(forms.ModelForm):
#     class Meta:
#         model = CertificateRequest
#         fields = ['cert_type'] 

class CertificateRequestForm(forms.ModelForm):
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
        self.fields['other_description'].required = False

    def clean(self):
        cleaned_data = super().clean()
        cert_type = cleaned_data.get('cert_type')
        other_description = cleaned_data.get('other_description')

        if cert_type == 'other' and not other_description:
          self.add_error('other_description', 'Please describe the certificate you need.')
        elif cert_type != 'other':
            cleaned_data['other_description'] = None

        return cleaned_data

