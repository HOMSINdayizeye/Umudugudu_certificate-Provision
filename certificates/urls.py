from django.urls import path
from .import views
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect


urlpatterns = [
    path('', lambda request: redirect('dashboard/')),
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='certificates/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('choose/', views.choose_certificate, name='choose_certificate'),
    path('submit-request/', views.submit_request, name='submit_request'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('request/<int:pk>/', views.request_detail, name='request_detail'),
]