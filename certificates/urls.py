from django.urls import path
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect
from . import views

urlpatterns = [
    # Redirect root URL to dashboard
    path('', lambda request: redirect('dashboard'), name='home'),

    # Authentication
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='certificates/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),

    # Certificate workflow
    path('choose/', views.choose_certificate, name='choose_certificate'),
    path('submit-request/', views.submit_request, name='submit_request'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('request/<int:pk>/', views.request_detail, name='request_detail'),
    path('request/<int:pk>/<str:action>/', views.update_request_status, name='update_request_status'),

    # Eligibility management (admin only)
    path('manage-eligibility/', views.manage_eligibility, name='manage_eligibility'),

    # AJAX endpoints for hierarchical location filtering
    path('api/get-provinces/', views.get_provinces, name='get_provinces'),
    path('api/get-districts/', views.get_districts, name='get_districts'),
    path('api/get-sectors/', views.get_sectors, name='get_sectors'),
    path('api/get-cells/', views.get_cells, name='get_cells'),
    path('api/get-villages/', views.get_villages, name='get_villages'),
    path('api/get-location-code/', views.get_location_code, name='get_location_code'),
]
