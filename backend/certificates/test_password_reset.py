"""Password reset by emailed/texted code and the Brevo messaging settings endpoints (sending is mocked)."""
import json
import re
from unittest import mock

from django.test import TestCase, override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from .models import CustomUser, PasswordResetCode, SystemSetting
from . import brevo


def capture(sent):
    def fake_email(to_email, subject, text, html=None, to_name='', tag='certify'):
        sent.append(('email', to_email, text, tag, html))
        return {'messageId': '<1@brevo>'}

    def fake_sms(phone, content, tag='certify'):
        sent.append(('sms', phone, content, tag, None))
        return {'messageId': 123}
    return fake_email, fake_sms


@override_settings(DEBUG=False)
class PasswordResetTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(username='amina', email='amina@example.test', password='OldPass1!',
                                                   phone='0791234567', first_name='Amina', last_name='U')
        self.client = APIClient()
        self.sent = []

    def request(self, identifier, channel=None, origin='http://localhost:5173'):
        fake_email, fake_sms = capture(self.sent)
        body = {'identifier': identifier, **({'channel': channel} if channel else {})}
        with mock.patch.object(brevo, 'send_email', fake_email), mock.patch.object(brevo, 'send_sms', fake_sms):
            return self.client.post('/api/auth/password-reset/request/', body, format='json', HTTP_ORIGIN=origin)

    def code_from_message(self):
        return re.search(r'code is:? (\d{6})', self.sent[-1][2]).group(1)

    def test_code_is_emailed_with_a_link_and_sets_a_new_password(self):
        res = self.request('amina')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual((res.data['channel'], res.data['sent_to']), ('email', 'am***@example.test'))
        kind, to, text, tag, html = self.sent[-1]
        self.assertEqual((kind, to, tag), ('email', 'amina@example.test', 'password-reset'))
        code = self.code_from_message()
        self.assertIn(f'http://localhost:5173/reset-password?identifier=amina&code={code}', text)
        self.assertIn(code, html)
        self.assertNotIn('debug_code', res.data)      # never leaks the code when DEBUG is off
        self.assertNotEqual(PasswordResetCode.objects.get().code_hash, code)   # stored hashed

        Token.objects.create(user=self.user)
        res = self.client.post('/api/auth/password-reset/confirm/',
                               {'identifier': 'amina', 'code': code, 'new_password': 'NewPass1!'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewPass1!'))
        self.assertFalse(Token.objects.filter(user=self.user).exists())   # other devices signed out
        self.assertFalse(PasswordResetCode.objects.get().is_open)        # code cannot be reused

    def test_long_email_addresses_fit_the_reset_record(self):
        self.user.email = 'amina.uwimana.longaddress@kigalicity.example.test'   # longer than a phone number
        self.user.save()
        res = self.request('amina')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(PasswordResetCode.objects.get().sent_to, self.user.email)

    @mock.patch.dict('os.environ', {'FRONTEND_URL': 'https://certify.example.rw/'})
    def test_frontend_url_env_wins_for_the_link(self):
        self.request('amina')
        self.assertIn('https://certify.example.rw/reset-password?identifier=amina', self.sent[-1][2])

    def test_sms_when_asked_or_when_the_account_has_no_email(self):
        res = self.request('250791234567', channel='sms')
        self.assertEqual((res.status_code, res.data['channel'], res.data['sent_to']), (200, 'sms', '25079*****67'))
        self.assertEqual(self.sent[-1][:2], ('sms', '0791234567'))
        self.user.email = ''
        self.user.save()
        PasswordResetCode.objects.all().delete()
        res = self.request('amina')
        self.assertEqual((res.status_code, res.data['channel']), (200, 'sms'))
        self.user.phone = ''
        self.user.save()
        PasswordResetCode.objects.all().delete()
        self.assertEqual(self.request('amina').status_code, 400)

    def test_wrong_code_counts_attempts_and_weak_password_is_refused(self):
        self.request('amina')
        code = self.code_from_message()
        for i in range(4):
            res = self.client.post('/api/auth/password-reset/confirm/',
                                   {'identifier': 'amina', 'code': '000000', 'new_password': 'NewPass1!'}, format='json')
            self.assertEqual(res.status_code, 400)
        self.assertIn('1 try left', res.data['detail'])
        res = self.client.post('/api/auth/password-reset/confirm/',
                               {'identifier': 'amina', 'code': code, 'new_password': 'weak'}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('new_password', res.data)
        # That was the fifth attempt: the code is now closed even though it was right
        res = self.client.post('/api/auth/password-reset/confirm/',
                               {'identifier': 'amina', 'code': code, 'new_password': 'NewPass1!'}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('Ask for a new code', res.data['detail'])

    def test_unknown_account_and_resend_wait(self):
        self.assertEqual(self.request('nobody').status_code, 404)
        self.assertEqual(self.request('amina').status_code, 200)
        res = self.request('amina')
        self.assertEqual(res.status_code, 429)
        self.assertIn('retry_in', res.data)

    def test_brevo_failure_reports_the_reason_and_keeps_no_code(self):
        def failing(*args, **kwargs):
            raise brevo.BrevoError('Brevo rejected the API key (HTTP 401).')
        with mock.patch.object(brevo, 'send_email', failing):
            res = self.client.post('/api/auth/password-reset/request/', {'identifier': 'amina'}, format='json')
        self.assertEqual(res.status_code, 502)
        self.assertIn('Brevo rejected', res.data['detail'])
        self.assertFalse(PasswordResetCode.objects.exists())


ENV_EMPTY = {'BREVO_API_KEY': '', 'BREVO_EMAIL_SENDER': '', 'BREVO_EMAIL_SENDER_NAME': '', 'BREVO_SMS_SENDER': ''}


class MessagingSettingsTests(TestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_superuser(username='admin', password='x', phone='0788000000',
                                                         email='admin@example.test')
        self.leader = CustomUser.objects.create_user(username='vl', password='x', role='village_leader')

    def client_for(self, user):
        c = APIClient()
        c.force_authenticate(user)
        return c

    @mock.patch.dict('os.environ', ENV_EMPTY)
    def test_admin_stores_key_and_senders_and_status_never_returns_the_key(self):
        c = self.client_for(self.admin)
        res = c.get('/api/settings/messaging/')
        self.assertEqual((res.status_code, res.data['enabled'], res.data['email_ready']), (200, False, False))
        self.assertEqual(c.put('/api/settings/messaging/', {'api_key': 'short'}, format='json').status_code, 400)
        res = c.put('/api/settings/messaging/', {'api_key': 'xkeysib-0123456789abcdef0123456789abcdef',
                                                 'email_sender': 'No-Reply@KigaliCity.gov.rw', 'email_sender_name': 'Kigali City',
                                                 'sms_sender': 'KigaliCity'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual((res.data['enabled'], res.data['email_ready'], res.data['source'], res.data['key_hint'],
                          res.data['email_sender'], res.data['email_sender_name'], res.data['sms_sender']),
                         (True, True, 'database', '…cdef', 'no-reply@kigalicity.gov.rw', 'Kigali City', 'KigaliCity'))
        self.assertNotIn('xkeysib', str(res.data))
        # Saving only a new sender keeps the key
        res = c.put('/api/settings/messaging/', {'email_sender_name': 'Certify'}, format='json')
        self.assertEqual((res.status_code, res.data['enabled'], res.data['email_sender_name']), (200, True, 'Certify'))
        self.assertEqual(c.put('/api/settings/messaging/', {'sms_sender': 'bad name!'}, format='json').status_code, 400)
        self.assertEqual(c.delete('/api/settings/messaging/').data['enabled'], False)
        self.assertFalse(SystemSetting.objects.filter(key='brevo').exists())

    def test_only_allowed_users_manage_messaging(self):
        c = self.client_for(self.leader)
        self.assertEqual(c.get('/api/settings/messaging/').status_code, 403)
        self.assertEqual(c.post('/api/settings/messaging/test/', {'channel': 'email'}, format='json').status_code, 403)

    @mock.patch.dict('os.environ', {**ENV_EMPTY, 'BREVO_API_KEY': 'xkeysib-env-key-0000000000000000',
                                    'BREVO_EMAIL_SENDER': 'no-reply@example.test'})
    def test_env_values_win_and_tests_use_them(self):
        c = self.client_for(self.admin)
        res = c.get('/api/settings/messaging/')
        self.assertEqual((res.data['enabled'], res.data['source'], res.data['email_ready'], res.data['email_sender']),
                         (True, 'env', True, 'no-reply@example.test'))
        self.assertEqual(sorted(res.data['env_overrides']), ['BREVO_API_KEY', 'BREVO_EMAIL_SENDER'])
        sent = []
        fake_email, fake_sms = capture(sent)
        with mock.patch.object(brevo, 'send_email', fake_email), mock.patch.object(brevo, 'send_sms', fake_sms):
            self.assertEqual(c.post('/api/settings/messaging/test/', {'channel': 'email'}, format='json').status_code, 200)
            self.assertEqual(c.post('/api/settings/messaging/test/', {'channel': 'sms', 'to': '0791234567'},
                                    format='json').status_code, 200)
            self.assertEqual(c.post('/api/settings/messaging/test/', {'channel': 'sms', 'to': '12345'},
                                    format='json').status_code, 400)
        self.assertEqual([(s[0], s[1]) for s in sent], [('email', 'admin@example.test'), ('sms', '0791234567')])


class BrevoClientTests(TestCase):
    def test_phone_and_email_masks(self):
        self.assertEqual(brevo.international('0791234567'), '250791234567')
        self.assertEqual(brevo.international('+250 791 234 567'), '250791234567')
        self.assertEqual(brevo.mask_phone('0791234567'), '25079*****67')
        self.assertEqual(brevo.mask_email('amina@example.test'), 'am***@example.test')

    @mock.patch.dict('os.environ', ENV_EMPTY)
    def test_sending_without_a_key_or_sender_is_refused_clearly(self):
        with self.assertRaises(brevo.BrevoError) as ctx:
            brevo.send_email('a@b.c', 's', 't')
        self.assertIn('not configured', str(ctx.exception))
        SystemSetting.objects.create(key='brevo', value={'api_key': 'xkeysib-0123456789abcdef0123456789'})
        with self.assertRaises(brevo.BrevoError) as ctx:
            brevo.send_email('a@b.c', 's', 't')
        self.assertIn('sender email', str(ctx.exception))

    @mock.patch.dict('os.environ', {**ENV_EMPTY, 'BREVO_API_KEY': 'xkeysib-test', 'BREVO_EMAIL_SENDER': 'no-reply@x.rw',
                                    'BREVO_EMAIL_SENDER_NAME': 'Certify'})
    def test_email_request_is_built_for_brevo(self):
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return b'{"messageId": "<42@brevo>"}'

        def fake_urlopen(req, timeout=0):
            captured['url'] = req.full_url
            captured['headers'] = {k.lower(): v for k, v in req.header_items()}
            captured['body'] = json.loads(req.data)
            return FakeResponse()

        with mock.patch('urllib.request.urlopen', fake_urlopen):
            result = brevo.send_email('amina@example.test', 'Subject', 'Text body', '<p>html</p>', to_name='Amina', tag='password-reset')
        self.assertEqual(result['messageId'], '<42@brevo>')
        self.assertEqual(captured['url'], brevo.BREVO_EMAIL_URL)
        self.assertEqual(captured['headers']['api-key'], 'xkeysib-test')
        body = captured['body']
        self.assertEqual(body['sender'], {'email': 'no-reply@x.rw', 'name': 'Certify'})
        self.assertEqual(body['to'], [{'email': 'amina@example.test', 'name': 'Amina'}])
        self.assertEqual((body['subject'], body['textContent'], body['htmlContent'], body['tags']),
                         ('Subject', 'Text body', '<p>html</p>', ['password-reset']))
