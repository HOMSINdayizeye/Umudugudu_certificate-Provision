from django.urls import path
from . import api

urlpatterns = [
    # Auth
    path('auth/register/', api.register, name='api_register'),
    path('auth/login/', api.login, name='api_login'),
    path('auth/logout/', api.logout, name='api_logout'),
    path('auth/me/', api.me, name='api_me'),

    # Certificate requests (fixed sub-paths must come before the <action> catch-all)
    path('requests/', api.request_list, name='api_request_list'),
    path('requests/<int:pk>/', api.request_detail, name='api_request_detail'),
    path('requests/<int:pk>/attachments/', api.attachment_list, name='api_attachment_list'),
    path('requests/<int:pk>/certificate/download/', api.download_certificate, name='api_download_certificate'),
    path('requests/<int:pk>/<str:action>/', api.update_request_status, name='api_update_request_status'),
    path('attachments/<int:pk>/download/', api.attachment_download, name='api_attachment_download'),
    path('attachments/<int:pk>/', api.attachment_delete, name='api_attachment_delete'),

    # Announcements
    path('announcements/', api.announcement_list, name='api_announcement_list'),
    path('announcements/preview/', api.announcement_preview, name='api_announcement_preview'),
    path('announcements/<int:pk>/', api.announcement_detail, name='api_announcement_detail'),
    path('announcements/<int:pk>/download/', api.announcement_download, name='api_announcement_download'),

    # Admin: users & eligibility
    path('users/', api.user_list, name='api_user_list'),
    path('users/<int:pk>/eligibility/', api.set_eligibility, name='api_set_eligibility'),

    # Citizens & service payments
    path('citizens/', api.citizen_list, name='api_citizen_list'),
    path('citizens/<int:pk>/', api.citizen_detail, name='api_citizen_detail'),
    path('payments/', api.payment_list, name='api_payment_list'),
    path('payments/<int:pk>/', api.payment_detail, name='api_payment_detail'),

    # Locations
    path('locations/provinces/', api.provinces, name='api_provinces'),
    path('locations/districts/', api.districts, name='api_districts'),
    path('locations/sectors/', api.sectors, name='api_sectors'),
    path('locations/cells/', api.cells, name='api_cells'),
    path('locations/villages/', api.villages, name='api_villages'),
]
