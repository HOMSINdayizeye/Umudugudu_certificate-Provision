import io
import os
import datetime

from django.conf import settings
from django.db.models import TextField
from django.db.models.functions import Cast, Length
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from docx import Document

from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response

from .models import CustomUser, CertificateRequest, StolenLaptopCertificate, LocationImport
from .serializers import (
    RegisterSerializer, LoginSerializer, UserSerializer,
    CertificateRequestSerializer, StolenLaptopCertificateSerializer,
    LocationImportSerializer,
)


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
    if request.method == 'GET':
        if request.user.is_superuser:
            qs = CertificateRequest.objects.all().order_by('-created_at')
        else:
            qs = CertificateRequest.objects.filter(user=request.user).order_by('-created_at')
        return Response(CertificateRequestSerializer(qs, many=True).data)

    serializer = CertificateRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    cert_request = serializer.save(user=request.user, status='pending', email=request.user.email or 'unknown@example.com')

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
    if request.user.is_superuser:
        req = get_object_or_404(CertificateRequest, pk=pk)
    else:
        req = get_object_or_404(CertificateRequest, pk=pk, user=request.user)
    return Response(CertificateRequestSerializer(req).data)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def update_request_status(request, pk, action):
    req = get_object_or_404(CertificateRequest, pk=pk)
    if action == 'approve':
        req.status = 'approved'
        req.admin_message = 'Your request has been approved.'
    elif action == 'deny':
        req.status = 'denied'
        req.admin_message = 'Your request has been denied.'
    else:
        return Response({'detail': 'Invalid action.'}, status=status.HTTP_400_BAD_REQUEST)
    req.save()
    return Response(CertificateRequestSerializer(req).data)


@api_view(['GET'])
def download_certificate(request, pk):
    if request.user.is_superuser:
        req = get_object_or_404(CertificateRequest, pk=pk)
    else:
        req = get_object_or_404(CertificateRequest, pk=pk, user=request.user)
    if req.status != 'approved':
        return Response({'detail': 'Certificate is only available once the request is approved.'},
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


# ---------- Admin: eligibility ----------

@api_view(['GET'])
@permission_classes([IsAdminUser])
def user_list(request):
    users = CustomUser.objects.all().order_by('username')
    return Response(UserSerializer(users, many=True).data)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def set_eligibility(request, pk):
    user = get_object_or_404(CustomUser, pk=pk)
    user.is_eligible = bool(request.data.get('is_eligible'))
    user.save()
    return Response(UserSerializer(user).data)


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
