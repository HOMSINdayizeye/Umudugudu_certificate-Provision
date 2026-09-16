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
    RequestAttachment, Announcement,
)
from .serializers import (
    RegisterSerializer, AdminCreateUserSerializer, LoginSerializer, UserSerializer,
    CertificateRequestSerializer, RequestAttachmentSerializer, AnnouncementSerializer,
    LocationImportSerializer, ServicePaymentSerializer, CitizenSerializer,
)
from .documents import (
    render_request_document, render_announcement, announcement_paragraphs, location_chain,
    request_location_id, docx_to_pdf,
)

LEADER_STAGE = {
    # role -> (status it can act on, status approval moves the request to)
    # The village leader signs every letter, so their approval is final.
    'village_leader': ('pending', 'approved'),
    # Kept so requests already sitting at these older stages can still be completed
    'cell_leader': ('village_approved', 'cell_approved'),
    'sector_leader': ('cell_approved', 'approved'),
}

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


def generate_letter(req, signer):
    data, filename = render_request_document(req, leader=signer)
    if req.generated_document:
        req.generated_document.delete(save=False)
    req.generated_document.save(filename, ContentFile(data), save=False)


def generate_announcement_file(ann):
    data, filename = render_announcement(ann, ann.created_by)
    if ann.generated_document:
        ann.generated_document.delete(save=False)
    ann.generated_document.save(filename, ContentFile(data), save=False)
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


@api_view(['GET'])
def me(request):
    return Response(UserSerializer(request.user).data)


# ---------- Certificate requests ----------

@api_view(['GET', 'POST'])
def request_list(request):
    user = request.user

    if request.method == 'GET':
        qs = visible_requests_qs(user).select_related('user').order_by('-created_at')
        return Response(CertificateRequestSerializer(qs, many=True).data)

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
    return Response(CertificateRequestSerializer(cert_request).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
def request_detail(request, pk):
    req = get_object_or_404(CertificateRequest, pk=pk)
    if not can_view_request(request.user, req):
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(CertificateRequestSerializer(req).data)


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
    if req.status in ('approved', 'denied') and not is_admin(user):
        return Response({'detail': 'This request is closed; documents can no longer be added.'},
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

    if is_admin(user):
        if req.status in ('approved', 'denied'):
            return Response({'detail': 'This request is already closed.'}, status=status.HTTP_400_BAD_REQUEST)
        if action == 'approve':
            req.admin_message = message or 'Your request has been approved. Your letter is ready to download.'
            finalize_approval(req, user)
        else:
            req.status = 'denied'
            req.admin_message = message or 'Your request has been denied.'
        req.save()
        return Response(CertificateRequestSerializer(req).data)

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
        if next_status == 'approved':
            req.admin_message = message or f'Approved by the {role_label}. Your letter is ready to download.'
            finalize_approval(req, user)
        else:
            req.status = next_status
            req.admin_message = message or f'Approved by {role_label}. Awaiting next level approval.'
    else:
        req.status = 'denied'
        req.admin_message = message or f'Your request has been denied by the {role_label}.'
    req.save()
    return Response(CertificateRequestSerializer(req).data)


def finalize_approval(req, approver):
    """Mark approved and write the letter so it is ready the moment the citizen looks."""
    req.status = 'approved'
    req.approved_by = approver
    req.approved_at = timezone.now()
    generate_letter(req, signing_leader(req, approver))


@api_view(['GET'])
def download_certificate(request, pk):
    user = request.user
    req = get_object_or_404(CertificateRequest, pk=pk)
    if not can_view_request(user, req):
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
    if req.status != 'approved':
        return Response({'detail': 'The letter is only available once the request is approved.'},
                        status=status.HTTP_403_FORBIDDEN)

    can_regenerate = is_admin(user) or user.role in LEADER_STAGE
    wants_regenerate = request.GET.get('regenerate') == '1' and can_regenerate
    missing = not req.generated_document or not os.path.exists(req.generated_document.path)
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
    reqs = visible_requests_qs(user).filter(status='approved').select_related('user', 'approved_by')
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
    if not ann.generated_document or not os.path.exists(ann.generated_document.path):
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
