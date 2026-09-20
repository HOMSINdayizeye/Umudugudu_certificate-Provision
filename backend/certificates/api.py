import io
import os
import re
import datetime

from django.conf import settings
from django.core.files.base import ContentFile
from django.db.models import Q, TextField, Count, Prefetch
from django.db.models.functions import Cast, Length
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import (
    CustomUser, CertificateRequest, LocationImport, ServicePayment, Citizen, CitizenTransfer,
    RequestAttachment, Announcement, Notification, RolePolicy, Activity, Attendance, SystemSetting, DeathReport,
)
from .permissions import CATALOG, ROLE_DEFAULTS, has_perm, role_permissions, clean_keys, is_full_admin
from .serializers import (
    RegisterSerializer, AdminCreateUserSerializer, LoginSerializer, UserSerializer,
    CertificateRequestSerializer, RequestAttachmentSerializer, AnnouncementSerializer,
    LocationImportSerializer, ServicePaymentSerializer, CitizenSerializer, CitizenTransferSerializer,
    NotificationSerializer, ProfileUpdateSerializer, ChangePasswordSerializer, can_see_codes, location_path,
    ActivitySerializer, AttendanceSerializer, DeathReportSerializer,
)
from .documents import (
    render_request_document, render_announcement, announcement_paragraphs, location_chain,
    request_location_id, docx_to_pdf, build_table_docx, build_table_pdf,
)

LEADER_STAGE = {
    # role -> (status it can act on, status approval moves the request to)
    # Village leader issues the letter; cell and sector leaders endorse it afterwards, each adding a code
    'village_leader': ('pending', 'village_approved'),
    'cell_leader': ('village_approved', 'cell_approved'),
    'sector_leader': ('cell_approved', 'approved'),
}
NEXT_STATUS = {'pending': 'village_approved', 'village_approved': 'cell_approved', 'cell_approved': 'approved'}
# status reached -> (level name, digits of the location code used as the code prefix)
LEVEL_FOR_STATUS = {'village_approved': ('village', 8), 'cell_approved': ('cell', 6), 'approved': ('sector', 4)}
ISSUED_STATUSES = CertificateRequest.ISSUED_STATUSES

# Fields each letter cannot be written without
REQUIRED_DETAILS = {
    'conduct': ['full_name', 'father_name', 'mother_name', 'dob', 'national_id'],
    'residence': ['full_name', 'national_id', 'dob', 'father_name', 'mother_name', 'resident_since'],
    'stolen_computer': ['full_name', 'id_number', 'incident_date', 'incident_location', 'device_type', 'brand',
                        'serial_number'],
    'community': ['full_name', 'national_id', 'activities'],
    'other': [],
}
ALLOWED_ATTACHMENT_EXT = {'.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx'}
MAX_ATTACHMENTS = 10
ANNOUNCER_ROLES = ('village_leader', 'cell_leader', 'sector_leader')
DOCX_MIME = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'

VOLUNTEER_SERVICE = {
    'cleaning_volunteer': 'cleaning',
    'security_volunteer': 'security',
}


def is_admin(user):
    return user.is_superuser or user.role == 'system_admin'


def request_location_code(req):
    # Most specific location on the request, falling back to the requester's village
    return (req.location_code or req.village or req.cell or req.sector
            or req.district or req.province or req.user.village)


def in_scope(code, scope_code):
    if code is None or scope_code is None:
        return False
    return str(code).startswith(str(scope_code))


def scope_queryset_by_village_prefix(qs, field, scope_code):
    # Match hierarchical location ids by string prefix (e.g. village 101010101 is in cell 101010)
    return qs.annotate(_loc=Cast(field, TextField())).filter(_loc__startswith=str(scope_code))


def location_fields_from(village_id):
    """Split an 8-digit village id into the province…village ids stored on a request."""
    s = str(village_id)
    out = {}
    for key, n in (('province', 1), ('district', 2), ('sector', 4), ('cell', 6), ('village', 8)):
        if len(s) >= n:
            out[key] = int(s[:n])
    out['location_code'] = int(s)
    return out


def can_view_request(user, req):
    return (
        is_admin(user)
        or req.user_id == user.id
        or (user.role in LEADER_STAGE and in_scope(request_location_code(req), user.scope_code))
    )


def signing_leader(req, fallback):
    """The village leader of the request's village signs the letter; fall back to whoever approved."""
    code = request_location_id(req)
    leader = CustomUser.objects.filter(role='village_leader', village=code).first() if code else None
    return leader or fallback


def req_data(obj, user, many=False):
    """Serialize with the viewer in context so the verification code is only shown to leaders."""
    return CertificateRequestSerializer(obj, many=many, context={'user': user}).data


def code_taken(code):
    return CertificateRequest.objects.filter(Q(verification_code=code) | Q(code_history__contains=[{'code': code}])).exists()


def issue_level_code(req, level, digits, approver):
    """Code for one approval level: that level's location code + running number of at least two digits.
    Village 11090309 → 1109030901…, cell 110903 → 11090301…, sector 1109 → 110901…"""
    loc = str(request_location_id(req) or '')
    prefix = loc[:digits] if len(loc) >= digits else (loc or '0')
    n = CertificateRequest.objects.filter(code_history__contains=[{'level': level, 'prefix': prefix}]).count() + 1
    while code_taken(f'{prefix}{n:02d}'):
        n += 1
    code = f'{prefix}{n:02d}'
    history = list(req.code_history or [])
    history.append({'level': level, 'prefix': prefix, 'code': code,
                    'by': approver.display_name if approver else '', 'at': timezone.now().isoformat()})
    req.code_history = history
    req.verification_code = code
    return code


def issue_verification_code(req):
    """Village-level code for a letter that somehow has none yet (older data)."""
    if not req.verification_code:
        issue_level_code(req, 'village', 8, req.approved_by)
    return req.verification_code


def applicant_name(req):
    details = req.details if isinstance(req.details, dict) else {}
    return details.get('full_name') or req.user.display_name


def leaders_for(req, role, digits):
    """Leaders of the given role whose area contains the request's village."""
    loc = str(request_location_id(req) or '')
    if len(loc) < digits:
        return CustomUser.objects.none()
    field = {'village_leader': 'village', 'cell_leader': 'cell', 'sector_leader': 'sector'}[role]
    return CustomUser.objects.filter(role=role, **{field: int(loc[:digits])})


def notify(users, req, title, message):
    for u in users:
        Notification.objects.create(user=u, request=req, link=f'/requests/{req.id}', title=title, message=message)


def notify_users(users, title, message, link=''):
    for u in users:
        Notification.objects.create(user=u, link=link, title=title, message=message)


def notify_stage(req, approver, level, prev_code):
    """Who hears what after each approval level; the citizen never receives a code."""
    kind = req.get_cert_type_display()
    who = applicant_name(req)
    code = req.verification_code
    if level == 'village':
        notify(leaders_for(req, 'cell_leader', 6), req, f'{kind} issued · awaiting your approval',
               f'Code {code}: {kind} for {who} approved by village leader {approver.display_name}. '
               f'Open it to review and endorse.')
        notify([req.user], req, 'Your letter is ready',
               f'Your {kind} has been approved by the village leader. Open the request to view the letter.')
    elif level == 'cell':
        notify(leaders_for(req, 'village_leader', 8), req, f'Cell approved {kind}',
               f'New code {code} replaces {prev_code} for {who}. Endorsed by cell leader {approver.display_name}.')
        notify(leaders_for(req, 'sector_leader', 4), req, f'{kind} endorsed by cell · awaiting your approval',
               f'Code {code} (previously {prev_code}): {kind} for {who}. Open it to review and endorse.')
        notify([req.user], req, 'Your letter was endorsed by the cell',
               f'Your {kind} has been approved by the cell leader. The updated letter is ready to open.')
    else:
        notify(list(leaders_for(req, 'village_leader', 8)) + list(leaders_for(req, 'cell_leader', 6)), req,
               f'Sector approved {kind}',
               f'Final code {code} replaces {prev_code} for {who}. Endorsed by sector leader {approver.display_name}.')
        notify([req.user], req, 'Your letter is fully approved',
               f'Your {kind} has been approved by the sector leader. The final letter is ready to open.')


def _replace_file(field_file, filename, data):
    """Store a new version; on Windows the old file may still be streaming to someone, so a locked copy is left behind."""
    if field_file:
        try:
            field_file.delete(save=False)
        except OSError:
            pass
    field_file.save(filename, ContentFile(data), save=False)


def generate_letter(req, signer):
    issue_verification_code(req)
    data, filename = render_request_document(req, leader=signer)
    _replace_file(req.generated_document, filename, data)


def generate_announcement_file(ann):
    data, filename = render_announcement(ann, ann.created_by)
    _replace_file(ann.generated_document, filename, data)
    ann.generated_at = timezone.now()


def send_stored_document(field_file, fmt):
    """Serve a stored .docx as-is, or converted to PDF when ?format=pdf."""
    filename = os.path.basename(field_file.name)
    if fmt == 'pdf':
        with field_file.open('rb') as fh:
            pdf = docx_to_pdf(fh.read())
        return FileResponse(io.BytesIO(pdf), as_attachment=True,
                            filename=os.path.splitext(filename)[0] + '.pdf', content_type='application/pdf')
    return FileResponse(field_file.open('rb'), as_attachment=True, filename=filename, content_type=DOCX_MIME)


def visible_requests_qs(user):
    if is_admin(user):
        return CertificateRequest.objects.all()
    if user.role in LEADER_STAGE and user.scope_code:
        # Leaders see every request in their jurisdiction, plus their own
        scoped = [r.pk for r in CertificateRequest.objects.select_related('user')
                  if in_scope(request_location_code(r), user.scope_code)]
        return CertificateRequest.objects.filter(pk__in=scoped) | CertificateRequest.objects.filter(user=user)
    return CertificateRequest.objects.filter(user=user)


# ---------- Auth ----------

@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    token, _ = Token.objects.get_or_create(user=user)
    return Response({'token': token.key, 'user': UserSerializer(user).data}, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.validated_data['user']
    token, _ = Token.objects.get_or_create(user=user)
    return Response({'token': token.key, 'user': UserSerializer(user).data})


@api_view(['POST'])
def logout(request):
    Token.objects.filter(user=request.user).delete()
    return Response({'detail': 'Logged out.'})


@api_view(['GET', 'PATCH'])
def me(request):
    if request.method == 'PATCH':
        serializer = ProfileUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
    return Response(UserSerializer(request.user).data)


@api_view(['POST'])
def change_password(request):
    serializer = ChangePasswordSerializer(data=request.data, context={'user': request.user})
    serializer.is_valid(raise_exception=True)
    request.user.set_password(serializer.validated_data['new_password'])
    request.user.save()
    return Response({'detail': 'Password changed. You stay signed in on this device.'})


# ---------- Certificate requests ----------

@api_view(['GET', 'POST'])
def request_list(request):
    user = request.user

    if request.method == 'GET':
        qs = visible_requests_qs(user).select_related('user').order_by('-created_at')
        return Response(req_data(qs, user, many=True))

    serializer = CertificateRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    cert_type = serializer.validated_data['cert_type']
    details = serializer.validated_data.get('details') or {}
    if not isinstance(details, dict):
        return Response({'details': 'Must be an object of field values.'}, status=status.HTTP_400_BAD_REQUEST)

    missing = {f: 'This field is required.' for f in REQUIRED_DETAILS.get(cert_type, [])
               if not str(details.get(f, '') or '').strip()}
    if missing:
        return Response({'details': missing}, status=status.HTTP_400_BAD_REQUEST)
    if cert_type == 'other' and not (serializer.validated_data.get('other_description') or '').strip():
        return Response({'other_description': 'Describe the document you need.'}, status=status.HTTP_400_BAD_REQUEST)

    # The community engagement letter needs a minimum number of recorded attendances
    if cert_type == 'community' and not is_admin(user):
        check = community_eligibility_for(user, details.get('national_id'))
        if not check['eligible']:
            return Response({'detail': check['message'], 'eligibility': check}, status=status.HTTP_400_BAD_REQUEST)

    # The letter is issued by the applicant's own village unless a location was chosen explicitly
    location = {}
    if not serializer.validated_data.get('village') and user.village:
        location = location_fields_from(user.village)
    if not location and not serializer.validated_data.get('village'):
        return Response({'village': 'Your account has no village. Select your location or ask the admin to set it.'},
                        status=status.HTTP_400_BAD_REQUEST)

    cert_request = serializer.save(user=user, status='pending', details=details,
                                   email=user.email or 'unknown@example.com', **location)
    return Response(req_data(cert_request, user), status=status.HTTP_201_CREATED)


@api_view(['GET', 'PATCH'])
def request_detail(request, pk):
    user = request.user
    req = get_object_or_404(CertificateRequest, pk=pk)
    if not can_view_request(user, req):
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
    if request.method == 'GET':
        return Response(req_data(req, user))

    # The applicant may correct a request only while it is still waiting for review
    if not (is_admin(user) or req.user_id == user.id):
        return Response({'detail': 'Only the applicant can edit this request.'}, status=status.HTTP_403_FORBIDDEN)
    if req.status != 'pending' and not is_admin(user):
        return Response({'detail': 'This request has already been reviewed and can no longer be edited.'},
                        status=status.HTTP_400_BAD_REQUEST)

    details = request.data.get('details', req.details)
    if not isinstance(details, dict):
        return Response({'details': 'Must be an object of field values.'}, status=status.HTTP_400_BAD_REQUEST)
    missing = {f: 'This field is required.' for f in REQUIRED_DETAILS.get(req.cert_type, [])
               if not str(details.get(f, '') or '').strip()}
    if missing:
        return Response({'details': missing}, status=status.HTTP_400_BAD_REQUEST)
    if 'other_description' in request.data:
        req.other_description = (request.data.get('other_description') or '').strip()
    if req.cert_type == 'other' and not req.other_description:
        return Response({'other_description': 'Describe the document you need.'}, status=status.HTTP_400_BAD_REQUEST)
    req.details = details
    req.save()
    return Response(req_data(req, user))


# ---------- Attachments ----------

@api_view(['GET', 'POST'])
def attachment_list(request, pk):
    user = request.user
    req = get_object_or_404(CertificateRequest, pk=pk)
    if not can_view_request(user, req):
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(RequestAttachmentSerializer(req.attachments.order_by('uploaded_at'), many=True).data)

    if not (req.user_id == user.id or is_admin(user)):
        return Response({'detail': 'Only the applicant can add documents to this request.'},
                        status=status.HTTP_403_FORBIDDEN)
    if req.status != 'pending' and not is_admin(user):
        return Response({'detail': 'This request is under review; documents can no longer be added.'},
                        status=status.HTTP_400_BAD_REQUEST)

    files = request.FILES.getlist('files') or request.FILES.getlist('file')
    if not files:
        return Response({'detail': 'Choose at least one file.'}, status=status.HTTP_400_BAD_REQUEST)
    if req.attachments.count() + len(files) > MAX_ATTACHMENTS:
        return Response({'detail': f'A request can hold at most {MAX_ATTACHMENTS} files.'},
                        status=status.HTTP_400_BAD_REQUEST)

    kind = request.data.get('kind', 'other')
    if kind not in dict(RequestAttachment.KIND_CHOICES):
        kind = 'other'
    limit = settings.MAX_ATTACHMENT_MB * 1024 * 1024
    created = []
    for f in files:
        ext = os.path.splitext(f.name)[1].lower()
        if ext not in ALLOWED_ATTACHMENT_EXT:
            return Response({'detail': f'{f.name}: only PDF, JPG, PNG, DOC and DOCX files are accepted.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if f.size > limit:
            return Response({'detail': f'{f.name} is larger than {settings.MAX_ATTACHMENT_MB} MB.'},
                            status=status.HTTP_400_BAD_REQUEST)
        created.append(RequestAttachment.objects.create(
            request=req, kind=kind, file=f, original_name=f.name[:255], size=f.size))
    return Response(RequestAttachmentSerializer(created, many=True).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
def attachment_download(request, pk):
    att = get_object_or_404(RequestAttachment.objects.select_related('request__user'), pk=pk)
    if not can_view_request(request.user, att.request):
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
    return FileResponse(att.file.open('rb'), as_attachment=True, filename=att.original_name)


@api_view(['DELETE'])
def attachment_delete(request, pk):
    user = request.user
    att = get_object_or_404(RequestAttachment.objects.select_related('request'), pk=pk)
    if not (is_admin(user) or (att.request.user_id == user.id and att.request.status == 'pending')):
        return Response({'detail': 'This document can no longer be removed.'}, status=status.HTTP_403_FORBIDDEN)
    att.file.delete(save=False)
    att.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
def update_request_status(request, pk, action):
    user = request.user
    req = get_object_or_404(CertificateRequest, pk=pk)

    if action not in ('approve', 'deny'):
        return Response({'detail': 'Invalid action.'}, status=status.HTTP_400_BAD_REQUEST)
    message = (request.data.get('message') or '').strip()

    STAGE_MESSAGE = {
        'village_approved': 'Approved by the village leader. Your letter is ready to open; the cell leader will endorse it next.',
        'cell_approved': 'Endorsed by the cell leader. Your updated letter is ready; the sector leader will endorse it next.',
        'approved': 'Fully approved and endorsed by the sector leader. Your final letter is ready.',
    }

    if is_admin(user):
        if req.status in ('approved', 'denied'):
            return Response({'detail': 'This request is already closed.'}, status=status.HTTP_400_BAD_REQUEST)
        if action == 'approve':
            next_status = NEXT_STATUS[req.status]
            req.admin_message = message or STAGE_MESSAGE[next_status]
            advance_approval(req, user, next_status)
        else:
            req.status = 'denied'
            req.admin_message = message or 'Your request has been denied.'
        req.save()
        return Response(req_data(req, user))

    stage = LEADER_STAGE.get(user.role)
    if not stage or not has_perm(user, 'approve:requests'):
        return Response({'detail': 'You are not allowed to approve requests.'}, status=status.HTTP_403_FORBIDDEN)
    if not in_scope(request_location_code(req), user.scope_code):
        return Response({'detail': 'This request is outside your jurisdiction.'}, status=status.HTTP_403_FORBIDDEN)

    actionable_status, next_status = stage
    if req.status != actionable_status:
        return Response(
            {'detail': f'This request is not awaiting your approval (current status: {req.get_status_display()}).'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    role_label = user.get_role_display()
    if action == 'approve':
        req.admin_message = message or STAGE_MESSAGE[next_status]
        advance_approval(req, user, next_status)
    else:
        req.status = 'denied'
        req.admin_message = message or f'Your request has been denied by the {role_label}.'
    req.save()
    return Response(req_data(req, user))


def advance_approval(req, approver, next_status):
    """Move one level up the chain: new code for that level, letter re-stamped, everyone concerned notified."""
    prev_code = req.verification_code
    level, digits = LEVEL_FOR_STATUS[next_status]
    req.status = next_status
    if level == 'village':
        req.approved_by = approver
        req.approved_at = timezone.now()
    else:
        ends = list(req.endorsements or [])
        ends.append({'level': level, 'name': approver.display_name, 'at': timezone.localdate().isoformat()})
        req.endorsements = ends
    issue_level_code(req, level, digits, approver)
    generate_letter(req, signing_leader(req, req.approved_by or approver))
    notify_stage(req, approver, level, prev_code)


@api_view(['GET'])
def download_certificate(request, pk):
    user = request.user
    req = get_object_or_404(CertificateRequest, pk=pk)
    if not can_view_request(user, req):
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
    if req.status not in ISSUED_STATUSES:
        return Response({'detail': 'The letter is only available once the village leader has approved the request.'},
                        status=status.HTTP_403_FORBIDDEN)

    can_regenerate = is_admin(user) or user.role in LEADER_STAGE
    wants_regenerate = request.GET.get('regenerate') == '1' and can_regenerate
    # storage.exists works for the local disk and for cloud buckets alike (.path does not exist on S3)
    missing = not req.generated_document or not req.generated_document.storage.exists(req.generated_document.name)
    if wants_regenerate or missing:
        generate_letter(req, signing_leader(req, req.approved_by or user))
        req.save()

    # "?as=pdf" (not "format": DRF reserves that name for its own renderers)
    return send_stored_document(req.generated_document, request.GET.get('as'))


# ---------- Generated documents archive ----------

@api_view(['GET'])
def document_list(request):
    """Every generated letter the user may see, newest first, with Word and PDF links."""
    user = request.user
    items = []
    reqs = visible_requests_qs(user).filter(status__in=ISSUED_STATUSES).select_related('user', 'approved_by')
    for r in reqs:
        details = r.details if isinstance(r.details, dict) else {}
        items.append({
            'kind': 'request', 'id': r.id, 'title': r.get_cert_type_display(),
            'subject': details.get('full_name') or r.user.display_name,
            'created_at': r.approved_at or r.created_at,
            'created_by': r.approved_by.display_name if r.approved_by else '',
            'docx_url': f'/api/requests/{r.id}/certificate/download/',
            'pdf_url': f'/api/requests/{r.id}/certificate/download/?as=pdf',
            'link': f'/requests/{r.id}',
        })
    for a in announcements_qs(user).select_related('created_by'):
        items.append({
            'kind': 'announcement', 'id': a.id, 'title': a.get_kind_display(),
            'subject': a.title or a.venue or (a.event_date.isoformat() if a.event_date else ''),
            'created_at': a.created_at,
            'created_by': a.created_by.display_name if a.created_by else '',
            'docx_url': f'/api/announcements/{a.id}/download/',
            'pdf_url': f'/api/announcements/{a.id}/download/?as=pdf',
            'link': '/announcements',
        })
    items.sort(key=lambda x: x['created_at'] or timezone.now(), reverse=True)
    return Response(items)


# ---------- Table export (the list the user is looking at, as PDF or Word) ----------

@api_view(['POST'])
def export_table(request):
    """Body: {title, columns: [..], rows: [[..]], format: 'pdf'|'docx'}. Data comes from what the user already sees."""
    d = request.data
    title = str(d.get('title') or 'Export').strip()[:120]
    columns = [str(c)[:60] for c in (d.get('columns') or [])][:20]
    rows = d.get('rows') or []
    fmt = 'docx' if d.get('format') == 'docx' else 'pdf'
    if not columns or not isinstance(rows, list):
        return Response({'detail': 'Nothing to export.'}, status=status.HTTP_400_BAD_REQUEST)
    rows = [list(r)[:len(columns)] for r in rows[:5000] if isinstance(r, (list, tuple))]
    subtitle = f"Generated {timezone.localtime():%d %B %Y, %H:%M} by {request.user.display_name} · Certify, City of Kigali"
    slug = re.sub(r'[^A-Za-z0-9]+', '_', title).strip('_') or 'export'
    stamp = timezone.localdate().isoformat()
    if fmt == 'docx':
        data = build_table_docx(title, subtitle, columns, rows)
        return FileResponse(io.BytesIO(data), as_attachment=True, filename=f'{slug}_{stamp}.docx', content_type=DOCX_MIME)
    data = build_table_pdf(title, subtitle, columns, rows)
    return FileResponse(io.BytesIO(data), as_attachment=True, filename=f'{slug}_{stamp}.pdf', content_type='application/pdf')


# ---------- Notifications ----------

@api_view(['GET'])
def notification_list(request):
    qs = request.user.notifications.all()
    return Response({
        'unread': qs.filter(read_at__isnull=True).count(),
        'items': NotificationSerializer(qs[:30], many=True).data,
    })


@api_view(['POST'])
def notification_read(request, pk):
    n = get_object_or_404(Notification, pk=pk, user=request.user)
    if not n.read_at:
        n.read_at = timezone.now()
        n.save()
    return Response(NotificationSerializer(n).data)


@api_view(['POST'])
def notification_read_all(request):
    request.user.notifications.filter(read_at__isnull=True).update(read_at=timezone.now())
    return Response({'detail': 'All notifications marked as read.'})


# ---------- Verification codes (leaders only) ----------

def code_entry(r):
    return {
        'code': r.verification_code, 'request_id': r.id, 'cert_type': r.cert_type,
        'cert_type_display': r.get_cert_type_display(), 'applicant': applicant_name(r),
        'village_name': location_chain(request_location_id(r))['village'],
        'approved_at': r.approved_at, 'approved_by': r.approved_by.display_name if r.approved_by else '',
        'has_document': bool(r.generated_document),
        'status': r.status, 'status_display': r.get_status_display(),
        'history': r.code_history or [], 'endorsements': r.endorsements or [],
    }


@api_view(['GET'])
def code_list(request):
    user = request.user
    if not can_see_codes(user):
        return Response({'detail': 'Verification codes are only visible to leaders.'}, status=status.HTTP_403_FORBIDDEN)
    qs = (visible_requests_qs(user).filter(status__in=ISSUED_STATUSES).exclude(verification_code='')
          .select_related('user', 'approved_by').order_by('-approved_at'))
    q = (request.GET.get('q') or '').strip().lower()
    items = [code_entry(r) for r in qs]
    if q:
        items = [i for i in items if q in i['code'].lower() or q in (i['applicant'] or '').lower()]
    return Response(items)


@api_view(['GET'])
def code_lookup(request, code):
    """Check a code someone presents; leaders may verify any issued letter, not only those in their area."""
    user = request.user
    if not can_see_codes(user):
        return Response({'detail': 'Verification codes are only visible to leaders.'}, status=status.HTTP_403_FORBIDDEN)
    code = code.strip()
    r = (CertificateRequest.objects.filter(status__in=ISSUED_STATUSES)
         .filter(Q(verification_code__iexact=code) | Q(code_history__contains=[{'code': code}]))
         .select_related('user', 'approved_by').first())
    if not r:
        return Response({'valid': False, 'detail': 'No issued letter carries this code. Treat the document as unverified.'},
                        status=status.HTTP_404_NOT_FOUND)
    entry = code_entry(r)
    entry['valid'] = True
    entry['in_scope'] = can_view_request(user, r)
    # An older code still identifies the letter, but the holder should have the latest copy
    entry['superseded'] = r.verification_code.lower() != code.lower()
    return Response(entry)


# ---------- Announcements ----------

def announcements_qs(user):
    if is_admin(user):
        return Announcement.objects.all()
    if user.role == 'village_leader':
        return Announcement.objects.filter(Q(village=user.village) | Q(created_by=user))
    if user.role in ('cell_leader', 'sector_leader') and user.scope_code:
        qs = scope_queryset_by_village_prefix(Announcement.objects.all(), 'village', user.scope_code)
        return qs | Announcement.objects.filter(created_by=user)
    # Citizens and volunteers only read what their village leader has published
    return Announcement.objects.filter(published=True, village=user.village)


def can_announce(user):
    return has_perm(user, 'create:announcements')


def can_edit_announcement(user, ann):
    return is_admin(user) or ann.created_by_id == user.id


@api_view(['GET', 'POST'])
def announcement_list(request):
    user = request.user
    if request.method == 'GET':
        qs = announcements_qs(user).select_related('created_by')
        return Response({
            'can_create': can_announce(user),
            'announcements': AnnouncementSerializer(qs, many=True).data,
        })

    if not can_announce(user):
        return Response({'detail': 'Only village, cell or sector leaders can create announcements.'},
                        status=status.HTTP_403_FORBIDDEN)
    village = request.data.get('village') or user.village
    if not village:
        return Response({'village': 'Choose the village this announcement is for.'}, status=status.HTTP_400_BAD_REQUEST)
    serializer = AnnouncementSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    ann = serializer.save(created_by=user, village=int(village))
    generate_announcement_file(ann)
    ann.save()
    return Response(AnnouncementSerializer(ann).data, status=status.HTTP_201_CREATED)


@api_view(['GET', 'PATCH', 'DELETE'])
def announcement_detail(request, pk):
    user = request.user
    ann = get_object_or_404(Announcement, pk=pk)
    if not announcements_qs(user).filter(pk=pk).exists():
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(AnnouncementSerializer(ann).data)
    if not can_edit_announcement(user, ann):
        return Response({'detail': 'Only the author can change this announcement.'}, status=status.HTTP_403_FORBIDDEN)
    if request.method == 'DELETE':
        if ann.generated_document:
            ann.generated_document.delete(save=False)
        ann.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    serializer = AnnouncementSerializer(ann, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    ann = serializer.save()
    # Any edit beyond publishing changes the letter text, so rebuild the stored file
    if set(request.data.keys()) - {'published'}:
        generate_announcement_file(ann)
        ann.save()
    return Response(AnnouncementSerializer(ann).data)


@api_view(['POST'])
def announcement_preview(request):
    """Text of the announcement as it will read in the letter, for live preview while editing."""
    user = request.user
    if not can_announce(user):
        return Response({'detail': 'Not allowed.'}, status=status.HTTP_403_FORBIDDEN)
    village = request.data.get('village') or user.village
    chain = location_chain(village)
    paragraphs = announcement_paragraphs(request.data, chain, user.display_name)
    return Response({
        'letterhead': chain,
        'paragraphs': [{'style': s, 'text': t} for s, t in paragraphs],
    })


@api_view(['GET'])
def announcement_download(request, pk):
    user = request.user
    ann = get_object_or_404(Announcement, pk=pk)
    if not announcements_qs(user).filter(pk=pk).exists():
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
    if not ann.generated_document or not ann.generated_document.storage.exists(ann.generated_document.name):
        generate_announcement_file(ann)
        ann.save()
    return send_stored_document(ann.generated_document, request.GET.get('as'))


# ---------- Users (system admin) ----------

@api_view(['GET', 'POST'])
def user_list(request):
    needed = 'view:users' if request.method == 'GET' else 'add:users'
    if not has_perm(request.user, needed):
        return Response({'detail': 'You are not allowed to manage users.'}, status=status.HTTP_403_FORBIDDEN)

    if request.method == 'GET':
        users = CustomUser.objects.all().order_by('username')
        return Response(UserSerializer(users, many=True).data)

    serializer = AdminCreateUserSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


@api_view(['DELETE'])
def user_delete(request, pk):
    """Remove an account. Not yourself; admins only by admins; superusers only by superusers."""
    if not has_perm(request.user, 'delete:users'):
        return Response({'detail': 'You are not allowed to delete users.'}, status=status.HTTP_403_FORBIDDEN)
    target = get_object_or_404(CustomUser, pk=pk)
    if target.id == request.user.id:
        return Response({'detail': 'You cannot delete your own account.'}, status=status.HTTP_400_BAD_REQUEST)
    if target.is_superuser and not request.user.is_superuser:
        return Response({'detail': 'Only a superuser can delete another superuser.'}, status=status.HTTP_403_FORBIDDEN)
    if is_full_admin(target) and not is_full_admin(request.user):
        return Response({'detail': 'Only an administrator can delete another administrator.'},
                        status=status.HTTP_403_FORBIDDEN)
    name = target.display_name
    target.delete()
    return Response({'detail': f'{name} was deleted.'})


@api_view(['POST'])
def set_eligibility(request, pk):
    if not has_perm(request.user, 'eligibility:users'):
        return Response({'detail': 'You are not allowed to change eligibility.'}, status=status.HTTP_403_FORBIDDEN)
    user = get_object_or_404(CustomUser, pk=pk)
    user.is_eligible = bool(request.data.get('is_eligible'))
    user.save()
    return Response(UserSerializer(user).data)


# ---------- Roles & permissions ----------

def catalog_data():
    return [
        {'resource': g['resource'], 'label': g['label'],
         'actions': [{'key': k, 'description': d} for k, d in g['actions']]}
        for g in CATALOG
    ]


def roles_data():
    counts = {r['role']: r['n'] for r in CustomUser.objects.values('role').annotate(n=Count('id'))}
    saved = {p.role: p for p in RolePolicy.objects.all()}
    rows = []
    for role, label in CustomUser.ROLE_CHOICES:
        policy = saved.get(role)
        rows.append({
            'role': role,
            'label': label,
            'permissions': role_permissions(role),
            'defaults': ROLE_DEFAULTS.get(role, []),
            'customized': policy is not None,
            'updated_at': policy.updated_at if policy else None,
            'updated_by': policy.updated_by.display_name if policy and policy.updated_by else '',
            'users': counts.get(role, 0),
            # Administrators always hold every permission; their row cannot be edited
            'locked': role == 'system_admin',
        })
    return rows


@api_view(['GET'])
def permission_catalog(request):
    """Every grantable action plus the current permission set of each role."""
    if not has_perm(request.user, 'permissions:users'):
        return Response({'detail': 'You are not allowed to manage permissions.'}, status=status.HTTP_403_FORBIDDEN)
    return Response({'catalog': catalog_data(), 'roles': roles_data()})


@api_view(['PUT', 'DELETE'])
def set_role_permissions(request, role):
    """PUT {permissions: [...]} replaces what a role can do; DELETE returns the role to its defaults."""
    if not has_perm(request.user, 'permissions:users'):
        return Response({'detail': 'You are not allowed to manage permissions.'}, status=status.HTTP_403_FORBIDDEN)
    if role not in dict(CustomUser.ROLE_CHOICES):
        return Response({'detail': 'Unknown role.'}, status=status.HTTP_404_NOT_FOUND)
    if role == 'system_admin':
        return Response({'detail': 'The system admin always holds every permission.'}, status=status.HTTP_400_BAD_REQUEST)

    if request.method == 'DELETE':
        RolePolicy.objects.filter(role=role).delete()
    else:
        keys = request.data.get('permissions')
        if not isinstance(keys, list):
            return Response({'permissions': 'Send the list of permission keys.'}, status=status.HTTP_400_BAD_REQUEST)
        RolePolicy.objects.update_or_create(role=role, defaults={'permissions': clean_keys(keys),
                                                                  'updated_by': request.user})
    return Response({'roles': roles_data()})


@api_view(['PUT'])
def set_user_permissions(request, pk):
    """PUT {grants: [...], denies: [...]}: extra permissions for one user, and role permissions taken from them."""
    if not has_perm(request.user, 'permissions:users'):
        return Response({'detail': 'You are not allowed to manage permissions.'}, status=status.HTTP_403_FORBIDDEN)
    target = get_object_or_404(CustomUser, pk=pk)
    if is_full_admin(target):
        return Response({'detail': 'Administrators always hold every permission.'}, status=status.HTTP_400_BAD_REQUEST)
    grants = request.data.get('grants', [])
    denies = request.data.get('denies', [])
    if not isinstance(grants, list) or not isinstance(denies, list):
        return Response({'detail': 'grants and denies must be lists of permission keys.'},
                        status=status.HTTP_400_BAD_REQUEST)
    base = set(role_permissions(target.role))
    # Only keep overrides that change something: grants outside the role, denies inside it
    target.permission_grants = [k for k in clean_keys(grants) if k not in base]
    target.permission_denies = [k for k in clean_keys(denies) if k in base]
    target.save()
    return Response(UserSerializer(target).data)


# ---------- Citizens & service payments ----------

def area_code(user):
    # Location prefix a user's granted permissions apply to: their jurisdiction, else their own village
    return user.scope_code or user.village


def payment_scope(user):
    """Return (allowed, service_lock, scope_code). service_lock limits a volunteer to their own service."""
    if is_admin(user):
        return True, None, None
    if user.role in VOLUNTEER_SERVICE:
        return True, VOLUNTEER_SERVICE[user.role], user.village
    if user.role in ('village_leader', 'cell_leader', 'sector_leader'):
        return True, None, user.scope_code
    # Any other account the admin granted a permission to acts within its own village
    if user.village:
        return True, None, user.village
    return False, None, None


def can_see_citizen(user, citizen):
    if is_admin(user):
        return True
    if user.role == 'isibo_leader':
        if citizen.village != user.village:
            return False
        # His isibo's citizens, or citizens he registered himself
        return (citizen.added_by_id == user.id
                or (user.isibo and citizen.isibo.strip().lower() == user.isibo.strip().lower()))
    allowed, _, scope_code = payment_scope(user)
    return allowed and (scope_code is None or in_scope(citizen.village, scope_code))


def living():
    # Every citizen list and count in the system is of living citizens; the deceased stay in the death register
    return Citizen.objects.filter(status='alive')


def visible_citizens_qs(user):
    """Queryset of living registry citizens the user may view, or None if not allowed."""
    if is_admin(user):
        return living()
    if user.role == 'isibo_leader':
        if not user.village:
            return Citizen.objects.none()
        cond = Q(added_by=user)
        if user.isibo:
            cond = cond | Q(isibo__iexact=user.isibo)
        return living().filter(village=user.village).filter(cond)
    allowed, _, scope_code = payment_scope(user)
    if not allowed:
        return None
    qs = living()
    if scope_code is not None:
        qs = scope_queryset_by_village_prefix(qs, 'village', scope_code)
    return qs


def can_edit_citizen(user, citizen):
    # Editing needs the permission (isibo leaders by default) and the citizen must be in the user's view
    return has_perm(user, 'edit:citizens') and can_see_citizen(user, citizen)


def can_move_citizen(user, citizen, key):
    # transfer:citizens / place:citizens apply to citizens currently living inside the user's area
    if is_admin(user):
        return True
    return has_perm(user, key) and in_scope(citizen.village, area_code(user))


def is_village_id(value):
    return LocationImport.objects.filter(location_id=value, type='VILLAGE').exists()


def pending_transfer_prefetch():
    # Lets CitizenSerializer.pending_transfer read each citizen's open transfer without a query per row
    return Prefetch('transfers', queryset=CitizenTransfer.objects.filter(status='pending').select_related('transferred_by'),
                    to_attr='pending_transfers')


def village_leaders(village):
    return CustomUser.objects.filter(role='village_leader', village=village)


def citizen_label(citizen):
    return f'{citizen.first_name} {citizen.last_name}'.strip() + f' (ID {citizen.national_id})'


@api_view(['GET', 'POST'])
def citizen_list(request):
    """Citizen registry: isibo leaders add citizens; volunteers/leaders view with payment status."""
    user = request.user

    if request.method == 'POST':
        if not has_perm(user, 'add:citizens'):
            return Response({'detail': 'You are not allowed to add citizens.'}, status=status.HTTP_403_FORBIDDEN)

        # The citizen always lands in the creator's own village — no village picker.
        # Admins without an assigned village may pass one explicitly.
        village = user.village or request.data.get('village')
        if not village:
            return Response(
                {'detail': 'Your account has no village assigned, so citizens cannot be added. '
                           'Ask the system admin to assign your village.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = CitizenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        isibo = (request.data.get('isibo') or user.isibo or '').strip()
        citizen = serializer.save(added_by=user, village=village, isibo=isibo)
        return Response(CitizenSerializer(citizen).data, status=status.HTTP_201_CREATED)

    qs = visible_citizens_qs(user) if has_perm(user, 'view:citizens') else None
    if qs is None:
        return Response({'detail': 'You are not allowed to view citizens.'}, status=status.HTTP_403_FORBIDDEN)

    _, service_lock, _ = payment_scope(user)
    service = service_lock or request.GET.get('service', 'cleaning')
    try:
        year = int(request.GET.get('year', timezone.now().year))
    except ValueError:
        year = timezone.now().year

    qs = qs.order_by('first_name', 'last_name').prefetch_related(pending_transfer_prefetch())

    payments = ServicePayment.objects.filter(service=service, year=year, citizen__in=qs)
    paid_map = {}
    for p in payments:
        paid_map.setdefault(p.citizen_id, {})[p.trimester] = {'amount': str(p.amount), 'payment_id': p.id}

    data = []
    for c in qs:
        row = CitizenSerializer(c).data
        row['paid'] = paid_map.get(c.id, {})
        data.append(row)
    return Response({
        'service': service,
        'year': year,
        'can_add': has_perm(user, 'add:citizens'),
        'can_edit': has_perm(user, 'edit:citizens'),
        'can_delete': has_perm(user, 'delete:citizens'),
        'can_mark': has_perm(user, 'record:payments'),
        'can_transfer': has_perm(user, 'transfer:citizens'),
        'can_place': has_perm(user, 'place:citizens'),
        'citizens': data,
    })


@api_view(['GET', 'PATCH', 'PUT', 'DELETE'])
def citizen_detail(request, pk):
    user = request.user
    citizen = get_object_or_404(Citizen, pk=pk)

    if not (has_perm(user, 'view:citizens') and can_see_citizen(user, citizen)):
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(CitizenSerializer(citizen).data)

    if request.method == 'DELETE':
        if not has_perm(user, 'delete:citizens'):
            return Response({'detail': 'You are not allowed to delete citizens.'}, status=status.HTTP_403_FORBIDDEN)
        name = f'{citizen.first_name} {citizen.last_name}'.strip()
        citizen.delete()
        return Response({'detail': f'{name} was deleted.'})

    if not can_edit_citizen(user, citizen):
        return Response({'detail': 'You are not allowed to edit citizen information.'},
                        status=status.HTTP_403_FORBIDDEN)
    serializer = CitizenSerializer(citizen, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


# ---------- Citizen transfers between villages ----------

@api_view(['POST'])
def citizen_transfer(request, pk):
    """Ask to move a citizen to another village. Body: {village, note?}. The citizen stays here until accepted."""
    user = request.user
    citizen = get_object_or_404(Citizen, pk=pk)
    if not can_see_citizen(user, citizen):
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
    if not can_move_citizen(user, citizen, 'transfer:citizens'):
        return Response({'detail': 'You are not allowed to transfer citizens of this area.'},
                        status=status.HTTP_403_FORBIDDEN)
    if citizen.status != 'alive':
        return Response({'detail': 'A deceased citizen cannot be transferred.'}, status=status.HTTP_400_BAD_REQUEST)

    open_transfer = citizen.transfers.filter(status='pending').first()
    if open_transfer:
        return Response(
            {'detail': f'A transfer to {location_path(open_transfer.to_village)} is already waiting for confirmation. '
                       'Cancel it first to send the citizen elsewhere.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        to_village = int(request.data.get('village'))
    except (TypeError, ValueError):
        return Response({'village': 'Choose the village the citizen is moving to.'}, status=status.HTTP_400_BAD_REQUEST)
    if to_village == citizen.village:
        return Response({'village': 'The citizen already lives in this village.'}, status=status.HTTP_400_BAD_REQUEST)
    if not is_village_id(to_village):
        return Response({'village': 'Select the full location down to the village.'}, status=status.HTTP_400_BAD_REQUEST)

    transfer = CitizenTransfer.objects.create(
        citizen=citizen, from_village=citizen.village, from_isibo=citizen.isibo, to_village=to_village,
        note=(request.data.get('note') or '').strip(), transferred_by=user,
    )
    notify_users(
        village_leaders(to_village),
        'Citizen transfer awaiting your confirmation',
        f'{citizen_label(citizen)} is being transferred to your village from {location_path(transfer.from_village)} '
        f'by {user.display_name}. Open Transfers to accept or decline.',
        link='/transfers',
    )
    return Response(CitizenTransferSerializer(transfer).data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
def citizen_transfer_decide(request, pk, decision):
    """Destination leader accepts (body: {isibo?}) or declines (body: {note?}); the sender may cancel."""
    user = request.user
    if decision not in ('accept', 'reject', 'cancel'):
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
    transfer = get_object_or_404(CitizenTransfer.objects.select_related('citizen', 'transferred_by'), pk=pk)
    citizen = transfer.citizen
    if transfer.status != 'pending':
        return Response({'detail': f'This transfer was already {transfer.get_status_display().lower()}.'},
                        status=status.HTTP_400_BAD_REQUEST)

    if decision == 'cancel':
        # Only leaders of the village the citizen is leaving (or the sender) may withdraw the request
        allowed = is_admin(user) or transfer.transferred_by_id == user.id or (
            has_perm(user, 'transfer:citizens') and in_scope(transfer.from_village, area_code(user)))
        if not allowed:
            return Response({'detail': 'You are not allowed to cancel this transfer.'}, status=status.HTTP_403_FORBIDDEN)
    else:
        # Accept/decline belongs to the destination village's leaders
        allowed = is_admin(user) or (has_perm(user, 'place:citizens') and in_scope(transfer.to_village, area_code(user)))
        if not allowed:
            return Response({'detail': 'Only the leader of the receiving village can confirm this transfer.'},
                            status=status.HTTP_403_FORBIDDEN)

    now = timezone.now()
    transfer.decided_by = user
    transfer.decided_at = now
    transfer.decision_note = (request.data.get('note') or '').strip()
    senders = village_leaders(transfer.from_village)
    if transfer.transferred_by and transfer.transferred_by.role != 'village_leader':
        senders = list(senders) + [transfer.transferred_by]

    if decision == 'accept':
        isibo = (request.data.get('isibo') or '').strip()
        transfer.status = 'accepted'
        if isibo:
            transfer.to_isibo = isibo
            transfer.placed_by = user
            transfer.placed_at = now
        transfer.save()

        citizen.transferred_from_village = transfer.from_village
        citizen.transferred_from_isibo = transfer.from_isibo
        citizen.transferred_at = now
        citizen.transfer_placed_at = now if isibo else None
        citizen.village = transfer.to_village
        citizen.isibo = isibo
        citizen.save()

        where = f' and placed in isibo {isibo}' if isibo else ''
        notify_users(
            senders,
            'Citizen transfer accepted',
            f'{citizen_label(citizen)} was accepted into {location_path(transfer.to_village)}{where} '
            f'by {user.display_name}. They no longer appear among your citizens.',
            link='/transfers',
        )
        if isibo:
            notify_users(
                CustomUser.objects.filter(role='isibo_leader', village=citizen.village, isibo__iexact=isibo),
                'Transferred citizen added to your isibo',
                f'{citizen_label(citizen)} was transferred from {location_path(transfer.from_village)} '
                f'and placed in isibo {isibo} by {user.display_name}.',
                link='/citizens',
            )
    elif decision == 'reject':
        transfer.status = 'rejected'
        transfer.save()
        reason = f' Reason: {transfer.decision_note}' if transfer.decision_note else ''
        notify_users(
            senders,
            'Citizen transfer declined',
            f'{location_path(transfer.to_village)} declined to receive {citizen_label(citizen)} '
            f'({user.display_name}).{reason} The citizen stays in your village.',
            link='/transfers',
        )
    else:
        transfer.status = 'cancelled'
        transfer.save()
        notify_users(
            village_leaders(transfer.to_village),
            'Citizen transfer cancelled',
            f'The transfer of {citizen_label(citizen)} from {location_path(transfer.from_village)} '
            f'was cancelled by {user.display_name}.',
            link='/transfers',
        )
    return Response(CitizenTransferSerializer(transfer).data)


@api_view(['POST'])
def citizen_place(request, pk):
    """Destination village leader assigns a transferred citizen to an isibo. Body: {isibo}."""
    user = request.user
    citizen = get_object_or_404(Citizen, pk=pk)
    if not can_see_citizen(user, citizen):
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
    if not can_move_citizen(user, citizen, 'place:citizens'):
        return Response({'detail': 'You are not allowed to place citizens in this area.'},
                        status=status.HTTP_403_FORBIDDEN)
    if citizen.transferred_from_village is None:
        return Response({'detail': 'This citizen was not transferred; the isibo leader manages their isibo.'},
                        status=status.HTTP_400_BAD_REQUEST)

    isibo = (request.data.get('isibo') or '').strip()
    if not isibo:
        return Response({'isibo': 'Enter the isibo name.'}, status=status.HTTP_400_BAD_REQUEST)

    now = timezone.now()
    citizen.isibo = isibo
    citizen.transfer_placed_at = now
    citizen.save()
    transfer = citizen.transfers.filter(to_village=citizen.village, status='accepted').first()
    if transfer:
        transfer.to_isibo = isibo
        transfer.placed_by = user
        transfer.placed_at = now
        transfer.save()

    notify_users(
        CustomUser.objects.filter(role='isibo_leader', village=citizen.village, isibo__iexact=isibo),
        'Transferred citizen added to your isibo',
        f'{citizen_label(citizen)} was transferred from {location_path(citizen.transferred_from_village)} '
        f'and placed in isibo {isibo} by {user.display_name}.',
        link='/citizens',
    )
    return Response(CitizenSerializer(citizen).data)


@api_view(['GET'])
def citizen_transfer_list(request):
    """Leaders: citizens transferred into their area (to place) and out of it (with where they are now)."""
    user = request.user
    if not has_perm(user, 'view:transfers'):
        return Response({'detail': 'You are not allowed to view citizen transfers.'}, status=status.HTTP_403_FORBIDDEN)
    scope = None if is_admin(user) else area_code(user)
    flags = {'can_place': has_perm(user, 'place:citizens'), 'can_transfer': has_perm(user, 'transfer:citizens')}
    if scope is None and not is_admin(user):
        return Response({'pending_in': [], 'incoming': [], 'outgoing': [], **flags})

    # pending_in: transfers waiting for this area's leader to accept; incoming: citizens already accepted here
    pending_in = CitizenTransfer.objects.filter(status='pending').select_related('citizen', 'transferred_by')
    incoming = living().filter(transferred_from_village__isnull=False).prefetch_related(pending_transfer_prefetch())
    outgoing = CitizenTransfer.objects.select_related('citizen', 'transferred_by', 'placed_by', 'decided_by')
    if scope is not None:
        pending_in = scope_queryset_by_village_prefix(pending_in, 'to_village', scope)
        incoming = scope_queryset_by_village_prefix(incoming, 'village', scope)
        outgoing = scope_queryset_by_village_prefix(outgoing, 'from_village', scope)

    # Latest move per citizen only, and drop accepted moves whose citizen has since come back to the village they left
    seen = set()
    out_rows = []
    for t in outgoing:
        if t.citizen_id in seen or (t.status == 'accepted' and t.citizen.village == t.from_village):
            continue
        seen.add(t.citizen_id)
        out_rows.append(t)

    incoming = incoming.order_by('transfer_placed_at', '-transferred_at')
    return Response({
        'pending_in': CitizenTransferSerializer(pending_in.order_by('transferred_at'), many=True).data,
        'incoming': CitizenSerializer(incoming, many=True).data,
        'outgoing': CitizenTransferSerializer(out_rows, many=True).data,
        **flags,
    })


@api_view(['GET'])
def village_isibos(request):
    """Known isibo names in a village (from its citizens and isibo leaders) to help placement."""
    user = request.user
    try:
        village = int(request.GET.get('village') or user.village or 0)
    except ValueError:
        village = 0
    if not village:
        return Response([])
    allowed = has_perm(user, 'place:citizens') or has_perm(user, 'transfer:citizens')
    if not (is_admin(user) or (allowed and in_scope(village, area_code(user)))):
        return Response({'detail': 'This village is outside your area.'}, status=status.HTTP_403_FORBIDDEN)
    names = set(Citizen.objects.filter(village=village).exclude(isibo='').values_list('isibo', flat=True))
    names |= set(CustomUser.objects.filter(role='isibo_leader', village=village).exclude(isibo='')
                 .values_list('isibo', flat=True))
    return Response(sorted(names, key=str.lower))


@api_view(['GET', 'POST'])
def payment_list(request):
    user = request.user
    allowed, service_lock, scope_code = payment_scope(user)

    if request.method == 'POST':
        # Volunteers (their own service) by default; the admin may grant others
        if not (allowed and has_perm(user, 'record:payments')):
            return Response({'detail': 'You are not allowed to record payments.'}, status=status.HTTP_403_FORBIDDEN)

        service = service_lock or request.data.get('service')
        if service not in ('cleaning', 'security'):
            return Response({'service': 'Choose cleaning or security.'}, status=status.HTTP_400_BAD_REQUEST)

        citizen = get_object_or_404(Citizen, pk=request.data.get('citizen'))
        if scope_code is not None and not in_scope(citizen.village, scope_code):
            return Response({'detail': 'This citizen is not in your village.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            year = int(request.data.get('year'))
            amount = request.data.get('amount')
            trimesters = request.data.get('trimesters') or [int(request.data.get('trimester'))]
            trimesters = [int(t) for t in trimesters]
        except (TypeError, ValueError):
            return Response({'detail': 'year, amount and trimester(s) are required.'}, status=status.HTTP_400_BAD_REQUEST)
        if any(t not in (1, 2, 3) for t in trimesters):
            return Response({'detail': 'Trimester must be 1, 2 or 3.'}, status=status.HTTP_400_BAD_REQUEST)

        created = []
        skipped = []
        for t in trimesters:
            payment, was_created = ServicePayment.objects.get_or_create(
                citizen=citizen, service=service, trimester=t, year=year,
                defaults={'amount': amount, 'recorded_by': user},
            )
            (created if was_created else skipped).append(t)

        return Response({
            'created_trimesters': created,
            'already_paid_trimesters': skipped,
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    # GET — list payments with filters
    if not (allowed and has_perm(user, 'view:payments')):
        return Response({'detail': 'You are not allowed to view payments.'}, status=status.HTTP_403_FORBIDDEN)
    qs = ServicePayment.objects.all()
    if scope_code is not None:
        qs = scope_queryset_by_village_prefix(qs, 'citizen__village', scope_code)

    service = service_lock or request.GET.get('service')
    if service in ('cleaning', 'security'):
        qs = qs.filter(service=service)

    trimester = request.GET.get('trimester')
    if trimester in ('1', '2', '3'):
        qs = qs.filter(trimester=int(trimester))

    year = request.GET.get('year')
    if year and year.isdigit():
        qs = qs.filter(year=int(year))

    period = request.GET.get('period')  # this_month | last_month | all
    now = timezone.now()
    if period == 'this_month':
        qs = qs.filter(paid_at__year=now.year, paid_at__month=now.month)
    elif period == 'last_month':
        last = (now.replace(day=1) - datetime.timedelta(days=1))
        qs = qs.filter(paid_at__year=last.year, paid_at__month=last.month)

    qs = qs.select_related('citizen', 'recorded_by').order_by('-paid_at')
    return Response(ServicePaymentSerializer(qs, many=True).data)


@api_view(['DELETE'])
def payment_detail(request, pk):
    """Unmark a payment. Only the service's volunteer (in scope) or an admin can do this."""
    user = request.user
    payment = get_object_or_404(ServicePayment, pk=pk)

    if not is_admin(user):
        allowed, service_lock, scope_code = payment_scope(user)
        if not (allowed and has_perm(user, 'record:payments')):
            return Response({'detail': 'You are not allowed to unmark payments.'}, status=status.HTTP_403_FORBIDDEN)
        if service_lock and payment.service != service_lock:
            return Response({'detail': 'This payment belongs to a different service.'},
                            status=status.HTTP_403_FORBIDDEN)
        if scope_code is not None and not in_scope(payment.citizen.village, scope_code):
            return Response({'detail': 'This citizen is not in your area.'}, status=status.HTTP_403_FORBIDDEN)

    payment.delete()
    return Response({'detail': 'Payment unmarked.'}, status=status.HTTP_200_OK)


# ---------- Deceased register ----------

def deaths_scope_qs(user):
    """Death reports of the user's area (village leader: village; cell/sector leader: their whole area)."""
    qs = DeathReport.objects.select_related('citizen', 'reported_by')
    if is_admin(user):
        return qs
    code = area_code(user)
    if not code:
        return qs.none()
    return scope_queryset_by_village_prefix(qs, 'village', code)


@api_view(['GET', 'POST'])
def death_list(request):
    """GET: the deceased register of the area. POST: report a death ({citizen} or {new: {...}}, date_of_death…)."""
    user = request.user
    if request.method == 'GET':
        if not has_perm(user, 'view:deaths'):
            return Response({'detail': 'You are not allowed to view the deceased register.'}, status=status.HTTP_403_FORBIDDEN)
        return Response({
            'can_report': has_perm(user, 'report:deaths'),
            'reports': DeathReportSerializer(deaths_scope_qs(user), many=True).data,
        })

    if not has_perm(user, 'report:deaths'):
        return Response({'detail': 'Only the village leader can report a death.'}, status=status.HTTP_403_FORBIDDEN)
    serializer = DeathReportSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    new = request.data.get('new')
    if new:
        # Person never registered: create the record in the leader's village, then mark deceased
        village = user.village or new.get('village')
        if not village:
            return Response({'village': 'Your account has no village; choose the citizen’s village.'},
                            status=status.HTTP_400_BAD_REQUEST)
        cs = CitizenSerializer(data=new)
        cs.is_valid(raise_exception=True)
        citizen = cs.save(added_by=user, village=int(village), isibo=(new.get('isibo') or '').strip())
    else:
        pool = living() if is_admin(user) else citizens_in_area(area_code(user))
        citizen = pool.filter(pk=request.data.get('citizen')).first()
        if not citizen:
            return Response({'detail': 'This citizen is not in your area, or is already reported.'},
                            status=status.HTTP_404_NOT_FOUND)

    citizen.status = 'deceased'
    citizen.save()
    report = serializer.save(citizen=citizen, village=citizen.village, reported_by=user)
    return Response(DeathReportSerializer(report).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
def death_search(request):
    """Living citizens of the reporter's area matching ?q= (name, ID or phone), to pick who to report."""
    user = request.user
    if not has_perm(user, 'report:deaths'):
        return Response({'detail': 'Only the village leader can report a death.'}, status=status.HTTP_403_FORBIDDEN)
    q = (request.GET.get('q') or '').strip()
    if len(q) < 2:
        return Response([])
    pool = living() if is_admin(user) else citizens_in_area(area_code(user))
    qs = pool.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(national_id__icontains=q)
                     | Q(phone__icontains=q)).order_by('first_name', 'last_name')[:15]
    return Response(CitizenSerializer(qs, many=True).data)


@api_view(['DELETE'])
def death_detail(request, pk):
    """Undo a death report made by mistake: the citizen returns to the living register."""
    user = request.user
    report = deaths_scope_qs(user).filter(pk=pk).first()
    if not report:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
    if not has_perm(user, 'report:deaths'):
        return Response({'detail': 'Only the village leader can undo a death report.'}, status=status.HTTP_403_FORBIDDEN)
    citizen = report.citizen
    name = f'{citizen.first_name} {citizen.last_name}'.strip()
    report.delete()
    citizen.status = 'alive'
    citizen.save()
    return Response({'detail': f'{name} is back in the living register.'})


# ---------- Activities & attendance ----------

def location_prefixes(code):
    # 11090309 -> [1, 11, 1109, 110903, 11090309]: the areas that contain this location
    s = str(code)
    return [int(s[:n]) for n in (1, 2, 4, 6, 8) if len(s) >= n]


def visible_activities_qs(user):
    """Activities in the user's area: inside it, or run by a wider area (cell/sector) that contains it."""
    if is_admin(user):
        return Activity.objects.all()
    code = area_code(user)
    if not code:
        return Activity.objects.filter(created_by=user)
    inside = scope_queryset_by_village_prefix(Activity.objects.all(), 'location_code', code)
    return (inside | Activity.objects.filter(location_code__in=location_prefixes(code))
            | Activity.objects.filter(created_by=user)).distinct()


def can_manage_activity(user, activity):
    if is_admin(user):
        return True
    return has_perm(user, 'create:activities') and (
        activity.created_by_id == user.id or in_scope(activity.location_code, area_code(user)))


def citizens_in_area(code):
    return scope_queryset_by_village_prefix(living(), 'village', code)


def with_counts(qs):
    return qs.annotate(attendance_count=Count('attendances'))


@api_view(['GET', 'POST'])
def activity_list(request):
    user = request.user
    if request.method == 'POST':
        if not has_perm(user, 'create:activities'):
            return Response({'detail': 'You are not allowed to create activities.'}, status=status.HTTP_403_FORBIDDEN)
        code = area_code(user) or request.data.get('location_code')
        if not code:
            return Response({'detail': 'Your account has no area assigned, so you cannot create activities.'},
                            status=status.HTTP_400_BAD_REQUEST)
        serializer = ActivitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        activity = serializer.save(created_by=user, location_code=int(code))
        return Response(ActivitySerializer(with_counts(Activity.objects.filter(pk=activity.pk)).first()).data,
                        status=status.HTTP_201_CREATED)

    if not has_perm(user, 'view:activities'):
        return Response({'detail': 'You are not allowed to view activities.'}, status=status.HTTP_403_FORBIDDEN)
    qs = with_counts(visible_activities_qs(user).select_related('created_by'))
    return Response({
        'can_create': has_perm(user, 'create:activities'),
        'can_mark': has_perm(user, 'mark:attendance'),
        'min_attendance': SystemSetting.min_attendance(),
        'activities': ActivitySerializer(qs, many=True).data,
    })


@api_view(['GET', 'PATCH', 'DELETE'])
def activity_detail(request, pk):
    user = request.user
    activity = get_object_or_404(with_counts(Activity.objects.all()), pk=pk)
    if not (has_perm(user, 'view:activities') and visible_activities_qs(user).filter(pk=pk).exists()):
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        attendances = activity.attendances.select_related('citizen', 'marked_by')
        return Response({
            'activity': ActivitySerializer(activity).data,
            'attendances': AttendanceSerializer(attendances, many=True).data,
            'can_edit': can_manage_activity(user, activity),
            'can_mark': has_perm(user, 'mark:attendance') and (is_admin(user) or in_scope(activity.location_code, area_code(user)) or in_scope(area_code(user), activity.location_code)),
        })

    if not can_manage_activity(user, activity):
        return Response({'detail': 'You are not allowed to change this activity.'}, status=status.HTTP_403_FORBIDDEN)
    if request.method == 'DELETE':
        title = activity.title
        activity.delete()
        return Response({'detail': f'Activity "{title}" and its attendance were deleted.'})
    serializer = ActivitySerializer(activity, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


def attendance_pool(user, activity=None):
    """Citizens a user may mark or count: admins all; isibo leaders only their own isibo (and citizens they
    registered); other leaders their area, narrowed to the activity's area when that is smaller."""
    if is_admin(user):
        return living()
    if user.role == 'isibo_leader':
        return visible_citizens_qs(user)
    code = area_code(user)
    if activity is not None:
        act = activity.location_code
        if not code or (len(str(act)) > len(str(code)) and in_scope(act, code)):
            code = act
    return citizens_in_area(code) if code else Citizen.objects.none()


@api_view(['GET', 'POST'])
def activity_attendance(request, pk):
    """GET ?q= searches citizens who can be marked; POST marks one ({citizen}) or registers and marks ({new: {...}})."""
    user = request.user
    activity = get_object_or_404(Activity, pk=pk)
    if not (has_perm(user, 'mark:attendance') and visible_activities_qs(user).filter(pk=pk).exists()):
        return Response({'detail': 'You are not allowed to mark attendance here.'}, status=status.HTTP_403_FORBIDDEN)
    pool = attendance_pool(user, activity)

    if request.method == 'GET':
        q = (request.GET.get('q') or '').strip()
        if len(q) < 2:
            return Response([])
        marked = set(activity.attendances.values_list('citizen_id', flat=True))
        qs = pool.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(national_id__icontains=q)
                         | Q(phone__icontains=q)).order_by('first_name', 'last_name')[:15]
        rows = []
        for c in qs:
            row = CitizenSerializer(c).data
            row['already_marked'] = c.id in marked
            rows.append(row)
        return Response(rows)

    new = request.data.get('new')
    if new:
        # Citizen not registered yet: create the record in the leader's village, then mark
        village = user.village or new.get('village') or (int(activity.location_code) if len(str(activity.location_code)) == 8 else None)
        if not village:
            return Response({'village': 'Choose the village of this citizen.'}, status=status.HTTP_400_BAD_REQUEST)
        serializer = CitizenSerializer(data=new)
        serializer.is_valid(raise_exception=True)
        # An isibo leader's new registrations always join their own isibo
        isibo = user.isibo if user.role == 'isibo_leader' and user.isibo else (new.get('isibo') or '').strip()
        citizen = serializer.save(added_by=user, village=int(village), isibo=isibo)
    else:
        citizen = pool.filter(pk=request.data.get('citizen')).first()
        if not citizen:
            detail = ('This citizen is not in your isibo.' if user.role == 'isibo_leader'
                      else 'This citizen is not in the activity’s area.')
            return Response({'detail': detail}, status=status.HTTP_404_NOT_FOUND)

    att, created = Attendance.objects.get_or_create(activity=activity, citizen=citizen, defaults={'marked_by': user})
    data = AttendanceSerializer(att).data
    data['created'] = created
    data['total_attendance'] = citizen.attendances.count()
    data['min_attendance'] = SystemSetting.min_attendance()
    return Response(data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


@api_view(['DELETE'])
def attendance_delete(request, pk, citizen_id):
    user = request.user
    activity = get_object_or_404(Activity, pk=pk)
    if not (has_perm(user, 'mark:attendance') and visible_activities_qs(user).filter(pk=pk).exists()):
        return Response({'detail': 'You are not allowed to change attendance here.'}, status=status.HTTP_403_FORBIDDEN)
    deleted, _ = Attendance.objects.filter(activity=activity, citizen_id=citizen_id).delete()
    if not deleted:
        return Response({'detail': 'No attendance to remove.'}, status=status.HTTP_404_NOT_FOUND)
    return Response({'detail': 'Attendance removed.'})


@api_view(['GET'])
def attendance_summary(request):
    """Every citizen of the area with their attendance total, the top attendee, and who qualifies."""
    user = request.user
    if not has_perm(user, 'view:activities'):
        return Response({'detail': 'You are not allowed to view attendance.'}, status=status.HTTP_403_FORBIDDEN)
    activities = visible_activities_qs(user)
    citizens = attendance_pool(user).annotate(
        attended=Count('attendances', filter=Q(attendances__activity__in=activities)),
    ).order_by('-attended', 'first_name', 'last_name')
    minimum = SystemSetting.min_attendance()
    rows = []
    for c in citizens:
        row = CitizenSerializer(c).data
        row['attended'] = c.attended
        row['eligible'] = c.attended >= minimum
        rows.append(row)
    return Response({
        'min_attendance': minimum,
        'activities_count': activities.count(),
        'top': rows[0] if rows and rows[0]['attended'] > 0 else None,
        'eligible_count': sum(1 for r in rows if r['eligible']),
        'citizens': rows,
    })


def community_eligibility_for(user, national_id=None):
    """Match the account to registry citizens (ID, email or phone) and compare attendance with the minimum."""
    minimum = SystemSetting.min_attendance()
    cond = Q()
    if national_id and str(national_id).strip():
        cond |= Q(national_id=str(national_id).strip())
    if user.email:
        cond |= Q(email__iexact=user.email)
    if user.phone:
        cond |= Q(phone=user.phone)
    matches = list(Citizen.objects.filter(cond)) if cond else []
    attended = Attendance.objects.filter(citizen__in=matches).values('activity').distinct().count() if matches else 0
    eligible = attended >= minimum
    if eligible:
        message = f'You qualify: {attended} attendance(s) recorded, minimum {minimum}.'
    elif not matches:
        message = (f'You are not eligible. No attendance is recorded under your ID, email or phone, and the minimum '
                   f'attendance for this certificate is {minimum}. Ask your leader to mark you at the next activity.')
    else:
        message = (f'You are not eligible. You have {attended} attendance(s) but the minimum attendance for this '
                   f'certificate is {minimum}.')
    return {
        'eligible': eligible, 'attended': attended, 'min_attendance': minimum, 'matched': bool(matches),
        'citizen_name': f'{matches[0].first_name} {matches[0].last_name}'.strip() if matches else '',
        'message': message,
    }


@api_view(['GET'])
def community_eligibility(request):
    """Whether the signed-in citizen may apply for the community engagement letter (?national_id= optional)."""
    if is_admin(request.user):
        return Response({'eligible': True, 'attended': 0, 'min_attendance': SystemSetting.min_attendance(),
                         'matched': True, 'citizen_name': '', 'message': 'Administrators are not restricted.'})
    return Response(community_eligibility_for(request.user, request.GET.get('national_id')))


@api_view(['GET', 'PUT'])
def attendance_setting(request):
    """The attendance count that makes a citizen eligible for the community engagement letter."""
    if request.method == 'PUT':
        if not has_perm(request.user, 'settings:attendance'):
            return Response({'detail': 'You are not allowed to change this setting.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            count = int(request.data.get('min_attendance'))
        except (TypeError, ValueError):
            count = -1
        if count < 0 or count > 1000:
            return Response({'min_attendance': 'Enter a whole number of attendances (0 to 1000).'},
                            status=status.HTTP_400_BAD_REQUEST)
        SystemSetting.objects.update_or_create(key='min_attendance',
                                               defaults={'value': {'count': count}, 'updated_by': request.user})
    row = SystemSetting.objects.filter(key='min_attendance').first()
    return Response({
        'min_attendance': SystemSetting.min_attendance(),
        'updated_at': row.updated_at if row else None,
        'updated_by': row.updated_by.display_name if row and row.updated_by else '',
        'can_edit': has_perm(request.user, 'settings:attendance'),
    })


# ---------- Locations (hierarchical filtering) ----------

def _children(location_type, parent_id, id_length, min_length=None):
    qs = LocationImport.objects.filter(type=location_type).annotate(
        id_str=Cast('location_id', TextField()),
    ).annotate(id_len=Length('id_str')).filter(id_str__startswith=str(parent_id))
    if min_length:
        qs = qs.filter(id_len__gte=min_length)
    else:
        qs = qs.filter(id_len=id_length)
    return qs.order_by('location_id')


@api_view(['GET'])
@permission_classes([AllowAny])
def provinces(request):
    qs = LocationImport.objects.filter(type='PROVINCE').order_by('location_id')
    return Response(LocationImportSerializer(qs, many=True).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def districts(request):
    parent = request.GET.get('province')
    if not parent:
        return Response([])
    return Response(LocationImportSerializer(_children('DISTRICT', parent, 2), many=True).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def sectors(request):
    parent = request.GET.get('district')
    if not parent:
        return Response([])
    return Response(LocationImportSerializer(_children('SECTOR', parent, 4), many=True).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def cells(request):
    parent = request.GET.get('sector')
    if not parent:
        return Response([])
    return Response(LocationImportSerializer(_children('CELL', parent, 6), many=True).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def villages(request):
    parent = request.GET.get('cell')
    if not parent:
        return Response([])
    return Response(LocationImportSerializer(_children('VILLAGE', parent, None, min_length=7), many=True).data)
