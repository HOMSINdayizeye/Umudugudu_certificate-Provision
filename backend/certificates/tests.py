import datetime
import io
import os
import shutil
import tempfile

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from .models import (
    Citizen, CitizenTransfer, CustomUser, LocationImport, Notification, CertificateRequest, RequestAttachment,
    Announcement, ServicePayment, DeathReport, Activity, Attendance,
)

# Two villages in different cells of the same sector: sector 1001 -> cells 100101/100102 -> villages ...01
FROM_VILLAGE = 10010101
TO_VILLAGE = 10010201


def make_locations():
    LocationImport.objects.create(location_id=1001, type='SECTOR', name='Sector A', status='active')
    LocationImport.objects.create(location_id=100101, type='CELL', name='Cell A', status='active')
    LocationImport.objects.create(location_id=100102, type='CELL', name='Cell B', status='active')
    LocationImport.objects.create(location_id=FROM_VILLAGE, type='VILLAGE', name='Kigarama', status='active')
    LocationImport.objects.create(location_id=TO_VILLAGE, type='VILLAGE', name='Rugando', status='active')


def leader(username, village):
    return CustomUser.objects.create_user(username=username, password='x', role='village_leader', village=village,
                                          first_name=username, last_name='Leader')


class CitizenTransferFlowTests(TestCase):
    def setUp(self):
        make_locations()
        self.sender = leader('sender', FROM_VILLAGE)
        self.receiver = leader('receiver', TO_VILLAGE)
        self.citizen = Citizen.objects.create(first_name='Alice', last_name='Uwase', national_id='1199000000000001',
                                              age=30, village=FROM_VILLAGE, isibo='Amahoro', added_by=self.sender)

    def as_user(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def send_transfer(self):
        res = self.as_user(self.sender).post(f'/api/citizens/{self.citizen.id}/transfer/',
                                             {'village': TO_VILLAGE, 'note': 'Moved for work'}, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        return CitizenTransfer.objects.get(pk=res.data['id'])

    def test_transfer_request_keeps_citizen_in_source_village_and_notifies_receiver(self):
        transfer = self.send_transfer()
        self.citizen.refresh_from_db()
        self.assertEqual(transfer.status, 'pending')
        self.assertEqual(self.citizen.village, FROM_VILLAGE)
        self.assertEqual(self.citizen.isibo, 'Amahoro')
        self.assertIsNone(self.citizen.transferred_from_village)
        notice = Notification.objects.get(user=self.receiver)
        self.assertIn('awaiting your confirmation', notice.title)
        self.assertEqual(notice.link, '/transfers')

        # The sender still sees the citizen, flagged as pending
        res = self.as_user(self.sender).get('/api/citizens/')
        row = next(c for c in res.data['citizens'] if c['id'] == self.citizen.id)
        self.assertEqual(row['pending_transfer']['to_village'], TO_VILLAGE)

        # The receiver sees the request under pending_in, not among incoming citizens
        res = self.as_user(self.receiver).get('/api/citizens/transfers/')
        self.assertEqual([t['id'] for t in res.data['pending_in']], [transfer.id])
        self.assertEqual(res.data['incoming'], [])

    def test_second_pending_transfer_is_refused(self):
        self.send_transfer()
        res = self.as_user(self.sender).post(f'/api/citizens/{self.citizen.id}/transfer/',
                                             {'village': TO_VILLAGE}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('already waiting', res.data['detail'])

    def test_accept_moves_citizen_and_keeps_origin(self):
        transfer = self.send_transfer()
        res = self.as_user(self.receiver).post(f'/api/citizens/transfers/{transfer.id}/accept/',
                                               {'isibo': 'Ubumwe'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['status'], 'placed')

        self.citizen.refresh_from_db()
        transfer.refresh_from_db()
        self.assertEqual(transfer.status, 'accepted')
        self.assertEqual(transfer.decided_by, self.receiver)
        self.assertEqual(self.citizen.village, TO_VILLAGE)
        self.assertEqual(self.citizen.isibo, 'Ubumwe')
        self.assertEqual(self.citizen.transferred_from_village, FROM_VILLAGE)
        self.assertEqual(self.citizen.transferred_from_isibo, 'Amahoro')
        self.assertIsNotNone(self.citizen.transfer_placed_at)
        self.assertTrue(Notification.objects.filter(user=self.sender, title='Citizen transfer accepted').exists())

        # Origin is visible on the record in the new village
        res = self.as_user(self.receiver).get(f'/api/citizens/{self.citizen.id}/')
        self.assertEqual(res.data['transferred_from_village'], FROM_VILLAGE)
        self.assertIn('Kigarama', res.data['transferred_from_village_name'])
        # And the sender no longer sees them in their citizen list
        res = self.as_user(self.sender).get('/api/citizens/')
        self.assertNotIn(self.citizen.id, [c['id'] for c in res.data['citizens']])

    def test_accept_without_isibo_leaves_citizen_awaiting_placement(self):
        transfer = self.send_transfer()
        res = self.as_user(self.receiver).post(f'/api/citizens/transfers/{transfer.id}/accept/', {}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['status'], 'awaiting_isibo')
        self.citizen.refresh_from_db()
        self.assertEqual(self.citizen.village, TO_VILLAGE)
        self.assertTrue(self.citizen.awaiting_isibo)

    def test_reject_keeps_citizen_where_they_were(self):
        transfer = self.send_transfer()
        res = self.as_user(self.receiver).post(f'/api/citizens/transfers/{transfer.id}/reject/',
                                               {'note': 'Not known here'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['status'], 'rejected')
        self.citizen.refresh_from_db()
        self.assertEqual(self.citizen.village, FROM_VILLAGE)
        self.assertIsNone(self.citizen.transferred_from_village)
        notice = Notification.objects.get(user=self.sender)
        self.assertEqual(notice.title, 'Citizen transfer declined')
        self.assertIn('Not known here', notice.message)
        # A decided transfer cannot be decided again
        res = self.as_user(self.receiver).post(f'/api/citizens/transfers/{transfer.id}/accept/', {}, format='json')
        self.assertEqual(res.status_code, 400)

    def test_sender_can_cancel_but_not_accept(self):
        transfer = self.send_transfer()
        res = self.as_user(self.sender).post(f'/api/citizens/transfers/{transfer.id}/accept/', {}, format='json')
        self.assertEqual(res.status_code, 403)
        res = self.as_user(self.sender).post(f'/api/citizens/transfers/{transfer.id}/cancel/', {}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['status'], 'cancelled')
        self.assertTrue(Notification.objects.filter(user=self.receiver, title='Citizen transfer cancelled').exists())
        # Once cancelled, a new transfer can be sent
        self.send_transfer()

    def test_admin_edits_user_and_leader_cannot(self):
        admin = CustomUser.objects.create_user(username='admin', password='x', role='system_admin')
        res = self.as_user(admin).patch(f'/api/users/{self.sender.id}/',
                                        {'first_name': 'Jean', 'phone': '250788000000', 'role': 'cell_leader',
                                         'cell': 100101, 'password': 'Strong#Pass1'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.sender.refresh_from_db()
        self.assertEqual((self.sender.first_name, self.sender.phone, self.sender.role, self.sender.cell),
                         ('Jean', '250788000000', 'cell_leader', 100101))
        self.assertTrue(self.sender.check_password('Strong#Pass1'))
        # Phone: 10 digits starting 07, or 12 digits starting 2507; anything else is refused
        for bad in ('078800000', '07880000000', '25078800000', '2517880000000', '+250788000000', '0688000000'):
            res = self.as_user(admin).patch(f'/api/users/{self.sender.id}/', {'phone': bad}, format='json')
            self.assertEqual(res.status_code, 400, bad)
            self.assertIn('phone', res.data)
        res = self.as_user(admin).patch(f'/api/users/{self.sender.id}/', {'phone': '0788000000'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        # Citizens' phones follow the same rule (isibo leaders edit citizens)
        isibo_leader = CustomUser.objects.create_user(username='isibo', password='x', role='isibo_leader',
                                                      village=FROM_VILLAGE, isibo='Amahoro')
        res = self.as_user(isibo_leader).patch(f'/api/citizens/{self.citizen.id}/', {'phone': '079123456'}, format='json')
        self.assertEqual(res.status_code, 400, res.data)
        res = self.as_user(isibo_leader).patch(f'/api/citizens/{self.citizen.id}/', {'phone': '250791234567'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        # A role that needs a location it does not have is refused
        res = self.as_user(admin).patch(f'/api/users/{self.receiver.id}/', {'role': 'sector_leader'}, format='json')
        self.assertEqual(res.status_code, 400)
        # Admins cannot demote or deactivate themselves; a village leader cannot edit anyone
        res = self.as_user(admin).patch(f'/api/users/{admin.id}/', {'role': 'citizen', 'is_active': False}, format='json')
        self.assertEqual(res.status_code, 200)
        admin.refresh_from_db()
        self.assertEqual((admin.role, admin.is_active), ('system_admin', True))
        res = self.as_user(self.receiver).patch(f'/api/users/{self.sender.id}/', {'first_name': 'X'}, format='json')
        self.assertEqual(res.status_code, 403)

    def test_user_list_pages_five_at_a_time(self):
        admin = CustomUser.objects.create_user(username='admin', password='x', role='system_admin')
        for i in range(6):
            CustomUser.objects.create_user(username=f'citizen{i}', password='x', role='citizen', village=FROM_VILLAGE)
        client = self.as_user(admin)
        # 9 accounts in total: admin, sender, receiver and six citizens
        res = client.get('/api/users/?limit=5&offset=0')
        self.assertEqual(res.status_code, 200)
        self.assertEqual((len(res.data['results']), res.data['count'], res.data['next_offset']), (5, 9, 5))
        self.assertEqual(res.data['role_counts']['citizen'], 6)
        res = client.get('/api/users/?limit=5&offset=5')
        self.assertEqual((len(res.data['results']), res.data['next_offset']), (4, None))
        # Search and role filters are applied on the server
        res = client.get('/api/users/?limit=5&offset=0&role=village_leader')
        self.assertEqual([u['username'] for u in res.data['results']], ['receiver', 'sender'])
        res = client.get('/api/users/?limit=5&offset=0&q=Kigarama')
        self.assertEqual(res.data['count'], 7)  # sender plus the six citizens tied to that village
        # Without ?limit the old full-list shape still works for the eligibility page
        res = client.get('/api/users/')
        self.assertEqual(len(res.data), 9)

    def test_unrelated_leader_cannot_decide(self):
        transfer = self.send_transfer()
        LocationImport.objects.create(location_id=10010301, type='VILLAGE', name='Elsewhere', status='active')
        other = leader('other', 10010301)
        for decision in ('accept', 'reject', 'cancel'):
            res = self.as_user(other).post(f'/api/citizens/transfers/{transfer.id}/{decision}/', {}, format='json')
            self.assertEqual(res.status_code, 403, decision)

    def test_cell_and_sector_leaders_announce_for_their_whole_area(self):
        cell_leader = CustomUser.objects.create_user(username='cell', password='x', role='cell_leader', cell=100101,
                                                     first_name='Cell', last_name='Leader')
        sector_leader = CustomUser.objects.create_user(username='sector', password='x', role='sector_leader',
                                                       sector=1001, first_name='Sector', last_name='Leader')
        body = {'kind': 'umuganda', 'language': 'en', 'event_date': '2026-10-03', 'letter_date': '2026-09-22'}
        # A cell leader's letter starts with the cell office and its letterhead stops at the cell, whatever village is sent
        res = self.as_user(cell_leader).post('/api/announcements/preview/', {**body, 'village': TO_VILLAGE}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual((res.data['letterhead']['cell'], res.data['letterhead']['village']), ('Cell A', ''))
        self.assertTrue(res.data['paragraphs'][1]['text'].startswith('The Office of Cell A Cell'))
        self.assertEqual(res.data['paragraphs'][-2]['text'], 'Cell Leader')
        # Date, venue, gathering place and times are the bold parts of the letter
        res = self.as_user(cell_leader).post('/api/announcements/preview/', {
            **body, 'venue': 'GANZA village', 'start_time': '08:30',
            'meeting_points': [{'audience': 'Students', 'place': 'DUSAIDI Hall', 'time': '07:45'}],
        }, format='json')
        bold = [p['text'] for para in res.data['paragraphs'] for p in para['parts'] if p['bold']]
        self.assertEqual(bold, ['Saturday, 03 October 2026', 'GANZA village', '8:30 AM', 'DUSAIDI Hall', '7:45 AM'])
        self.assertEqual(res.data['paragraphs'][2]['text'],
                         'Students will gather at DUSAIDI Hall at 7:45 AM. Further details about the location and '
                         'activities will be shared at the gathering point.')
        # The generated Word letter carries the same bold runs
        from docx import Document
        from .documents import render_announcement
        ann = Announcement(created_by=cell_leader, village=100101, kind='umuganda', language='en', venue='GANZA village',
                           start_time='08:30', letter_date=datetime.date(2026, 9, 22), event_date=datetime.date(2026, 10, 3))
        data, filename = render_announcement(ann, cell_leader)
        runs = [r.text for p in Document(io.BytesIO(data)).paragraphs for r in p.runs if r.bold]
        self.assertIn('GANZA village', runs)
        self.assertIn('8:30 AM', runs)
        # Sector leader: letterhead ends at the sector, in Kinyarwanda too
        res = self.as_user(sector_leader).post('/api/announcements/preview/', {**body, 'language': 'rw'}, format='json')
        self.assertEqual((res.data['letterhead']['sector'], res.data['letterhead']['cell']), ('Sector A', ''))
        self.assertTrue(res.data['paragraphs'][1]['text'].startswith("Ubuyobozi bw'umurenge wa Sector A"))
        self.assertEqual(res.data['paragraphs'][-2]['text'], "Umuyobozi w'umurenge wa Sector A")
        # Published cell and sector letters reach the village leader and citizens below them, village letters stay local
        Announcement.objects.create(created_by=cell_leader, village=100101, letter_date=datetime.date.today(), published=True)
        Announcement.objects.create(created_by=sector_leader, village=1001, letter_date=datetime.date.today(), published=True)
        Announcement.objects.create(created_by=self.receiver, village=TO_VILLAGE, letter_date=datetime.date.today(), published=True)
        citizen = CustomUser.objects.create_user(username='cit', password='x', role='citizen', village=FROM_VILLAGE)
        seen = lambda user: sorted(a['village'] for a in self.as_user(user).get('/api/announcements/').data['announcements'])
        self.assertEqual(seen(citizen), [1001, 100101])
        self.assertEqual(seen(self.sender), [1001, 100101])
        self.assertEqual(seen(self.receiver), [1001, TO_VILLAGE])
        self.assertEqual(seen(cell_leader), [1001, 100101])
        self.assertEqual(seen(sector_leader), [1001, 100101, TO_VILLAGE])

    def test_leader_stats_count_only_the_leaders_own_work(self):
        cell_leader = CustomUser.objects.create_user(username='cell', password='x', role='cell_leader', cell=100101,
                                                     first_name='Cell', last_name='Leader')
        applicant = CustomUser.objects.create_user(username='app', password='x', role='citizen', village=FROM_VILLAGE)
        # Two letters the sender issued as village leader, one of them since endorsed by the cell leader
        for status_, history in (('village_approved', []),
                                 ('cell_approved', [{'level': 'cell', 'by': cell_leader.display_name}])):
            CertificateRequest.objects.create(user=applicant, cert_type='conduct', village=FROM_VILLAGE,
                                              status=status_, approved_by=self.sender, code_history=history)
        # A letter the receiver issued in the other village
        CertificateRequest.objects.create(user=applicant, cert_type='conduct', village=TO_VILLAGE,
                                          status='approved', approved_by=self.receiver)
        Announcement.objects.create(created_by=self.sender, village=FROM_VILLAGE, letter_date=datetime.date.today(),
                                    published=True)
        Announcement.objects.create(created_by=self.sender, village=FROM_VILLAGE, letter_date=datetime.date.today())
        Activity.objects.create(title='Umuganda', date=datetime.date.today(), location_code=FROM_VILLAGE,
                                created_by=self.sender)
        ServicePayment.objects.create(citizen=self.citizen, service='cleaning', trimester=1, year=2026, amount=500,
                                      recorded_by=self.sender)
        transfer = self.send_transfer()
        self.as_user(self.receiver).post(f'/api/citizens/transfers/{transfer.id}/accept/', {'isibo': 'Ubumwe'},
                                         format='json')

        res = self.as_user(self.sender).get('/api/dashboard/leader/')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(
            {k: res.data[k] for k in ('approved', 'fully_approved', 'announcements', 'announcements_published',
                                      'activities', 'deaths', 'transfers', 'payments', 'citizens')},
            {'approved': 2, 'fully_approved': 0, 'announcements': 2, 'announcements_published': 1,
             'activities': 1, 'deaths': 0, 'transfers': 1, 'payments': 1, 'citizens': 0})
        # The cell leader is counted through the endorsement written into the letter's code history; Alice has left their cell
        res = self.as_user(cell_leader).get('/api/dashboard/leader/')
        self.assertEqual((res.data['approved'], res.data['citizens']), (1, 0))
        # The receiving leader counts the transfer they accepted and the citizen now in their village
        res = self.as_user(self.receiver).get('/api/dashboard/leader/')
        self.assertEqual((res.data['approved'], res.data['fully_approved'], res.data['transfers'], res.data['citizens']),
                         (1, 1, 1, 1))
        # Citizens have no work summary
        self.assertEqual(self.as_user(applicant).get('/api/dashboard/leader/').status_code, 403)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix='certify-test-media-'))
class DataManagementTests(TestCase):
    """System admin bulk deletion: counts, partial deletion by dataset and date, file cleanup, guards."""

    def setUp(self):
        # The database rolls back between tests but files do not: start each test with an empty media folder
        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)
        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
        make_locations()
        self.admin = CustomUser.objects.create_user(username='admin', password='x', role='system_admin')
        self.other_admin = CustomUser.objects.create_user(username='admin2', password='x', role='system_admin')
        self.leader = leader('sender', FROM_VILLAGE)
        self.citizen_user = CustomUser.objects.create_user(username='cit', password='x', role='citizen', village=FROM_VILLAGE)
        self.req = CertificateRequest.objects.create(user=self.citizen_user, cert_type='conduct', status='village_approved')
        self.req.generated_document.save('letter.docx', ContentFile(b'letter'), save=True)
        att = RequestAttachment.objects.create(request=self.req, kind='proof', original_name='id.pdf', size=3)
        att.file.save('id.pdf', ContentFile(b'pdf'), save=True)
        Notification.objects.create(user=self.leader, title='New request', request=self.req)
        Notification.objects.create(user=self.leader, title='Old notice')
        Notification.objects.filter(title='Old notice').update(created_at=timezone.now() - datetime.timedelta(days=400))
        ann = Announcement.objects.create(created_by=self.leader, village=FROM_VILLAGE, letter_date=datetime.date.today())
        ann.generated_document.save('ann.docx', ContentFile(b'ann'), save=True)
        self.citizen = Citizen.objects.create(first_name='Alice', last_name='Uwase', national_id='1199000000000001',
                                              age=30, village=FROM_VILLAGE, added_by=self.leader)
        dead = Citizen.objects.create(first_name='Bob', last_name='Gone', national_id='1199000000000002', age=80,
                                      village=FROM_VILLAGE, status='deceased')
        DeathReport.objects.create(citizen=dead, date_of_death=datetime.date(2024, 1, 1), village=FROM_VILLAGE)
        ServicePayment.objects.create(citizen=self.citizen, service='cleaning', trimester=1, year=2025, amount=1000)
        act = Activity.objects.create(title='Umuganda', date=datetime.date.today(), location_code=FROM_VILLAGE, created_by=self.leader)
        Attendance.objects.create(activity=act, citizen=self.citizen, marked_by=self.leader)
        # A stray file nothing points to
        default_storage.save('generated/orphan.docx', ContentFile(b'orphan'))

    def as_user(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def test_only_admins_and_confirmation_phrase(self):
        self.assertEqual(self.as_user(self.leader).get('/api/data/').status_code, 403)
        res = self.as_user(self.leader).post('/api/data/purge/', {'datasets': ['notifications'], 'confirm': 'DELETE'}, format='json')
        self.assertEqual(res.status_code, 403)
        res = self.as_user(self.admin).post('/api/data/purge/', {'datasets': ['notifications'], 'confirm': 'delete please'}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('confirm', res.data)
        res = self.as_user(self.admin).post('/api/data/purge/', {'datasets': ['nonsense'], 'confirm': 'DELETE'}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(Notification.objects.count(), 2)

    def test_overview_counts_rows_files_and_orphans(self):
        res = self.as_user(self.admin).get('/api/data/')
        self.assertEqual(res.status_code, 200, res.data)
        rows = {d['key']: d for d in res.data['datasets']}
        self.assertEqual((rows['requests']['rows'], rows['requests']['files']), (1, 2))
        self.assertEqual(rows['notifications']['rows'], 2)
        self.assertEqual(rows['deaths']['rows'], 1)
        self.assertEqual(rows['citizens']['rows'], 2)
        self.assertEqual(rows['accounts']['rows'], 2)  # leader and citizen; both admins are kept
        self.assertEqual(rows['orphan_files']['files'], 1)
        self.assertEqual(res.data['storage']['files'], 4)
        self.assertEqual(res.data['confirm_phrase'], 'DELETE')
        # The date cutoff narrows the counts
        cutoff = (timezone.now() - datetime.timedelta(days=30)).date().isoformat()
        res = self.as_user(self.admin).get(f'/api/data/?before={cutoff}')
        rows = {d['key']: d for d in res.data['datasets']}
        self.assertEqual(rows['notifications']['rows'], 1)
        self.assertEqual(rows['requests']['rows'], 0)
        self.assertEqual(rows['orphan_files']['files'], 1)  # not limited by date
        self.assertEqual(self.as_user(self.admin).get('/api/data/?before=yesterday').status_code, 400)

    def test_partial_purge_by_dataset_and_date(self):
        cutoff = (timezone.now() - datetime.timedelta(days=30)).date().isoformat()
        res = self.as_user(self.admin).post('/api/data/purge/', {'datasets': ['notifications'], 'before': cutoff, 'confirm': 'DELETE'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['rows'], 1)
        self.assertEqual([n.title for n in Notification.objects.all()], ['New request'])
        self.assertEqual(CertificateRequest.objects.count(), 1)

    def test_purging_requests_removes_their_files_and_notices(self):
        letter, attachment = self.req.generated_document.name, self.req.attachments.first().file.name
        res = self.as_user(self.admin).post('/api/data/purge/', {'datasets': ['requests', 'orphan_files'], 'confirm': 'DELETE'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(CertificateRequest.objects.count(), 0)
        self.assertEqual(RequestAttachment.objects.count(), 0)
        self.assertFalse(Notification.objects.filter(title='New request').exists())
        self.assertTrue(Notification.objects.filter(title='Old notice').exists())
        self.assertFalse(default_storage.exists(letter))
        self.assertFalse(default_storage.exists(attachment))
        self.assertFalse(default_storage.exists('generated/orphan.docx'))
        self.assertEqual(res.data['files'], 3)
        self.assertGreater(res.data['bytes'], 0)
        self.assertIn('overview', res.data)

    def test_letters_purge_keeps_requests(self):
        res = self.as_user(self.admin).post('/api/data/purge/', {'datasets': ['letters'], 'confirm': 'DELETE'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.req.refresh_from_db()
        self.assertFalse(self.req.generated_document)
        self.assertEqual(self.req.status, 'village_approved')
        self.assertEqual(res.data['files'], 1)

    def test_deaths_purge_removes_only_deceased(self):
        res = self.as_user(self.admin).post('/api/data/purge/', {'datasets': ['deaths'], 'confirm': 'DELETE'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(DeathReport.objects.count(), 0)
        self.assertEqual(list(Citizen.objects.values_list('first_name', flat=True)), ['Alice'])

    def test_clear_everything_keeps_admins_locations_and_settings(self):
        keys = [d['key'] for d in self.as_user(self.admin).get('/api/data/').data['datasets']]
        res = self.as_user(self.admin).post('/api/data/purge/', {'datasets': keys, 'confirm': 'DELETE'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        for model in (CertificateRequest, RequestAttachment, Notification, Announcement, Citizen, DeathReport,
                      ServicePayment, Activity, Attendance, CitizenTransfer):
            self.assertEqual(model.objects.count(), 0, model.__name__)
        self.assertEqual(set(CustomUser.objects.values_list('username', flat=True)), {'admin', 'admin2'})
        self.assertEqual(LocationImport.objects.count(), 5)
        self.assertEqual(res.data['overview']['storage']['files'], 0)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix='certify-test-media-'))
class YouthAndIdTests(TestCase):
    """National IDs fill in the age, 16-30 year olds are youth, and youth leaders see and announce to them only."""

    def setUp(self):
        make_locations()
        self.year = datetime.date.today().year
        self.isibo = CustomUser.objects.create_user(username='isibo', password='x', role='isibo_leader',
                                                    village=FROM_VILLAGE, isibo='Amahoro')
        self.cell_youth = CustomUser.objects.create_user(username='cy', password='x', role='cell_youth_leader',
                                                         cell=100101, first_name='Cy', last_name='Leader')
        self.sector_youth = CustomUser.objects.create_user(username='sy', password='x', role='sector_youth_leader',
                                                           sector=1001, first_name='Sy', last_name='Leader')

    def as_user(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def nid(self, birth_year, serial=1):
        # 16 digits: citizen type, birth year, sex, then a running number
        return f'1{birth_year}8{serial:010d}'

    def add(self, **fields):
        body = {'first_name': 'Test', 'last_name': 'Person', **fields}
        return self.as_user(self.isibo).post('/api/citizens/', body, format='json')

    def test_national_id_fills_age_and_category(self):
        res = self.add(national_id=self.nid(self.year - 20))
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual((res.data['age'], res.data['category'], res.data['id_type']), (20, 'youth', 'national_id'))
        # The ID wins over a typed age; 31 is no longer youth
        res = self.add(national_id=self.nid(self.year - 31, 2), age=5)
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual((res.data['age'], res.data['category']), (31, 'citizen'))

    def test_national_id_must_have_sixteen_digits_and_passport_needs_age(self):
        self.assertIn('national_id', self.add(national_id='120028034238801').data)
        self.assertIn('age', self.add(id_type='passport', national_id='pc123456').data)
        res = self.add(id_type='passport', national_id='pc123456', age=16)
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual((res.data['national_id'], res.data['category']), ('PC123456', 'youth'))

    def make_people(self):
        young = Citizen.objects.create(first_name='Young', last_name='A', national_id='1', age=20, village=FROM_VILLAGE)
        Citizen.objects.create(first_name='Old', last_name='B', national_id='2', age=45, village=FROM_VILLAGE)
        other = Citizen.objects.create(first_name='Young', last_name='C', national_id='3', age=16, village=TO_VILLAGE)
        return young, other

    def test_youth_leaders_see_only_the_youth_of_their_area(self):
        young, other_cell = self.make_people()
        res = self.as_user(self.cell_youth).get('/api/citizens/')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertTrue(res.data['youth_only'])
        self.assertEqual([c['id'] for c in res.data['citizens']], [young.id])
        # The adult in the same cell is out of reach entirely
        adult = Citizen.objects.get(last_name='B')
        self.assertEqual(self.as_user(self.cell_youth).get(f'/api/citizens/{adult.id}/').status_code, 404)
        # The sector youth leader covers both cells
        res = self.as_user(self.sector_youth).get('/api/citizens/')
        self.assertEqual(sorted(c['id'] for c in res.data['citizens']), sorted([young.id, other_cell.id]))
        self.assertEqual(self.as_user(self.sector_youth).get('/api/dashboard/leader/').data['citizens'], 2)

    def test_category_filter_for_ordinary_leaders(self):
        self.make_people()
        cell_leader = CustomUser.objects.create_user(username='cl', password='x', role='cell_leader', cell=100101)
        names = lambda res: sorted(c['last_name'] for c in res.data['citizens'])
        self.assertEqual(names(self.as_user(cell_leader).get('/api/citizens/')), ['A', 'B'])
        self.assertEqual(names(self.as_user(cell_leader).get('/api/citizens/?category=youth')), ['A'])
        self.assertEqual(names(self.as_user(cell_leader).get('/api/citizens/?category=citizen')), ['B'])

    def test_youth_leader_announcement_is_for_the_youth_of_their_cell(self):
        body = {'kind': 'meeting', 'language': 'en', 'title': 'Youth meeting', 'letter_date': str(datetime.date.today()),
                'event_date': str(datetime.date.today()), 'venue': 'Cell office', 'village': TO_VILLAGE}
        res = self.as_user(self.cell_youth).post('/api/announcements/preview/', body, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        text = ' '.join(p['text'] for p in res.data['paragraphs'])
        self.assertIn('Invited: The youth of Cell A Cell.', text)
        self.assertIn('Cell Youth Leader', text)
        res = self.as_user(self.cell_youth).post('/api/announcements/preview/', {**body, 'language': 'rw'}, format='json')
        self.assertIn("Umuyobozi w'Urubyiruko rw'akagari ka Cell A", ' '.join(p['text'] for p in res.data['paragraphs']))
        # Saved letters ignore the requested village: they belong to the whole cell and are flagged for the youth
        res = self.as_user(self.cell_youth).post('/api/announcements/', body, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual((res.data['village'], res.data['for_youth']), (100101, True))
        # A citizen of that cell reads it once published; a village leader's letter is not marked for the youth
        citizen = CustomUser.objects.create_user(username='cit', password='x', role='citizen', village=FROM_VILLAGE)
        self.as_user(self.cell_youth).patch(f"/api/announcements/{res.data['id']}/", {'published': True}, format='json')
        seen = self.as_user(citizen).get('/api/announcements/').data['announcements']
        self.assertEqual([(a['village'], a['for_youth']) for a in seen], [(100101, True)])
