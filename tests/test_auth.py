"""
W3Panel v2 — Auth, Impersonation & Role Enforcement Tests
"""
from django.test import TestCase, Client
from packages.core.models import User, Package, LoginToken


class AuthAndRoleTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user('admin_test', 'admin@local.test', 'Pass123!', role='admin')
        self.user = User.objects.create_user('client_test', 'user@local.test', 'Pass123!', role='user')
        self.package = Package.objects.create(name='Pro Plan', disk_limit_mb=10000, bandwidth_limit_gb=50)

    def test_user_creation_and_roles(self):
        self.assertEqual(self.admin.role, 'admin')
        self.assertEqual(self.user.role, 'user')
        self.assertTrue(self.admin.check_password('Pass123!'))
        self.assertTrue(self.user.check_password('Pass123!'))

    def test_login_page_renders(self):
        # Admin / Host Manager login
        response = self.client.get('/login/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'W3Host Manager')
        self.assertContains(response, 'Host Manager')

        # User / Client Portal login
        user_resp = self.client.get('/user/login/')
        self.assertEqual(user_resp.status_code, 200)
        self.assertContains(user_resp, 'W3Client Portal')
        self.assertContains(user_resp, 'Client Portal')
        self.assertContains(user_resp, 'Port 2083')

    def test_admin_login_success(self):
        response = self.client.post('/login/', {'username': 'admin_test', 'password': 'Pass123!'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session.get('user_id'), self.admin.id)

    def test_invalid_login_fails(self):
        response = self.client.post('/login/', {'username': 'admin_test', 'password': 'WrongPassword!'})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(self.client.session.get('user_id'))

    def test_admin_user_edit_and_password_reset(self):
        # Log in as admin
        self.client.post('/login/', {'username': 'admin_test', 'password': 'Pass123!'})
        
        # 1. GET user edit page
        resp_get = self.client.get(f'/users/{self.user.id}/edit/')
        self.assertEqual(resp_get.status_code, 200)
        self.assertContains(resp_get, 'client_test')

        # 2. POST update user details and reset password
        resp_post = self.client.post(f'/users/{self.user.id}/edit/', {
            'email': 'updated@local.test',
            'package': self.package.id,
            'role': 'user',
            'password': 'BrandNewPassword999!',
            'is_active': '1',
            'shell_enabled': '1',
        })
        self.assertEqual(resp_post.status_code, 302)

        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'updated@local.test')
        self.assertEqual(self.user.package_id, self.package.id)
        self.assertTrue(self.user.shell_enabled)
        self.assertTrue(self.user.is_active)
        self.assertTrue(self.user.check_password('BrandNewPassword999!'))

    def test_admin_user_toggle_status_and_shell(self):
        self.client.post('/login/', {'username': 'admin_test', 'password': 'Pass123!'})

        # 1. Toggle status
        self.assertTrue(self.user.is_active)
        resp_status = self.client.post(f'/users/{self.user.id}/toggle-status/')
        self.assertEqual(resp_status.status_code, 302)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

        # 2. Toggle shell
        self.assertFalse(self.user.shell_enabled)
        resp_shell = self.client.post(f'/users/{self.user.id}/toggle-shell/')
        self.assertEqual(resp_shell.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.shell_enabled)

    def test_impersonation_sso_flow(self):
        # Admin initiates autologin in new tab
        self.client.post('/login/', {'username': 'admin_test', 'password': 'Pass123!'})
        resp_autologin = self.client.get(f'/users/{self.user.id}/autologin/')
        self.assertEqual(resp_autologin.status_code, 302)
        sso_url = resp_autologin.url
        self.assertIn('/sso/?token=', sso_url)

        token_str = sso_url.split('token=')[1]
        token_obj = LoginToken.objects.get(token=token_str)
        self.assertEqual(token_obj.user, self.user)
        self.assertEqual(token_obj.created_by, self.admin)
        self.assertFalse(token_obj.is_used)

        # Switch to user client session visiting SSO endpoint
        from importlib import import_module
        from django.conf import settings
        SessionStore = import_module(settings.SESSION_ENGINE).SessionStore

        sso_client = Client()
        resp_sso = sso_client.get(f'/sso/?token={token_str}', follow=True, SERVER_PORT='2083')
        self.assertEqual(resp_sso.status_code, 200)
        client_session = SessionStore(sso_client.cookies['w3p_client_session'].value)
        self.assertEqual(client_session.get('user_id'), self.user.id)
        self.assertEqual(client_session.get('impersonated_by'), self.admin.username)
        # Verify no banner is shown to user
        self.assertNotContains(resp_sso, 'Auto-Login:')
        self.assertNotContains(resp_sso, 'Impersonation Mode')
        self.assertNotContains(resp_sso, 'WHM Impersonation')
        self.assertNotContains(resp_sso, 'Return to WHM')

        # Verify token cannot be reused
        token_obj.refresh_from_db()
        self.assertTrue(token_obj.is_used)
        resp_reuse = sso_client.get(f'/sso/?token={token_str}', SERVER_PORT='2083')
        self.assertEqual(resp_reuse.status_code, 302)
        self.assertEqual(resp_reuse.url, '/login/')

    def test_terminal_admin_and_user_access(self):
        # 1. Admin terminal
        self.client.post('/login/', {'username': 'admin_test', 'password': 'Pass123!'})
        resp_admin_term = self.client.get('/terminal/')
        self.assertEqual(resp_admin_term.status_code, 200)

        # Admin terminal exec safe command
        resp_admin_exec = self.client.post('/terminal/exec/', {'command': 'echo admin_ok'})
        self.assertEqual(resp_admin_exec.status_code, 200)
        data = resp_admin_exec.json()
        self.assertIn('admin_ok', data.get('stdout', ''))

        # Admin terminal blocked command
        resp_admin_blocked = self.client.post('/terminal/exec/', {'command': 'rm -rf /'})
        self.assertEqual(resp_admin_blocked.status_code, 200)
        self.assertIn('blocked', resp_admin_blocked.json().get('stderr', '').lower())

        # 2. User terminal
        user_client = Client()
        user_client.post('/user/login/', {'username': 'client_test', 'password': 'Pass123!'})
        
        # User terminal page renders
        resp_user_term = user_client.get('/user/terminal/')
        self.assertEqual(resp_user_term.status_code, 200)

        # User terminal exec with shell disabled (default False)
        resp_user_exec_dis = user_client.post('/user/terminal/exec/', {'command': 'whoami'})
        self.assertEqual(resp_user_exec_dis.status_code, 403)

        # User terminal exec with shell enabled
        self.user.shell_enabled = True
        self.user.save()
        resp_user_exec_en = user_client.post('/user/terminal/exec/', {'command': 'echo user_ok'})
        self.assertEqual(resp_user_exec_en.status_code, 200)
        user_data = resp_user_exec_en.json()
        self.assertIn('user_ok', user_data.get('stdout', ''))
