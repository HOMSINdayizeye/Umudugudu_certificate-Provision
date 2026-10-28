"""Email and SMS sending through Brevo (formerly Sendinblue): transactional email and transactional SMS.

One API key serves both. It comes from the BREVO_API_KEY environment variable (backend/.env, Render/Vercel
settings) or, when that is not set, from the key a system admin pasted on the Messaging settings page
(SystemSetting 'brevo'). Likewise for the senders:
    BREVO_EMAIL_SENDER       address the emails come from (must be a verified sender in Brevo)
    BREVO_EMAIL_SENDER_NAME  name shown next to it (default "Certify")
    BREVO_SMS_SENDER         SMS sender, up to 11 letters/digits (default "Certify")
"""
import json
import logging
import os
import urllib.error
import urllib.request

from .models import SystemSetting

BREVO_SMS_URL = 'https://api.brevo.com/v3/transactionalSMS/sms'
BREVO_EMAIL_URL = 'https://api.brevo.com/v3/smtp/email'
DEFAULT_SENDER_NAME = 'Certify'
log = logging.getLogger('certify.brevo')


class BrevoError(Exception):
    """The message could not be sent; the text is safe to show to the user."""


SmsError = BrevoError   # older name


def international(phone):
    """Rwandan number in the international form Brevo expects: 0791234567 -> 250791234567."""
    digits = ''.join(ch for ch in (phone or '') if ch.isdigit())
    if digits.startswith('0') and len(digits) == 10:
        return '250' + digits[1:]
    return digits


def mask_phone(phone):
    digits = international(phone)
    if len(digits) < 6:
        return '***'
    return digits[:5] + '*' * (len(digits) - 7) + digits[-2:]


def mask_email(email):
    email = (email or '').strip()
    if '@' not in email:
        return '***'
    name, domain = email.split('@', 1)
    shown = name[:2] if len(name) > 3 else name[:1]
    return f'{shown}{"*" * max(2, len(name) - len(shown))}@{domain}'


def config():
    """Keys and senders in use, and where they come from (the API key itself is never returned to clients)."""
    row = SystemSetting.objects.filter(key='brevo').first()
    stored = (row.value or {}) if row else {}
    env = {k: os.getenv(k, '').strip() for k in
           ('BREVO_API_KEY', 'BREVO_EMAIL_SENDER', 'BREVO_EMAIL_SENDER_NAME', 'BREVO_SMS_SENDER')}
    key = env['BREVO_API_KEY'] or stored.get('api_key', '')
    email_sender = env['BREVO_EMAIL_SENDER'] or stored.get('email_sender', '')
    return {
        'enabled': bool(key),
        'source': 'env' if env['BREVO_API_KEY'] else ('database' if stored.get('api_key') else ''),
        'key_hint': f'…{key[-4:]}' if key else '',
        'email_sender': email_sender,
        'email_sender_name': env['BREVO_EMAIL_SENDER_NAME'] or stored.get('email_sender_name') or DEFAULT_SENDER_NAME,
        'email_ready': bool(key and email_sender),
        'sms_sender': (env['BREVO_SMS_SENDER'] or stored.get('sms_sender') or DEFAULT_SENDER_NAME)[:11],
        'sms_ready': bool(key),
        'env_overrides': [k for k, v in env.items() if v],
        'updated_at': row.updated_at if row else None,
        'updated_by': row.updated_by.display_name if row and row.updated_by else '',
        '_key': key,
    }


def _post(url, api_key, body, what):
    req = urllib.request.Request(
        url, data=json.dumps(body).encode('utf-8'), method='POST',
        headers={'api-key': api_key, 'content-type': 'application/json', 'accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read() or b'{}')
    except urllib.error.HTTPError as err:
        raw = err.read().decode('utf-8', errors='replace')
        try:
            message = json.loads(raw).get('message') or raw
        except ValueError:
            message = raw
        log.error('Brevo refused %s: HTTP %s %s', what, err.code, message)
        if err.code == 401:
            raise BrevoError('Brevo rejected the API key (HTTP 401). Check the key on the Messaging settings page.')
        raise BrevoError(f'Brevo could not send the {what} (HTTP {err.code}): {message[:200]}')
    except urllib.error.URLError as err:
        log.error('Brevo unreachable: %s', err.reason)
        raise BrevoError(f'Could not reach Brevo: {err.reason}')


def send_email(to_email, subject, text, html=None, to_name='', tag='certify'):
    """Send one transactional email; returns Brevo's response (messageId) or raises BrevoError."""
    cfg = config()
    if not cfg['enabled']:
        raise BrevoError('Email sending is not configured. A system admin must enter the Brevo API key on the '
                         'Messaging settings page (or set BREVO_API_KEY in the server environment).')
    if not cfg['email_sender']:
        raise BrevoError('No sender email address is set. Enter a verified Brevo sender on the Messaging settings '
                         'page (or set BREVO_EMAIL_SENDER).')
    to_email = (to_email or '').strip()
    if '@' not in to_email:
        raise BrevoError('The account has no valid email address to send to.')
    body = {
        'sender': {'email': cfg['email_sender'], 'name': cfg['email_sender_name']},
        'to': [{'email': to_email, **({'name': to_name} if to_name else {})}],
        'subject': subject, 'textContent': text, 'htmlContent': html or f'<pre>{text}</pre>', 'tags': [tag],
    }
    data = _post(BREVO_EMAIL_URL, cfg['_key'], body, 'email')
    log.info('Email sent to %s (Brevo message %s)', mask_email(to_email), data.get('messageId'))
    return data


def send_sms(phone, content, tag='certify'):
    """Send one transactional SMS; returns Brevo's response (messageId) or raises BrevoError."""
    cfg = config()
    if not cfg['enabled']:
        raise BrevoError('SMS sending is not configured. A system admin must enter the Brevo API key on the '
                         'Messaging settings page (or set BREVO_API_KEY in the server environment).')
    recipient = international(phone)
    if len(recipient) < 10:
        raise BrevoError('The account has no valid phone number to send the SMS to.')
    body = {'type': 'transactional', 'sender': cfg['sms_sender'], 'recipient': recipient, 'content': content, 'tag': tag}
    data = _post(BREVO_SMS_URL, cfg['_key'], body, 'SMS')
    log.info('SMS sent to %s (Brevo message %s)', mask_phone(phone), data.get('messageId'))
    return data
