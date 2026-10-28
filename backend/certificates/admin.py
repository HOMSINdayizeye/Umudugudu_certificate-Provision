from django.contrib import admin

from .models import (
    CustomUser, CertificateRequest, RequestAttachment, Announcement, Citizen, CitizenTransfer, ServicePayment,
    LocationImport, RolePolicy, Activity, Attendance, SystemSetting, DeathReport, LeaderNotice, LeaderInquiry,
    PopulationFigure, CensusIndicator,
)


@admin.register(PopulationFigure)
class PopulationFigureAdmin(admin.ModelAdmin):
    list_display = ('location', 'level', 'year', 'kind', 'total', 'male', 'female', 'households', 'source')
    list_filter = ('kind', 'level', 'year')
    search_fields = ('location',)


@admin.register(CensusIndicator)
class CensusIndicatorAdmin(admin.ModelAdmin):
    list_display = ('location', 'level', 'year', 'key', 'value')
    list_filter = ('level', 'year', 'key')
    search_fields = ('location', 'key')


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
    list_display = ('id', 'citizen', 'from_village', 'to_village', 'status', 'to_isibo', 'transferred_by',
                    'transferred_at', 'decided_at', 'placed_at')
    list_filter = ('status', 'from_village', 'to_village')
admin.site.register(LocationImport)


@admin.register(LeaderNotice)
class LeaderNoticeAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'audience', 'area_code', 'created_by', 'created_at')
    filter_horizontal = ('excluded',)


@admin.register(LeaderInquiry)
class LeaderInquiryAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'from_user', 'role', 'to_location', 'answered_by', 'contact_status', 'created_at')
