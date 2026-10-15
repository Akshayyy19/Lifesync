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


class SecurityNoCacheTests(TestCase):
    """
    Verifies that all dynamic views output strict no-cache headers to eliminate
    back-button cache leaks and BFCache issues when switching users.
    """
    def setUp(self):
        self.user = User.objects.create_user(
            username='cacheuser',
            email='cache@example.com',
            password='Password123!'
        )
        self.user.profile.is_approved = True
        self.user.profile.save()

    def test_dynamic_views_have_no_cache_headers(self):
        response = self.client.get(reverse('accounts:login'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertIn('no-cache', response['Cache-Control'])
        self.assertIn('must-revalidate', response['Cache-Control'])
        self.assertEqual(response['Pragma'], 'no-cache')
        self.assertEqual(response['Expires'], '0')

    def test_authenticated_views_have_no_cache_headers(self):
        self.client.login(username='cacheuser', password='Password123!')
        response = self.client.get(reverse('core:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertIn('no-cache', response['Cache-Control'])
        self.assertIn('must-revalidate', response['Cache-Control'])


class AuthenticationAndBackNavigationTests(TestCase):
    """
    Verifies that authenticated users cannot access the login page (back-button safety),
    and that logging out or switching users isolates sessions cleanly.
    """
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='adminuser',
            email='admin@example.com',
            password='AdminPassword123!'
        )
        self.member = User.objects.create_user(
            username='memberuser',
            email='member@example.com',
            password='MemberPassword123!'
        )
        self.member.profile.is_approved = True
        self.member.profile.save()

    def test_authenticated_user_redirected_from_login_page(self):
        self.client.login(username='memberuser', password='MemberPassword123!')
        response = self.client.get(reverse('accounts:login'))
        # Should redirect to core:dashboard, preventing back-navigation to login
        self.assertRedirects(response, reverse('core:dashboard'))

    def test_logout_flushes_session_and_redirects(self):
        self.client.login(username='adminuser', password='AdminPassword123!')
        response = self.client.get(reverse('accounts:logout'))
        self.assertRedirects(response, reverse('accounts:login'))
        # After logout, accessing dashboard redirects to login
        dash_response = self.client.get(reverse('core:dashboard'))
        self.assertEqual(dash_response.status_code, 302)
        self.assertIn(reverse('accounts:login'), dash_response['Location'])


class AccessControlValidationTests(TestCase):
    """
    Verifies that admin endpoints are strictly protected with @admin_required,
    and regular members are denied and redirected to dashboard rather than login loop.
    """
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='siteadmin',
            email='siteadmin@example.com',
            password='AdminPassword123!'
        )
        self.member = User.objects.create_user(
            username='regularmember',
            email='regular@example.com',
            password='MemberPassword123!'
        )
        self.member.profile.is_approved = True
        self.member.profile.save()

    def test_anonymous_user_redirected_to_login_for_admin_users(self):
        url = reverse('accounts:admin_users')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response['Location'])

    def test_regular_user_denied_admin_users_and_redirected_to_dashboard(self):
        self.client.login(username='regularmember', password='MemberPassword123!')
        url = reverse('accounts:admin_users')
        response = self.client.get(url, follow=True)
        # Should redirect to core:dashboard and show access denied message
        self.assertRedirects(response, reverse('core:dashboard'))
        messages = list(response.context['messages'])
        self.assertTrue(any("Access Denied" in str(m) for m in messages))

    def test_regular_user_denied_admin_action_and_redirected_to_dashboard(self):
        self.client.login(username='regularmember', password='MemberPassword123!')
        url = reverse('accounts:admin_user_action', kwargs={'user_id': self.member.pk})
        response = self.client.post(url, {'action': 'toggle_staff'}, follow=True)
        self.assertRedirects(response, reverse('core:dashboard'))
        messages = list(response.context['messages'])
        self.assertTrue(any("Access Denied" in str(m) for m in messages))

    def test_admin_can_access_admin_users(self):
        self.client.login(username='siteadmin', password='AdminPassword123!')
        url = reverse('accounts:admin_users')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'User Traffic')

    def test_restricted_user_session_terminated_by_middleware(self):
        self.client.login(username='regularmember', password='MemberPassword123!')
        # Admin restricts the user
        self.member.profile.is_restricted = True
        self.member.profile.restriction_reason = 'Violation of rules'
        self.member.profile.save()

        # Next request by user should be blocked and logged out
        response = self.client.get(reverse('core:dashboard'))
        self.assertRedirects(response, reverse('accounts:login'))
