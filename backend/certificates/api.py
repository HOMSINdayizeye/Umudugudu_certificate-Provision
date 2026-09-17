import io
import os
import datetime

from django.conf import settings
from django.core.files.base import ContentFile
from django.db.models import Q, TextField
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
    CustomUser, CertificateRequest, LocationImport, ServicePayment, Citizen,
    RequestAttachment, Announcement, Notification,
)
from .serializers import (
    RegisterSerializer, AdminCreateUserSerializer, LoginSerializer, UserSerializer,
    CertificateRequestSerializer, RequestAttachmentSerializer, AnnouncementSerializer,
    LocationImportSerializer, ServicePaymentSerializer, CitizenSerializer, NotificationSerializer,
    ProfileUpdateSerializer, ChangePasswordSerializer, can_see_codes,
)
from .documents import (
    render_request_document, render_announcement, announcement_paragraphs, location_chain,
    request_location_id, docx_to_pdf,
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
    if not stage:
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
    return is_admin(user) or user.role in ANNOUNCER_ROLES


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
    if not is_admin(request.user):
        return Response({'detail': 'Only the system admin can manage users.'}, status=status.HTTP_403_FORBIDDEN)

    if request.method == 'GET':
        users = CustomUser.objects.all().order_by('username')
        return Response(UserSerializer(users, many=True).data)

    serializer = AdminCreateUserSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
def set_eligibility(request, pk):
    if not is_admin(request.user):
        return Response({'detail': 'Only the system admin can manage users.'}, status=status.HTTP_403_FORBIDDEN)
    user = get_object_or_404(CustomUser, pk=pk)
    user.is_eligible = bool(request.data.get('is_eligible'))
    user.save()
    return Response(UserSerializer(user).data)


# ---------- Citizens & service payments ----------

def payment_scope(user):
    """Return (allowed, service_lock, scope_code). service_lock limits a volunteer to their own service."""
    if is_admin(user):
        return True, None, None
    if user.role in VOLUNTEER_SERVICE:
        return True, VOLUNTEER_SERVICE[user.role], user.village
    if user.role in ('village_leader', 'cell_leader', 'sector_leader'):
        return True, None, user.scope_code
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


def visible_citizens_qs(user):
    """Queryset of registry citizens the user may view, or None if not allowed."""
    from django.db.models import Q
    if is_admin(user):
        return Citizen.objects.all()
    if user.role == 'isibo_leader':
        if not user.village:
            return Citizen.objects.none()
        cond = Q(added_by=user)
        if user.isibo:
            cond = cond | Q(isibo__iexact=user.isibo)
        return Citizen.objects.filter(village=user.village).filter(cond)
    allowed, _, scope_code = payment_scope(user)
    if not allowed:
        return None
    qs = Citizen.objects.all()
    if scope_code is not None:
        qs = scope_queryset_by_village_prefix(qs, 'village', scope_code)
    return qs


def can_edit_citizen(user, citizen):
    # Only the isibo leader of that citizen (or an admin) may edit the record
    if is_admin(user):
        return True
    return user.role == 'isibo_leader' and can_see_citizen(user, citizen)


@api_view(['GET', 'POST'])
def citizen_list(request):
    """Citizen registry: isibo leaders add citizens; volunteers/leaders view with payment status."""
    user = request.user

    if request.method == 'POST':
        if not (user.role == 'isibo_leader' or is_admin(user)):
            return Response({'detail': 'Only the isibo leader can add citizens.'}, status=status.HTTP_403_FORBIDDEN)

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

    qs = visible_citizens_qs(user)
    if qs is None:
        return Response({'detail': 'You are not allowed to view citizens.'}, status=status.HTTP_403_FORBIDDEN)

    _, service_lock, _ = payment_scope(user)
    service = service_lock or request.GET.get('service', 'cleaning')
    try:
        year = int(request.GET.get('year', timezone.now().year))
    except ValueError:
        year = timezone.now().year

    qs = qs.order_by('first_name', 'last_name')

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
        'can_edit': user.role == 'isibo_leader' or is_admin(user),
        'can_mark': user.role in VOLUNTEER_SERVICE or is_admin(user),
        'citizens': data,
    })


@api_view(['GET', 'PATCH', 'PUT'])
def citizen_detail(request, pk):
    user = request.user
    citizen = get_object_or_404(Citizen, pk=pk)

    if not can_see_citizen(user, citizen):
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(CitizenSerializer(citizen).data)

    if not can_edit_citizen(user, citizen):
        return Response({'detail': 'Only the isibo leader can edit citizen information.'},
                        status=status.HTTP_403_FORBIDDEN)
    serializer = CitizenSerializer(citizen, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@api_view(['GET', 'POST'])
def payment_list(request):
    user = request.user
    allowed, service_lock, scope_code = payment_scope(user)

    if request.method == 'POST':
        # Only volunteers (their own service) and admins can record payments
        if not (is_admin(user) or user.role in VOLUNTEER_SERVICE):
            return Response({'detail': 'Only service volunteers can record payments.'}, status=status.HTTP_403_FORBIDDEN)

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
    if not allowed:
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
        service = VOLUNTEER_SERVICE.get(user.role)
        if not service:
            return Response({'detail': 'Only service volunteers can unmark payments.'},
                            status=status.HTTP_403_FORBIDDEN)
        if payment.service != service:
            return Response({'detail': 'This payment belongs to a different service.'},
                            status=status.HTTP_403_FORBIDDEN)
        if not in_scope(payment.citizen.village, user.village):
            return Response({'detail': 'This citizen is not in your village.'}, status=status.HTTP_403_FORBIDDEN)

    payment.delete()
    return Response({'detail': 'Payment unmarked.'}, status=status.HTTP_200_OK)


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
