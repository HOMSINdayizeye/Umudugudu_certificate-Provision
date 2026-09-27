from django.urls import path
from . import api

urlpatterns = [
    # Auth
    path('auth/register/', api.register, name='api_register'),
    path('auth/login/', api.login, name='api_login'),
    path('auth/logout/', api.logout, name='api_logout'),
    path('auth/me/', api.me, name='api_me'),
    path('auth/change-password/', api.change_password, name='api_change_password'),

    # Certificate requests (fixed sub-paths must come before the <action> catch-all)
    path('requests/', api.request_list, name='api_request_list'),
    path('requests/<int:pk>/', api.request_detail, name='api_request_detail'),
    path('requests/<int:pk>/attachments/', api.attachment_list, name='api_attachment_list'),
    path('requests/<int:pk>/certificate/download/', api.download_certificate, name='api_download_certificate'),
    path('requests/<int:pk>/<str:action>/', api.update_request_status, name='api_update_request_status'),
    path('attachments/<int:pk>/download/', api.attachment_download, name='api_attachment_download'),
    path('attachments/<int:pk>/', api.attachment_delete, name='api_attachment_delete'),

    # Generated documents archive & table export
    path('documents/', api.document_list, name='api_document_list'),
    path('export/', api.export_table, name='api_export_table'),

    # Notifications & verification codes
    path('notifications/', api.notification_list, name='api_notification_list'),
    path('notifications/read-all/', api.notification_read_all, name='api_notification_read_all'),
    path('notifications/<int:pk>/read/', api.notification_read, name='api_notification_read'),
    path('codes/', api.code_list, name='api_code_list'),
    path('codes/<str:code>/', api.code_lookup, name='api_code_lookup'),

    # Leader dashboard: totals of the signed-in leader's own work
    path('dashboard/leader/', api.leader_stats, name='api_leader_stats'),

    # Announcements
    path('announcements/', api.announcement_list, name='api_announcement_list'),
    path('announcements/preview/', api.announcement_preview, name='api_announcement_preview'),
    path('announcements/<int:pk>/', api.announcement_detail, name='api_announcement_detail'),
    path('announcements/<int:pk>/download/', api.announcement_download, name='api_announcement_download'),
    # Leader-to-leader notices (sector -> cell leaders, cell -> village leaders); kept under announcements
    path('announcements/notices/', api.leader_notice_list, name='api_leader_notice_list'),
    path('announcements/notices/<int:pk>/', api.leader_notice_detail, name='api_leader_notice_detail'),

    # Admin: users & eligibility
    path('users/', api.user_list, name='api_user_list'),
    path('users/<int:pk>/', api.user_detail, name='api_user_detail'),
    path('users/<int:pk>/eligibility/', api.set_eligibility, name='api_set_eligibility'),
    path('users/<int:pk>/permissions/', api.set_user_permissions, name='api_set_user_permissions'),

    # Activities & attendance
    path('activities/', api.activity_list, name='api_activity_list'),
    path('activities/summary/', api.attendance_summary, name='api_attendance_summary'),
    path('activities/<int:pk>/', api.activity_detail, name='api_activity_detail'),
    path('activities/<int:pk>/attendance/', api.activity_attendance, name='api_activity_attendance'),
    path('activities/<int:pk>/attendance/<int:citizen_id>/', api.attendance_delete, name='api_attendance_delete'),
    path('community/eligibility/', api.community_eligibility, name='api_community_eligibility'),
    path('settings/attendance/', api.attendance_setting, name='api_attendance_setting'),

    # Roles & permissions
    path('permissions/', api.permission_catalog, name='api_permission_catalog'),
    path('permissions/roles/<str:role>/', api.set_role_permissions, name='api_set_role_permissions'),

    # Data management (system admin): counts and bulk deletion
    path('data/', api.data_overview, name='api_data_overview'),
    path('data/purge/', api.data_purge, name='api_data_purge'),

    # Citizens & service payments
    path('citizens/', api.citizen_list, name='api_citizen_list'),
    path('citizens/transfers/', api.citizen_transfer_list, name='api_citizen_transfer_list'),
    path('citizens/transfers/<int:pk>/<str:decision>/', api.citizen_transfer_decide, name='api_citizen_transfer_decide'),
    path('citizens/isibos/', api.village_isibos, name='api_village_isibos'),
    path('citizens/pick/', api.citizen_pick, name='api_citizen_pick'),
    path('citizens/deaths/', api.death_list, name='api_death_list'),
    path('citizens/deaths/search/', api.death_search, name='api_death_search'),
    path('citizens/deaths/<int:pk>/', api.death_detail, name='api_death_detail'),
    path('citizens/<int:pk>/', api.citizen_detail, name='api_citizen_detail'),
    path('citizens/<int:pk>/transfer/', api.citizen_transfer, name='api_citizen_transfer'),
    path('citizens/<int:pk>/place/', api.citizen_place, name='api_citizen_place'),
    path('payments/', api.payment_list, name='api_payment_list'),
    path('payments/<int:pk>/', api.payment_detail, name='api_payment_detail'),

    # Locations
    path('locations/provinces/', api.provinces, name='api_provinces'),
    path('locations/districts/', api.districts, name='api_districts'),
    path('locations/sectors/', api.sectors, name='api_sectors'),
    path('locations/cells/', api.cells, name='api_cells'),
    path('locations/villages/', api.villages, name='api_villages'),
]
