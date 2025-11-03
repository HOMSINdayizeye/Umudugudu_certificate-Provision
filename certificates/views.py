
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, login as auth_login
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from .forms import SignUpForm, CertificateRequestForm
from .models import EligiblePerson, CertificateRequest
from django.contrib.auth import logout
from django.conf import settings
from .models import CustomUser
from django.http import HttpResponseForbidden


from django.http import HttpResponseBadRequest
from .forms import SignUpForm  # or wherever your custom form is defined


def index(request):
    return render(request, 'certificates/index.html')

# def register(request):
#     if request.method == 'POST':
#         form = SignUpForm(request.POST)
#         if form.is_valid():
#             user = form.save(commit=False)
#             user.email = form.cleaned_data.get('email')
#             user.save()
#             login(request, user)
#             messages.success(request, 'Account created. Now choose the certificate you want.')
#             return redirect('choose_certificate')
#     else:
#         form = SignUpForm()
#     return render(request, 'certificates/register.html', {'form': form})

def register(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.email = form.cleaned_data['email']
            user.first_name = form.cleaned_data['first_name']
            user.last_name = form.cleaned_data['last_name']
            user.save()
            return redirect('login')  # or wherever you want to redirect
    else:
        form = SignUpForm()
    
    return render(request, 'certificates/register.html', {'form': form})    


@login_required
def choose_certificate(request):
    # simple page to let user pick
    return render(request, 'certificates/choose_certificate.html')

@login_required
# def submit_request(request):
#     if request.method == 'POST':
#         form = CertificateRequestForm(request.POST)
#         if form.is_valid():
#             try:
#                 #EligiblePerson.objects.get(email__iexact=request.user.email)
#                 cert_req = form.save(commit=False)
#                 cert_req.user = request.user
#                 cert_req.eligible = True
#                 cert_req.email = request.user.email
#                 cert_req.save()
#                 messages.success(request, 'Your request is submitted and you are eligible. Waiting for approval.')
#                 return redirect('dashboard')
#             except EligiblePerson.DoesNotExist:
#                 messages.error(request, 'You are not eligible to submit a certificate request.')
#                 return redirect('dashboard')
#         return render(request, 'certificates/submit_request.html')
def submit_request(request):
    if request.user.is_superuser:
        return HttpResponseForbidden("Superusers cannot submit certificate requests.")

    if request.method == 'POST':
        form = CertificateRequestForm(request.POST)
        if form.is_valid():
            certificate_request = form.save(commit=False)
            certificate_request.user = request.user
            certificate_request.save()
            return redirect('dashboard')
    else:
        form = CertificateRequestForm()

    return render(request, 'certificates/submit_request.html', {'form': form})

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
       req.action = 'denied'
       req.admin_message = 'Your request has been denied.'
    else:
        return HttpResponseBadRequest('Invalid action.')
    req.save()
    return redirect('dashboard')
 # managing Eligibility
def manage_eligibility(request):
    users = CustomUser.objects.all()
    if request.method == 'POST':
        eligible_ids = request.POST.getlist('eligible')
        for user in users:
            user.profile.is_eligible = str(user.id) in eligible_ids
            user.profile.save()
        return redirect('manage_eligibility')
    return render(request, 'certificates/manage_eligibility.html', {'users': users})
#tracking Eligibility person

def login(request):
    if request.method == 'POST':
        username = request.POST['email']
        password = request.POST['password']
        user = authenticate(request, username =username,password= password)
        if user is not None:
            auth_login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid username or password.')