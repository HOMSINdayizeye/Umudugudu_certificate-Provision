from django.contrib import admin

from .models import (
    CustomUser, CertificateRequest, RequestAttachment, Announcement, Citizen, CitizenTransfer, ServicePayment,
    LocationImport, RolePolicy, Activity, Attendance, SystemSetting, DeathReport,
)


@admin.register(DeathReport)
class DeathReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'citizen', 'date_of_death', 'village', 'reported_by', 'reported_at')

admin.site.register(RolePolicy)
admin.site.register(SystemSetting)


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'kind', 'date', 'location_code', 'created_by')
    list_filter = ('kind',)


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('id', 'activity', 'citizen', 'marked_by', 'marked_at')


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


@admin.register(CitizenTransfer)
class CitizenTransferAdmin(admin.ModelAdmin):
    list_display = ('id', 'citizen', 'from_village', 'to_village', 'to_isibo', 'transferred_by', 'transferred_at', 'placed_at')
    list_filter = ('from_village', 'to_village')
admin.site.register(LocationImport)
