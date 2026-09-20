from django.test import TestCase
from rest_framework.test import APIClient

from .models import Citizen, CitizenTransfer, CustomUser, LocationImport, Notification

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
                                        {'first_name': 'Jean', 'phone': '0788000000', 'role': 'cell_leader',
                                         'cell': 100101, 'password': 'Strong#Pass1'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.sender.refresh_from_db()
        self.assertEqual((self.sender.first_name, self.sender.phone, self.sender.role, self.sender.cell),
                         ('Jean', '0788000000', 'cell_leader', 100101))
        self.assertTrue(self.sender.check_password('Strong#Pass1'))
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

    def test_unrelated_leader_cannot_decide(self):
        transfer = self.send_transfer()
        LocationImport.objects.create(location_id=10010301, type='VILLAGE', name='Elsewhere', status='active')
        other = leader('other', 10010301)
        for decision in ('accept', 'reject', 'cancel'):
            res = self.as_user(other).post(f'/api/citizens/transfers/{transfer.id}/{decision}/', {}, format='json')
            self.assertEqual(res.status_code, 403, decision)
