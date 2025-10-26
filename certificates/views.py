
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from .forms import SignUpForm, CertificateRequestForm
from .models import EligiblePerson, CertificateRequest


def index(request):
    return render(request, 'certificates/index.html')

def register(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.email = form.cleaned_data.get('email')
            user.save()
            login(request, user)
            messages.success(request, 'Account created. Now choose the certificate you want.')
            return redirect('choose_certificate')
    else:
        form = SignUpForm()
    return render(request, 'certificates/register.html', {'form': form})

@login_required
def choose_certificate(request):
    # simple page to let user pick
    return render(request, 'certificates/choose_certificate.html')

@login_required
def submit_request(request):
    if request.method == 'POST':
        form = CertificateRequestForm(request.POST)
        if form.is_valid():
            cert_req = form.save(commit=False)
            cert_req.user = request.user
            # check eligibility - by email match
            try:
                EligiblePerson.objects.get(email__iexact=request.user.email)
                cert_req.eligible = True
            except EligiblePerson.DoesNotExist:
                cert_req.eligible = False
                cert_req.admin_message = 'User not found in eligibility list.'

            cert_req.save()

            # notify admin: we will create a message in admin site view; also add django messages
            if cert_req.eligible:
                messages.success(request, 'Your request is submitted and you are eligible. Waiting for approval.')
            else:
                messages.warning(request, 'Your request is submitted but you are NOT on the eligibility list. Admins will review.')

            return redirect('dashboard')
    else:
        form = CertificateRequestForm()
    return render(request, 'certificates/submit_request.html', {'form': form})

@login_required
def dashboard(request):
    requests = request.user.requests.order_by('-created_at')
    return render(request, 'certificates/dashboard.html', {'requests': requests})

@login_required
def request_detail(request, pk):
    req = get_object_or_404(CertificateRequest, pk=pk, user=request.user)
    return render(request, 'certificates/request_detail.html', {'req': req})