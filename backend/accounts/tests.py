from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from django.core import mail

class AccountRecoveryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='Password123!'
        )

    def test_forgot_username_success(self):
        url = reverse('accounts:forgot_username')
        response = self.post_email(url, 'test@example.com')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'testuser')
        # Check that email was dispatched
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('LifeSync - Your Username Recovery', mail.outbox[0].subject)
        self.assertIn('testuser', mail.outbox[0].body)

    def test_forgot_username_not_found(self):
        url = reverse('accounts:forgot_username')
        response = self.post_email(url, 'nonexistent@example.com')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_password_reset_by_email(self):
        url = reverse('accounts:password_reset')
        response = self.client.post(url, {'email': 'test@example.com'})
        self.assertRedirects(response, reverse('accounts:password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Password Reset Request', mail.outbox[0].subject)

    def test_password_reset_by_username(self):
        url = reverse('accounts:password_reset')
        response = self.client.post(url, {'email': 'testuser'})
        self.assertRedirects(response, reverse('accounts:password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Password Reset Request', mail.outbox[0].subject)

    def post_email(self, url, email):
        return self.client.post(url, {'email': email})
