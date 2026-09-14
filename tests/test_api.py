"""
W3Panel v2 — REST API Test Suite
"""
import json
import hashlib
from django.test import TestCase, Client
from packages.core.models import User, APIToken, Website, Database, Mailbox


class RestApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('api_test_user', 'api@local.test', 'Pass123!', role='admin')
        self.raw_token = 'w3p_live_tok_1234567890abcdef'
        token_hash = hashlib.sha256(self.raw_token.encode()).hexdigest()
        self.token = APIToken.objects.create(user=self.user, name='Test Token', token_hash=token_hash)
        self.headers = {'HTTP_AUTHORIZATION': f'Bearer {self.raw_token}'}

    def test_system_metrics_api(self):
        response = self.client.get('/api/v1/system/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('cpu_percent', data)
        self.assertIn('memory', data)
        self.assertIn('disk', data)

    def test_websites_api_crud(self):
        # 1. Create website
        create_res = self.client.post(
            '/api/v1/websites/',
            data=json.dumps({'domain': 'apidomain.local', 'framework': 'none'}),
            content_type='application/json',
            **self.headers
        )
        self.assertEqual(create_res.status_code, 201)
        site_id = create_res.json()['id']

        # 2. List websites
        list_res = self.client.get('/api/v1/websites/', **self.headers)
        self.assertEqual(list_res.status_code, 200)
        self.assertTrue(len(list_res.json()['websites']) >= 1)

        # 3. Delete website
        del_res = self.client.delete(f'/api/v1/websites/{site_id}/', **self.headers)
        self.assertEqual(del_res.status_code, 200)

    def test_databases_api(self):
        create_res = self.client.post(
            '/api/v1/databases/',
            data=json.dumps({'name': 'apidb', 'db_type': 'mariadb'}),
            content_type='application/json',
            **self.headers
        )
        self.assertEqual(create_res.status_code, 201)
        
        list_res = self.client.get('/api/v1/databases/', **self.headers)
        self.assertEqual(list_res.status_code, 200)

    def test_unauthorized_api_fails(self):
        res = self.client.get('/api/v1/websites/')
        self.assertEqual(res.status_code, 401)

    def test_users_api_with_optional_domain(self):
        # Create user with primary domain
        res = self.client.post(
            '/api/v1/users/',
            data=json.dumps({
                'username': 'newclient_api',
                'password': 'Password123!',
                'email': 'newclient@test.local',
                'domain': 'newclientdomain.com'
            }),
            content_type='application/json',
            **self.headers
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data['username'], 'newclient_api')
        self.assertIsNotNone(data['website'])
        self.assertEqual(data['website']['domain'], 'newclientdomain.com')

        # Verify website exists in db
        self.assertTrue(Website.objects.filter(domain='newclientdomain.com').exists())

