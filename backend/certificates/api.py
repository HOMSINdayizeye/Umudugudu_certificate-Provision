import io
import os
import datetime

from django.conf import settings
from django.db.models import TextField
from django.db.models.functions import Cast, Length
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from docx import Document

from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import (
    CustomUser, CertificateRequest, StolenLaptopCertificate, LocationImport,
    ServicePayment, Citizen,
)
from .serializers import (
    RegisterSerializer, AdminCreateUserSerializer, LoginSerializer, UserSerializer,
    CertificateRequestSerializer, StolenLaptopCertificateSerializer,
    LocationImportSerializer, ServicePaymentSerializer, CitizenSerializer,
)

LEADER_STAGE = {
    # role -> (status it can act on, status approval moves the request to)
    'village_leader': ('pending', 'village_approved'),
    'cell_leader': ('village_approved', 'cell_approved'),
    'sector_leader': ('cell_approved', 'approved'),
}

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
        if is_admin(user):
            qs = CertificateRequest.objects.all()
        elif user.role in LEADER_STAGE and user.scope_code:
            # Leaders see every request in their jurisdiction, plus their own
            scoped = [r.pk for r in CertificateRequest.objects.select_related('user')
                      if in_scope(request_location_code(r), user.scope_code)]
            qs = CertificateRequest.objects.filter(pk__in=scoped) | CertificateRequest.objects.filter(user=user)
        else:
            qs = CertificateRequest.objects.filter(user=user)
        qs = qs.select_related('user').order_by('-created_at')
        return Response(CertificateRequestSerializer(qs, many=True).data)

    serializer = CertificateRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    cert_request = serializer.save(user=user, status='pending', email=user.email or 'unknown@example.com')

    # Stolen computer requests carry extra device details
    if cert_request.cert_type == 'stolen_computer' and request.data.get('stolen_device'):
        device = StolenLaptopCertificateSerializer(data=request.data['stolen_device'])
        if device.is_valid():
            device.save()
        else:
            cert_request.delete()
            return Response({'stolen_device': device.errors}, status=status.HTTP_400_BAD_REQUEST)

    return Response(CertificateRequestSerializer(cert_request).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
def request_detail(request, pk):
    user = request.user
    req = get_object_or_404(CertificateRequest, pk=pk)
    allowed = (
        is_admin(user)
        or req.user_id == user.id
        or (user.role in LEADER_STAGE and in_scope(request_location_code(req), user.scope_code))
    )
    if not allowed:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(CertificateRequestSerializer(req).data)


@api_view(['POST'])
def update_request_status(request, pk, action):
    user = request.user
    req = get_object_or_404(CertificateRequest, pk=pk)

    if action not in ('approve', 'deny'):
        return Response({'detail': 'Invalid action.'}, status=status.HTTP_400_BAD_REQUEST)

    if is_admin(user):
        if action == 'approve':
            req.status = 'approved'
            req.admin_message = 'Your request has been approved.'
        else:
            req.status = 'denied'
            req.admin_message = 'Your request has been denied.'
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
        req.status = next_status
        if next_status == 'approved':
            req.admin_message = 'Your request has been fully approved.'
        else:
            req.admin_message = f'Approved by {role_label}. Awaiting next level approval.'
    else:
        req.status = 'denied'
        req.admin_message = f'Your request has been denied by the {role_label}.'
    req.save()
    return Response(CertificateRequestSerializer(req).data)


@api_view(['GET'])
def download_certificate(request, pk):
    user = request.user
    if is_admin(user):
        req = get_object_or_404(CertificateRequest, pk=pk)
    else:
        req = get_object_or_404(CertificateRequest, pk=pk, user=user)
    if req.status != 'approved':
        return Response({'detail': 'Certificate is only available once the request is fully approved.'},
                        status=status.HTTP_403_FORBIDDEN)

    template_path = os.path.join(settings.BASE_DIR, 'certificates', 'templates_docs', 'conduct_template.docx')
    doc = Document(template_path)

    def location_name(location_id):
        if not location_id:
            return ''
        loc = LocationImport.objects.filter(location_id=location_id).first()
        return loc.name if loc else ''

    replacements = {
        '{{name}}': f'{req.user.first_name} {req.user.last_name}'.strip() or req.user.username,
        '{{province_name}}': location_name(req.province),
        '{{district_name}}': location_name(req.district),
        '{{sector_name}}': location_name(req.sector),
        '{{cell_name}}': location_name(req.cell),
        '{{village_name}}': location_name(req.village),
        '{{date}}': datetime.date.today().strftime('%d/%m/%Y'),
    }

    for p in doc.paragraphs:
        for run in p.runs:
            for key, val in replacements.items():
                if key in run.text:
                    run.text = run.text.replace(key, val)

    output = io.BytesIO()
    doc.save(output)
    output.seek(0)
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    )
    response['Content-Disposition'] = f'attachment; filename=certificate_{req.pk}.docx'
    return response


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
