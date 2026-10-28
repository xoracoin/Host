from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Notification, NotificationRead

User = get_user_model()

class NotificationSystemTestCase(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username='alice', email='alice@test.uz', password='PassAlice123!')
        self.bob = User.objects.create_user(username='bob', email='bob@test.uz', password='PassBob456!')

        self.broadcast_notif = Notification.objects.create(
            title='Umumiy e\'lon',
            message='Barcha foydalanuvchilar uchun e\'lon',
            type='info',
            target_type='all'
        )

        self.targeted_alice_notif = Notification.objects.create(
            title='Shaxsiy xabar Alice uchun',
            message='Alice xush kelibsiz!',
            type='success',
            target_type='single',
            recipient=self.alice
        )

        self.client_alice = APIClient()
        self.client_alice.credentials(HTTP_AUTHORIZATION=f'Bearer {str(RefreshToken.for_user(self.alice).access_token)}')

        self.client_bob = APIClient()
        self.client_bob.credentials(HTTP_AUTHORIZATION=f'Bearer {str(RefreshToken.for_user(self.bob).access_token)}')

    def test_notification_visibility(self):
        """Alice sees 2 notifications (1 broadcast + 1 targeted). Bob sees only 1 (broadcast)."""
        res_alice = self.client_alice.get('/api/notifications/')
        self.assertEqual(res_alice.status_code, 200)
        self.assertEqual(res_alice.data['total_count'], 2)
        self.assertEqual(res_alice.data['unread_count'], 2)

        res_bob = self.client_bob.get('/api/notifications/')
        self.assertEqual(res_bob.status_code, 200)
        self.assertEqual(res_bob.data['total_count'], 1)
        self.assertEqual(res_bob.data['unread_count'], 1)
        self.assertEqual(res_bob.data['notifications'][0]['id'], self.broadcast_notif.id)

    def test_mark_single_notification_read(self):
        """Marking a single notification read marks it read for Alice without affecting Bob."""
        res = self.client_alice.post(f'/api/notifications/{self.broadcast_notif.id}/read/')
        self.assertEqual(res.status_code, 200)

        unread_alice = self.client_alice.get('/api/notifications/unread-count/').data['unread_count']
        self.assertEqual(unread_alice, 1)

        unread_bob = self.client_bob.get('/api/notifications/unread-count/').data['unread_count']
        self.assertEqual(unread_bob, 1)

    def test_mark_all_read(self):
        """Marking all read resets Alice's unread count to 0."""
        res = self.client_alice.post('/api/notifications/read-all/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['marked_count'], 2)

        unread_alice = self.client_alice.get('/api/notifications/unread-count/').data['unread_count']
        self.assertEqual(unread_alice, 0)

    def test_bob_cannot_mark_alice_targeted_notification(self):
        """Bob cannot access or mark Alice's single notification as read (returns 404)."""
        res = self.client_bob.post(f'/api/notifications/{self.targeted_alice_notif.id}/read/')
        self.assertEqual(res.status_code, 404)

    def test_admin_changelist_view(self):
        """Admin changelist view loads properly and renders badges/targets without errors."""
        admin_user = User.objects.create_superuser(username='superadmin', email='super@test.uz', password='SuperPass123!')
        self.client.force_login(admin_user)
        response = self.client.get('/admin/notifications/notification/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Barcha foydalanuvchilar')
        self.assertContains(response, 'alice')
