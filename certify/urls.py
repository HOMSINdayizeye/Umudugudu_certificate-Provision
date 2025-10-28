
from django.contrib import admin
from django.urls import path, include
from certificates import views

from django.shortcuts import redirect

urlpatterns = [
    path('', lambda request: redirect('certificates/')),
    path('admin/', admin.site.urls),
    path('certificates/', include('certificates.urls')),
    path('choose/', views.choose_certificate, name='choose_certificate'),
]

