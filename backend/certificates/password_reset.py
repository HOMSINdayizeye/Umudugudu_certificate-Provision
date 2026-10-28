"""Password reset by a code sent to the account's email (or phone), and the admin page that holds the Brevo key.

Flow: the user types their username, email or phone -> a 6-digit code is emailed (SMS when the account has no
email) with a link back to the app -> they send the code with a new password -> the password is replaced and
every existing login token is revoked.
"""
import os
import secrets
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.hashers import make_password, check_password
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from . import brevo
from .models import CustomUser, PasswordResetCode, SystemSetting
from .permissions import has_perm, is_full_admin
from .serializers import validate_strong_password, validate_phone_format


class PasswordResetThrottle(ScopedRateThrottle):
    scope = 'password_reset'


def find_user(identifier):
    value = (identifier or '').strip()
    if not value:
        return None
    phone = brevo.international(value) if value.replace('+', '').replace(' ', '').isdigit() else ''
    cond = Q(username__iexact=value) | Q(email__iexact=value)
    if phone:
        cond |= Q(phone=value) | Q(phone=phone) | Q(phone='0' + phone[3:])
    return CustomUser.objects.filter(cond).first()


def open_code_for(user):
    return next((c for c in user.password_reset_codes.filter(used_at__isnull=True)[:3] if c.is_open), None)


def frontend_url(request):
    """Where the reset link points: FRONTEND_URL, else the site the request came from."""
    return (os.getenv('FRONTEND_URL', '').strip() or request.META.get('HTTP_ORIGIN') or '').rstrip('/')


def reset_message(user, code, link):
    minutes = PasswordResetCode.LIFETIME_MINUTES
    name = user.first_name or user.username
    text = (f'Hello {name},\n\nYour Certify password reset code is: {code}\n\n'
            f'Open this link to enter it (or type it on the reset page): {link}\n\n'
            f'The code expires in {minutes} minutes. If you did not ask to reset your password, ignore this message; '
            f'your password stays unchanged.')
    html = (f'<div style="font-family:Arial,sans-serif;max-width:520px;color:#222">'
            f'<h2 style="color:#056daa;margin:0 0 12px">Certify password reset</h2>'
            f'<p>Hello {name},</p><p>Your password reset code is:</p>'
            f'<p style="font-size:32px;font-weight:bold;letter-spacing:6px;margin:8px 0 16px">{code}</p>'
            f'<p><a href="{link}" style="background:#056daa;color:#fff;padding:10px 18px;text-decoration:none;'
            f'display:inline-block">Set a new password</a></p>'
            f'<p style="color:#666;font-size:13px">The code expires in {minutes} minutes. If you did not ask to reset '
            f'your password, ignore this email; your password stays unchanged.</p></div>')
    sms = (f'Your Certify password reset code is {code}. It expires in {minutes} minutes. '
           f'Ignore this message if you did not ask for it.')
    return text, html, sms


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PasswordResetThrottle])
def request_code(request):
    """Body: {identifier, channel?: 'email'|'sms'}. Sends a reset code to the account's email (default) or phone."""
    user = find_user(request.data.get('identifier'))
    if not user:
        return Response({'detail': 'No account uses this username, email or phone number.'},
                        status=status.HTTP_404_NOT_FOUND)
    if not user.is_active:
        return Response({'detail': 'This account is deactivated. Ask the system admin.'}, status=status.HTTP_403_FORBIDDEN)

    channel = request.data.get('channel') or ('email' if user.email else 'sms')
    if channel == 'email' and not user.email:
        channel = 'sms'
    if channel == 'sms' and not user.phone:
        channel = 'email' if user.email else None
    if channel is None:
        return Response({'detail': 'This account has neither an email address nor a phone number, so no code can be '
                                   'sent. Ask the system admin to add one or reset the password for you.'},
                        status=status.HTTP_400_BAD_REQUEST)

    recent = open_code_for(user)
    if recent:
        age = (timezone.now() - recent.created_at).total_seconds()
        if age < PasswordResetCode.RESEND_SECONDS:
            wait = int(PasswordResetCode.RESEND_SECONDS - age)
            return Response({'detail': f'A code was sent {int(age)} seconds ago. Wait {wait} s before asking for another.',
                             'retry_in': wait}, status=status.HTTP_429_TOO_MANY_REQUESTS)

    code = f'{secrets.randbelow(1_000_000):06d}'
    user.password_reset_codes.filter(used_at__isnull=True).update(used_at=timezone.now())   # one open code at a time
    entry = PasswordResetCode.objects.create(
        user=user, sent_to=user.phone if channel == 'sms' else user.email, code_hash=make_password(code),
        expires_at=timezone.now() + timedelta(minutes=PasswordResetCode.LIFETIME_MINUTES))
    link = f'{frontend_url(request)}/reset-password?' + urlencode({'identifier': user.username, 'code': code})
    text, html, sms_text = reset_message(user, code, link)

    body = {'channel': channel, 'sent_to': brevo.mask_email(user.email) if channel == 'email' else brevo.mask_phone(user.phone),
            'expires_in': PasswordResetCode.LIFETIME_MINUTES * 60, 'resend_in': PasswordResetCode.RESEND_SECONDS,
            'can_use_email': bool(user.email), 'can_use_sms': bool(user.phone)}
    try:
        if channel == 'email':
            brevo.send_email(user.email, 'Your Certify password reset code', text, html, to_name=user.display_name,
                             tag='password-reset')
        else:
            brevo.send_sms(user.phone, sms_text, tag='password-reset')
    except brevo.BrevoError as err:
        if settings.DEBUG and not brevo.config()['enabled']:
            # Developer convenience only: no Brevo key yet, so the code is handed back (never when DEBUG is off)
            body.update(detail=f'Brevo is not configured, so the code is shown here (DEBUG mode only): {code}',
                        debug_code=code)
            return Response(body)
        entry.delete()
        return Response({'detail': str(err)}, status=status.HTTP_502_BAD_GATEWAY)
    body['detail'] = (f"We emailed a 6-digit code to {body['sent_to']}." if channel == 'email'
                      else f"We sent a 6-digit code by SMS to {body['sent_to']}.")
    return Response(body)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PasswordResetThrottle])
def confirm_code(request):
    """Body: {identifier, code, new_password}. Sets the new password when the code is right."""
    user = find_user(request.data.get('identifier'))
    entry = open_code_for(user) if user else None
    if not entry:
        return Response({'detail': 'No valid code is open for this account. Ask for a new code.'},
                        status=status.HTTP_400_BAD_REQUEST)
    code = str(request.data.get('code') or '').strip()
    entry.attempts += 1
    entry.save(update_fields=['attempts'])
    if not check_password(code, entry.code_hash):
        left = PasswordResetCode.MAX_ATTEMPTS - entry.attempts
        if left <= 0:
            return Response({'detail': 'Wrong code. That was the last try; ask for a new code.'}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': f'Wrong code. {left} tr{"y" if left == 1 else "ies"} left.'}, status=status.HTTP_400_BAD_REQUEST)

    new_password = request.data.get('new_password') or ''
    try:
        validate_strong_password(new_password)
    except Exception as err:   # serializers.ValidationError
        detail = getattr(err, 'detail', None) or str(err)
        return Response({'new_password': detail}, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(new_password)
    user.save(update_fields=['password'])
    entry.used_at = timezone.now()
    entry.save(update_fields=['used_at'])
    Token.objects.filter(user=user).delete()   # every device must log in again with the new password
    return Response({'detail': 'Your password has been changed. You can now log in with it.'})


# ---------- Admin: Brevo messaging settings ----------

def can_manage_messaging(user):
    return is_full_admin(user) or has_perm(user, 'settings:sms')


def messaging_status():
    cfg = brevo.config()
    cfg.pop('_key', None)
    return cfg


@api_view(['GET', 'PUT', 'DELETE'])
def messaging_settings(request):
    """GET the status (never the key); PUT {api_key?, email_sender?, email_sender_name?, sms_sender?};
    DELETE removes everything stored in the app (environment variables are untouched)."""
    if not can_manage_messaging(request.user):
        return Response({'detail': 'You are not allowed to manage messaging settings.'}, status=status.HTTP_403_FORBIDDEN)
    if request.method == 'DELETE':
        SystemSetting.objects.filter(key='brevo').delete()
        return Response({'detail': 'Stored Brevo settings removed.', **messaging_status()})
    if request.method == 'PUT':
        row = SystemSetting.objects.filter(key='brevo').first()
        value = dict(row.value or {}) if row else {}
        api_key = (request.data.get('api_key') or '').strip()
        email_sender = (request.data.get('email_sender') or '').strip()
        email_sender_name = (request.data.get('email_sender_name') or '').strip()
        sms_sender = (request.data.get('sms_sender') or '').strip()
        if api_key:
            if len(api_key) < 20 or ' ' in api_key:
                return Response({'api_key': 'That does not look like a Brevo API key (it starts with "xkeysib-").'},
                                status=status.HTTP_400_BAD_REQUEST)
            value['api_key'] = api_key
        if email_sender:
            if '@' not in email_sender or ' ' in email_sender:
                return Response({'email_sender': 'Enter the sender email address exactly as verified in Brevo.'},
                                status=status.HTTP_400_BAD_REQUEST)
            value['email_sender'] = email_sender.lower()
        if email_sender_name:
            value['email_sender_name'] = email_sender_name[:60]
        if sms_sender:
            if not sms_sender.isalnum() or len(sms_sender) > 11:
                return Response({'sms_sender': 'SMS sender: 1 to 11 letters or digits, no spaces (e.g. Certify).'},
                                status=status.HTTP_400_BAD_REQUEST)
            value['sms_sender'] = sms_sender
        if not value.get('api_key') and not os.getenv('BREVO_API_KEY', '').strip():
            return Response({'api_key': 'Paste the Brevo API key.'}, status=status.HTTP_400_BAD_REQUEST)
        SystemSetting.objects.update_or_create(key='brevo', defaults={'value': value, 'updated_by': request.user})
        return Response({'detail': 'Messaging settings saved.', **messaging_status()})
    return Response(messaging_status())


@api_view(['POST'])
def messaging_test(request):
    """Body: {channel: 'email'|'sms', to?}. Sends a test message so the admin can confirm the setup works."""
    if not can_manage_messaging(request.user):
        return Response({'detail': 'You are not allowed to manage messaging settings.'}, status=status.HTTP_403_FORBIDDEN)
    channel = request.data.get('channel') or 'email'
    to = (request.data.get('to') or '').strip()
    try:
        if channel == 'sms':
            phone = validate_phone_format(to or request.user.phone)
            if not phone:
                return Response({'to': 'Enter the phone number to send the test SMS to.'}, status=status.HTTP_400_BAD_REQUEST)
            result = brevo.send_sms(phone, 'Certify test SMS: your Brevo setup works.', tag='test')
            where = brevo.mask_phone(phone)
        else:
            email = to or request.user.email
            if '@' not in email:
                return Response({'to': 'Enter the email address to send the test to.'}, status=status.HTTP_400_BAD_REQUEST)
            result = brevo.send_email(email, 'Certify test email',
                                      'This is a test email from Certify. Your Brevo setup works.',
                                      '<p>This is a test email from <strong>Certify</strong>. Your Brevo setup works.</p>',
                                      tag='test')
            where = brevo.mask_email(email)
    except Exception as err:
        if isinstance(err, brevo.BrevoError):
            return Response({'detail': str(err)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({'to': getattr(err, 'detail', str(err))}, status=status.HTTP_400_BAD_REQUEST)
    return Response({'detail': f'Test {channel} sent to {where} (Brevo message {result.get("messageId", "?")}).'})


# Older names kept for the URL file
sms_settings = messaging_settings
sms_test = messaging_test
