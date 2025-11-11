from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login as auth_login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from .forms import SignUpForm, CertificateRequestForm
from .models import EligiblePerson, CertificateRequest, CustomUser, LocationImport
from django.http import HttpResponseForbidden, HttpResponseBadRequest, JsonResponse
from django.conf import settings


def index(request):
    return render(request, 'certificates/index.html')


def register(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.email = form.cleaned_data['email']
            user.first_name = form.cleaned_data['first_name']
            user.last_name = form.cleaned_data['last_name']
            user.save()
            messages.success(request, 'Account created successfully!')
            return redirect('login')
    else:
        form = SignUpForm()
    
    return render(request, 'certificates/register.html', {'form': form})


@login_required
def choose_certificate(request):
    return render(request, 'certificates/choose_certificate.html')


@login_required
def submit_request(request):
    if request.user.is_superuser:
        return HttpResponseForbidden("Superusers cannot submit certificate requests.")

    if request.method == 'POST':
        form = CertificateRequestForm(request.POST)
        if form.is_valid():
            certificate_request = form.save(commit=False)
            certificate_request.user = request.user
            certificate_request.email = request.user.email
            
            # Save location data if conduct certificate
            if certificate_request.cert_type == 'conduct':
                certificate_request.province = request.POST.get('province')
                certificate_request.district = request.POST.get('district')
                certificate_request.sector = request.POST.get('sector')
                certificate_request.cell = request.POST.get('cell')
                certificate_request.village = request.POST.get('village')
                certificate_request.location_code = request.POST.get('location_code')
            
            certificate_request.save()
            messages.success(request, 'Your request has been submitted successfully!')
            return redirect('dashboard')
    else:
        form = CertificateRequestForm()

    # Get provinces for the location dropdown
    provinces = LocationImport.objects.filter(type='PROVINCE').values('location_id', 'name').order_by('location_id')
    
    return render(request, 'certificates/submit_request.html', {
        'form': form,
        'provinces': provinces
    })


@login_required
def dashboard(request):
    if request.user.is_superuser:
        requests = CertificateRequest.objects.all()
    else:
        requests = CertificateRequest.objects.filter(user=request.user)

    return render(request, 'certificates/dashboard.html', {
        'requests': requests,
        'is_admin': request.user.is_superuser
    })


@login_required
def request_detail(request, pk):
    if request.user.is_superuser:
        req = get_object_or_404(CertificateRequest, pk=pk)
    else:
        req = get_object_or_404(CertificateRequest, pk=pk, user=request.user)
    return render(request, 'certificates/request_detail.html', {'req': req})


@user_passes_test(lambda u: u.is_superuser)
def update_request_status(request, pk, action):
    req = get_object_or_404(CertificateRequest, pk=pk)
    if action == 'approve':
        req.status = 'approved'
        req.admin_message = 'Your request has been approved.'
    elif action == 'deny':
        req.status = 'denied'
        req.admin_message = 'Your request has been denied.'
    else:
        return HttpResponseBadRequest('Invalid action.')
    req.save()
    messages.success(request, f'Request has been {action}ed successfully.')
    return redirect('dashboard')


@user_passes_test(lambda u: u.is_superuser)
def manage_eligibility(request):
    users = CustomUser.objects.all()
    if request.method == 'POST':
        eligible_ids = request.POST.getlist('eligible')
        for user in users:
            user.is_eligible = str(user.id) in eligible_ids
            user.save()
        messages.success(request, 'Eligibility updated successfully!')
        return redirect('manage_eligibility')
    return render(request, 'certificates/manage_eligibility.html', {'users': users})


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('email')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            auth_login(request, user)
            messages.success(request, 'Login successful!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid email or password.')
    return render(request, 'certificates/login.html')


# ==================== AJAX LOCATION FILTERING VIEWS ====================

def get_provinces(request):
    """Get all provinces"""
    provinces = LocationImport.objects.filter(
        type='PROVINCE'
    ).values('location_id', 'name').order_by('location_id')
    
    return JsonResponse({'provinces': list(provinces)})


def get_districts(request):
    """Get districts based on selected province"""
    province_id = request.GET.get('province')
    
    if not province_id:
        return JsonResponse({'districts': []})
    
    province_id_str = str(province_id)
    
    districts = LocationImport.objects.filter(
        type='DISTRICT'
    ).extra(
        where=[
            "CAST(location_id AS TEXT) LIKE %s",
            "CHAR_LENGTH(CAST(location_id AS TEXT)) = 2"
        ],
        params=[f"{province_id_str}%"]
    ).values('location_id', 'name').order_by('location_id')
    
    return JsonResponse({'districts': list(districts)})


def get_sectors(request):
    """Get sectors based on selected district"""
    district_id = request.GET.get('district')
    
    if not district_id:
        return JsonResponse({'sectors': []})
    
    district_id_str = str(district_id)
    
    sectors = LocationImport.objects.filter(
        type='SECTOR'
    ).extra(
        where=[
            "CAST(location_id AS TEXT) LIKE %s",
            "CHAR_LENGTH(CAST(location_id AS TEXT)) = 4"
        ],
        params=[f"{district_id_str}%"]
    ).values('location_id', 'name').order_by('location_id')
    
    return JsonResponse({'sectors': list(sectors)})


def get_cells(request):
    """Get cells based on selected sector"""
    sector_id = request.GET.get('sector')
    
    if not sector_id:
        return JsonResponse({'cells': []})
    
    sector_id_str = str(sector_id)
    
    cells = LocationImport.objects.filter(
        type='CELL'
    ).extra(
        where=[
            "CAST(location_id AS TEXT) LIKE %s",
            "CHAR_LENGTH(CAST(location_id AS TEXT)) = 6"
        ],
        params=[f"{sector_id_str}%"]
    ).values('location_id', 'name').order_by('location_id')
    
    return JsonResponse({'cells': list(cells)})


def get_villages(request):
    """Get villages based on selected cell"""
    cell_id = request.GET.get('cell')
    
    if not cell_id:
        return JsonResponse({'villages': []})
    
    cell_id_str = str(cell_id)
    
    # If you don't have villages in your data, this will return empty
    villages = LocationImport.objects.filter(
        type='VILLAGE'
    ).extra(
        where=[
            "CAST(location_id AS TEXT) LIKE %s",
            "CHAR_LENGTH(CAST(location_id AS TEXT)) >= 7"
        ],
        params=[f"{cell_id_str}%"]
    ).values('location_id', 'name').order_by('location_id')
    
    return JsonResponse({'villages': list(villages)})


def get_location_code(request):
    """Get final location code based on selection"""
    village_id = request.GET.get('village')
    cell_id = request.GET.get('cell')
    sector_id = request.GET.get('sector')
    district_id = request.GET.get('district')
    province_id = request.GET.get('province')
    
    location_id = village_id or cell_id or sector_id or district_id or province_id
    
    if location_id:
        try:
            location = LocationImport.objects.get(location_id=location_id)
            return JsonResponse({
                'code': location.location_id,
                'name': location.name,
                'type': location.type,
                'success': True
            })
        except LocationImport.DoesNotExist:
            return JsonResponse({
                'code': None,
                'success': False,
                'error': 'Location not found'
            })
    
    return JsonResponse({
        'code': None,
        'success': False,
        'error': 'No location selected'
    })