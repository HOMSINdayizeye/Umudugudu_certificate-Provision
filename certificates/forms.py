
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import CertificateRequest
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


class CertificateRequestForm(forms.ModelForm):
    class Meta:
        model = CertificateRequest
        fields = ('cert_type',)
        widgets = {
            'cert_type': forms.Select(attrs={'class': 'form-select'})
        }