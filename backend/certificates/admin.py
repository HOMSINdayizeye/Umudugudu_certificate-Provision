from django.contrib import admin

from .models import (
    CustomUser, CertificateRequest, RequestAttachment, Announcement, Citizen, ServicePayment, LocationImport,
)


@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'village', 'phone')
    list_filter = ('role',)
    search_fields = ('username', 'email', 'first_name', 'last_name')


class RequestAttachmentInline(admin.TabularInline):
    model = RequestAttachment
    extra = 0


@admin.register(CertificateRequest)
class CertificateRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'cert_type', 'status', 'created_at', 'approved_by')
    list_filter = ('cert_type', 'status')
    inlines = [RequestAttachmentInline]


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('id', 'kind', 'language', 'letter_date', 'event_date', 'published', 'created_by')
    list_filter = ('kind', 'language', 'published')


admin.site.register(Citizen)
admin.site.register(ServicePayment)
admin.site.register(LocationImport)
