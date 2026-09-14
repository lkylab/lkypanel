"""
W3Panel v2 — Hosting Services Integration Tests
Phase 1: Per-user PHP pool isolation, kernel tuning, and Real-IP restoration.
"""
from django.test import TestCase
from pathlib import Path
from packages.core.models import User, Website, Database, DNSRecord
from services.webserver import (
    create_vhost,
    remove_vhost,
    create_user_php_pool,
    remove_user_php_pool,
    apply_system_tuning,
    get_system_tuning_status,
)
from services.database import create_database, delete_database, generate_secure_password
from services.ssl import issue_certificate
from services.dns import export_zone_file
from services.wizards.wordpress import _generate_wp_config


class HostingServicesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('test_owner', 'owner@local.test', 'Pass123!', role='user')
        self.website = Website.objects.create(
            owner=self.user,
            domain='unittest.local',
            doc_root=f'/tmp/w3panel_test/public_html/unittest.local',
            framework='none',
            php_version='8.3'
        )

    def test_virtualhost_generator(self):
        # 1. By default, site is direct-traffic (proxy_real_ip=False)
        self.assertFalse(self.website.proxy_real_ip)
        res = create_vhost(self.website)
        self.assertTrue(res.get('success'))
        vhost_path = Path(res.get('vhost_path'))
        self.assertTrue(vhost_path.exists())
        content = vhost_path.read_text()
        self.assertIn('unittest.local', content)
        # Dedicated per-tenant PHP-FPM socket
        self.assertIn('php8.3-fpm-test_owner.sock', content)
        # Security headers
        self.assertIn('X-Frame-Options "SAMEORIGIN"', content)
        self.assertIn('X-Content-Type-Options "nosniff"', content)
        self.assertIn('Referrer-Policy', content)
        # Sensitive file protection
        self.assertIn('composer', content)
        self.assertIn('deny all', content)
        # Static asset caching
        self.assertIn('expires 30d', content)
        # Direct site does NOT include proxy real_ip directives (prevents spoofing)
        self.assertNotIn('set_real_ip_from', content)
        self.assertNotIn('real_ip_header X-Forwarded-For', content)

        # 2. When user enables proxy_real_ip for this specific site
        self.website.proxy_real_ip = True
        self.website.save()
        res_proxy = create_vhost(self.website)
        self.assertTrue(res_proxy.get('success'))
        content_proxy = vhost_path.read_text()
        self.assertIn('set_real_ip_from', content_proxy)
        self.assertIn('real_ip_header X-Forwarded-For', content_proxy)

        # 3. Node.js site with custom port
        self.website.framework = 'nodejs'
        self.website.port = 4567
        self.website.save()
        res_node = create_vhost(self.website)
        self.assertTrue(res_node.get('success'))
        content_node = vhost_path.read_text()
        self.assertIn('http://127.0.0.1:4567', content_node)
        self.assertIn('@node_backend', content_node)

        # Test cleanup
        remove_res = remove_vhost('unittest.local')
        self.assertTrue(remove_res.get('success'))

    def test_user_php_pool_isolation(self):
        # 1. Create dedicated tenant pool
        pool_res = create_user_php_pool(
            username='test_tenant',
            php_version='8.3',
            memory_limit='256M',
            upload_max_filesize='64M'
        )
        self.assertTrue(pool_res.get('success'))
        pool_path = Path(pool_res.get('pool_path'))
        self.assertTrue(pool_path.exists())

        pool_content = pool_path.read_text()
        self.assertIn('[test_tenant]', pool_content)
        self.assertIn('php8.3-fpm-test_tenant.sock', pool_content)
        self.assertIn('open_basedir', pool_content)
        self.assertIn('upload_tmp_dir', pool_content)
        self.assertIn('session.save_path', pool_content)

        # 2. Cleanup tenant pool
        rm_res = remove_user_php_pool(username='test_tenant', php_version='8.3')
        self.assertTrue(rm_res.get('success'))
        self.assertFalse(pool_path.exists())

    def test_system_tuning_status(self):
        status = get_system_tuning_status('8.3')
        self.assertIn('sysctl', status)
        self.assertIn('limits', status)
        self.assertIn('opcache', status)
        self.assertIn('pool_count', status)
        self.assertIn('fully_tuned', status)
        self.assertIsInstance(status['pool_count'], int)

    def test_user_website_toggle_proxy_view(self):
        self.client.force_login(self.user)
        session = self.client.session
        session['user_id'] = self.user.id
        session.save()

        self.assertFalse(self.website.proxy_real_ip)
        resp = self.client.post(f'/user/websites/{self.website.id}/toggle-proxy/')
        self.assertEqual(resp.status_code, 302)
        self.website.refresh_from_db()
        self.assertTrue(self.website.proxy_real_ip)

        # Toggle back
        resp2 = self.client.post(f'/user/websites/{self.website.id}/toggle-proxy/')
        self.assertEqual(resp2.status_code, 302)
        self.website.refresh_from_db()
        self.assertFalse(self.website.proxy_real_ip)

    def test_database_password_and_provision(self):
        pwd = generate_secure_password(20)
        self.assertEqual(len(pwd), 20)
        res = create_database('test_db', 'test_user', pwd)
        self.assertTrue(res.get('success'))

    def test_ssl_self_signed_generation(self):
        res = issue_certificate(self.website)
        self.assertTrue(res.get('success'))
        self.assertTrue(self.website.ssl_enabled)
        cert_path = Path(res.get('cert'))
        self.assertTrue(cert_path.exists())

    def test_dns_zone_file_export(self):
        DNSRecord.objects.create(domain=self.website, record_type='A', name='@', value='1.2.3.4')
        DNSRecord.objects.create(domain=self.website, record_type='CNAME', name='www', value='unittest.local')
        res = export_zone_file(self.website.domain, self.website.dns_records.all())
        self.assertTrue(res.get('success'))
        zone_path = Path(res.get('path'))
        self.assertTrue(zone_path.exists())
        zone_content = zone_path.read_text()
        self.assertIn('1.2.3.4', zone_content)

    def test_wp_config_generator(self):
        tmp_dir = Path('/tmp/w3panel_test/wp')
        tmp_dir.mkdir(parents=True, exist_ok=True)
        _generate_wp_config(tmp_dir, 'wp_db', 'wp_usr', 'wp_pw')
        wp_conf = tmp_dir / 'wp-config.php'
        self.assertTrue(wp_conf.exists())
        content = wp_conf.read_text()
        self.assertIn('wp_db', content)
        self.assertIn('AUTH_KEY', content)

    def test_process_manager_systemd(self):
        from services.process_manager import (
            setup_app_service,
            start_app,
            stop_app,
            restart_app,
            get_app_status,
            get_app_logs,
            remove_app_service,
            get_service_name,
        )
        self.website.framework = 'nodejs'
        self.website.port = 4000
        self.website.app_entrypoint = 'server.js'
        self.website.app_env_vars = 'FOO=BAR\nAPI_KEY=testkey'
        self.website.save()

        # 1. Unit file setup
        res = setup_app_service(self.website)
        self.assertTrue(res.get('success'))
        unit_path = Path(res.get('unit_path'))
        self.assertTrue(unit_path.exists())
        content = unit_path.read_text()
        self.assertIn('Environment=PORT=4000', content)
        self.assertIn('Environment="FOO=BAR"', content)
        self.assertIn('Environment="API_KEY=testkey"', content)
        self.assertIn('server.js', content)
        self.assertIn('MemoryMax=512M', content)
        self.assertIn('Restart=always', content)

        # 2. Status & action checks
        status = get_app_status(self.website)
        self.assertIn('service_name', status)
        self.assertEqual(status['port'], 4000)

        start_res = start_app(self.website)
        self.assertTrue(start_res.get('success'))

        restart_res = restart_app(self.website)
        self.assertTrue(restart_res.get('success'))

        stop_res = stop_app(self.website)
        self.assertTrue(stop_res.get('success'))

        logs = get_app_logs(self.website)
        self.assertIsInstance(logs, str)

        # 3. Cleanup unit file
        rm_res = remove_app_service(self.website)
        self.assertTrue(rm_res.get('success'))
        self.assertFalse(unit_path.exists())

    def test_laravel_installer_wizard(self):
        from services.wizards import install_laravel
        res = install_laravel(self.website, db_name='test_lv_db', db_user='test_lv_u', db_pass='secret123')
        self.assertTrue(res.get('success'))
        self.website.refresh_from_db()
        self.assertEqual(self.website.framework, 'laravel')
        self.assertTrue(self.website.doc_root.endswith('/public'))

        public_path = Path(self.website.doc_root)
        base_path = public_path.parent
        self.assertTrue((public_path / 'index.php').exists())
        self.assertTrue((base_path / '.env').exists())
        self.assertTrue((base_path / 'storage' / 'framework').exists())

        env_content = (base_path / '.env').read_text()
        self.assertIn('APP_KEY=base64:', env_content)
        self.assertIn('DB_DATABASE=test_lv_db', env_content)

    def test_atomic_releases_and_rollback(self):
        from services.releases import deploy_release, rollback_release, list_releases
        from packages.core.models import Release

        # 1. First deployment
        d1 = deploy_release(self.website, commit_or_version='v1.0.0', notes='Initial deploy')
        self.assertTrue(d1.get('success'))
        r1_id = d1.get('release_id')
        current_link = Path(d1.get('current_link'))
        self.assertTrue(current_link.exists())
        self.assertTrue(current_link.is_symlink())
        self.assertIn(r1_id, str(current_link.resolve()))

        rel1 = Release.objects.get(website=self.website, release_id=r1_id)
        self.assertTrue(rel1.is_current)

        # 2. Second deployment
        import time
        time.sleep(1.1)  # Ensure distinct timestamp
        d2 = deploy_release(self.website, commit_or_version='v1.1.0', notes='Second deploy')
        self.assertTrue(d2.get('success'))
        r2_id = d2.get('release_id')
        self.assertNotEqual(r1_id, r2_id)
        self.assertIn(r2_id, str(current_link.resolve()))

        rel1.refresh_from_db()
        rel2 = Release.objects.get(website=self.website, release_id=r2_id)
        self.assertFalse(rel1.is_current)
        self.assertTrue(rel2.is_current)

        # 3. Rollback to v1.0.0
        rb = rollback_release(self.website, target_release_id=r1_id)
        self.assertTrue(rb.get('success'))
        self.assertIn(r1_id, str(current_link.resolve()))

        rel1.refresh_from_db()
        rel2.refresh_from_db()
        self.assertTrue(rel1.is_current)
        self.assertFalse(rel2.is_current)

        # 4. List releases
        releases = list_releases(self.website)
        self.assertEqual(len(releases), 2)

    def test_database_performance_tuning(self):
        from services.database import apply_database_tuning, get_database_tuning_status
        tune_res = apply_database_tuning()
        self.assertTrue(tune_res.get('success'))
        conf_path = Path(tune_res.get('config_path'))
        self.assertTrue(conf_path.exists())
        conf_content = conf_path.read_text()
        self.assertIn('skip-name-resolve = 1', conf_content)
        self.assertIn('performance_schema = OFF', conf_content)
        self.assertIn('innodb_buffer_pool_size = 128M', conf_content)

        status = get_database_tuning_status()
        self.assertTrue(status.get('tuned'))

    def test_user_website_manage_and_release_views(self):
        self.client.force_login(self.user)
        session = self.client.session
        session['user_id'] = self.user.id
        session.save()

        # 1. GET manage page
        resp = self.client.get(f'/user/websites/{self.website.id}/manage/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Site Configuration')

        # 2. POST update settings
        post_resp = self.client.post(f'/user/websites/{self.website.id}/manage/', {
            'action': 'update_settings',
            'port': '5050',
            'app_entrypoint': 'index.js',
            'php_version': '8.3',
            'app_env_vars': 'TEST=TRUE',
        })
        self.assertEqual(post_resp.status_code, 302)
        self.website.refresh_from_db()
        self.assertEqual(self.website.port, 5050)
        self.assertEqual(self.website.app_entrypoint, 'index.js')

        # 3. POST deploy release view
        deploy_resp = self.client.post(f'/user/websites/{self.website.id}/release-deploy/', {
            'commit_version': 'v2.0.0',
            'notes': 'Automated test release',
        })
        self.assertEqual(deploy_resp.status_code, 302)
        self.assertEqual(self.website.releases.count(), 1)
        rel = self.website.releases.first()
        self.assertEqual(rel.commit_or_version, 'v2.0.0')

    def test_dual_database_engine_manager(self):
        from services.database import (
            create_database,
            delete_database,
            create_database_user,
            grant_user_privileges,
            change_user_password,
            delete_database_user,
            is_mariadb_installed,
            is_postgresql_installed,
        )
        # Verify inspection functions return booleans without error
        self.assertIsInstance(is_mariadb_installed(), bool)
        self.assertIsInstance(is_postgresql_installed(), bool)

        # MariaDB operations
        maria_db = create_database('my_maria_db', 'maria_user', 'pass123', db_type='mariadb')
        self.assertTrue(maria_db.get('success'))
        maria_usr = create_database_user('maria_u2', 'pass123', db_type='mariadb')
        self.assertTrue(maria_usr.get('success'))
        maria_grant = grant_user_privileges('my_maria_db', 'maria_u2', db_type='mariadb')
        self.assertTrue(maria_grant.get('success'))
        maria_pwd = change_user_password('maria_u2', 'newpass123', db_type='mariadb')
        self.assertTrue(maria_pwd.get('success'))
        maria_del_u = delete_database_user('maria_u2', db_type='mariadb')
        self.assertTrue(maria_del_u.get('success'))
        maria_del = delete_database('my_maria_db', 'maria_user', db_type='mariadb')
        self.assertTrue(maria_del.get('success'))

        # PostgreSQL operations
        pg_db = create_database('my_pg_db', 'pg_user', 'pass123', db_type='postgresql')
        self.assertTrue(pg_db.get('success'))
        pg_usr = create_database_user('pg_u2', 'pass123', db_type='postgresql')
        self.assertTrue(pg_usr.get('success'))
        pg_grant = grant_user_privileges('my_pg_db', 'pg_u2', db_type='postgresql')
        self.assertTrue(pg_grant.get('success'))
        pg_pwd = change_user_password('pg_u2', 'newpass123', db_type='postgresql')
        self.assertTrue(pg_pwd.get('success'))
        pg_del_u = delete_database_user('pg_u2', db_type='postgresql')
        self.assertTrue(pg_del_u.get('success'))
        pg_del = delete_database('my_pg_db', 'pg_user', db_type='postgresql')
        self.assertTrue(pg_del.get('success'))

    def test_user_database_actions_view(self):
        self.client.force_login(self.user)
        session = self.client.session
        session['user_id'] = self.user.id
        session.save()

        # 1. GET databases page
        resp = self.client.get('/user/databases/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'MariaDB')
        self.assertContains(resp, 'PostgreSQL')

        # 2. POST create MariaDB database
        create_resp = self.client.post('/user/databases/', {
            'action': 'create_database',
            'name': 'testsite_db',
            'db_type': 'mariadb',
        })
        self.assertEqual(create_resp.status_code, 302)
        self.assertTrue(Database.objects.filter(name=f"{self.user.username}_testsite_db").exists())
        db_obj = Database.objects.get(name=f"{self.user.username}_testsite_db")
        self.assertEqual(db_obj.db_type, 'mariadb')

        # 3. POST create PostgreSQL database
        pg_resp = self.client.post('/user/databases/', {
            'action': 'create_database',
            'name': 'testpg_db',
            'db_type': 'postgresql',
        })
        self.assertEqual(pg_resp.status_code, 302)
        self.assertTrue(Database.objects.filter(name=f"{self.user.username}_testpg_db").exists())
        pg_obj = Database.objects.get(name=f"{self.user.username}_testpg_db")
        self.assertEqual(pg_obj.db_type, 'postgresql')

        # 4. POST delete database via /user/databases/<db_id>/delete/
        del_resp = self.client.post(f'/user/databases/{pg_obj.id}/delete/')
        self.assertEqual(del_resp.status_code, 302)
        self.assertFalse(Database.objects.filter(id=pg_obj.id).exists())

    def test_user_website_lifecycle_views(self):
        self.client.force_login(self.user)
        session = self.client.session
        session['user_id'] = self.user.id
        session.save()

        # 1. GET website create page
        create_get = self.client.get('/user/websites/create/')
        self.assertEqual(create_get.status_code, 200)
        self.assertContains(create_get, 'Create a New Domain')

        # 2. POST create new website
        create_post = self.client.post('/user/websites/create/', {
            'domain': 'newsite.test',
            'framework': 'wordpress',
            'php_version': '8.3',
            'proxy_real_ip': '1',
        })
        self.assertEqual(create_post.status_code, 302)
        self.assertTrue(Website.objects.filter(domain='newsite.test').exists())
        new_site = Website.objects.get(domain='newsite.test')
        self.assertEqual(new_site.owner, self.user)
        self.assertEqual(new_site.framework, 'wordpress')
        self.assertTrue(new_site.proxy_real_ip)

        # 3. GET websites list
        list_resp = self.client.get('/user/websites/')
        self.assertEqual(list_resp.status_code, 200)
        self.assertContains(list_resp, 'newsite.test')

        # 4. POST delete website
        del_resp = self.client.post(f'/user/websites/{new_site.id}/delete/')
        self.assertEqual(del_resp.status_code, 302)
        self.assertFalse(Website.objects.filter(domain='newsite.test').exists())

    def test_vhost_editor_and_logs(self):
        from services.webserver import (
            get_vhost_content,
            save_custom_vhost,
            reset_vhost_to_default,
            get_website_logs,
        )
        self.client.force_login(self.user)
        session = self.client.session
        session['user_id'] = self.user.id
        session.save()

        # 1. Content retrieval and service functions
        initial_content = get_vhost_content(self.website)
        self.assertIn(self.website.domain, initial_content)

        custom_text = f"# Custom Directive\n{initial_content}"
        save_res = save_custom_vhost(self.website, custom_text)
        self.assertTrue(save_res.get('success'))

        reset_res = reset_vhost_to_default(self.website)
        self.assertTrue(reset_res.get('success'))

        logs = get_website_logs(self.website, log_type='error', lines=50)
        self.assertIsInstance(logs, str)

        # 2. User Panel VHost View
        vhost_get = self.client.get(f'/user/websites/{self.website.id}/vhost/')
        self.assertEqual(vhost_get.status_code, 200)
        self.assertContains(vhost_get, 'VirtualHost Editor')

        vhost_save_post = self.client.post(f'/user/websites/{self.website.id}/vhost/', {
            'action': 'save_vhost',
            'vhost_content': initial_content,
        })
        self.assertEqual(vhost_save_post.status_code, 302)

        vhost_reset_post = self.client.post(f'/user/websites/{self.website.id}/vhost/', {
            'action': 'reset_vhost',
        })
        self.assertEqual(vhost_reset_post.status_code, 302)

        # 3. User Panel Logs View
        logs_get = self.client.get(f'/user/websites/{self.website.id}/logs/?type=error')
        self.assertEqual(logs_get.status_code, 200)
        self.assertContains(logs_get, 'HTTP Logs')

    def test_cron_jobs_user_and_admin(self):
        from packages.core.models import CronJob
        self.client.force_login(self.user)
        session = self.client.session
        session['user_id'] = self.user.id
        session.save()

        # 1. User GET cron page
        resp_get = self.client.get('/user/cron/')
        self.assertEqual(resp_get.status_code, 200)
        self.assertContains(resp_get, 'Cron Jobs')

        # 2. User POST add cron job
        resp_post = self.client.post('/user/cron/', {
            'minute': '*/10',
            'hour': '*',
            'day': '*',
            'month': '*',
            'weekday': '*',
            'command': 'php /tmp/test_cron.php',
            'description': 'Test scheduled runner',
        })
        self.assertEqual(resp_post.status_code, 302)
        self.assertTrue(CronJob.objects.filter(owner=self.user, command='php /tmp/test_cron.php').exists())
        cj = CronJob.objects.get(owner=self.user, command='php /tmp/test_cron.php')
        self.assertEqual(cj.schedule, '*/10 * * * *')
        self.assertTrue(cj.is_active)

        # 3. Toggle cron job
        toggle_resp = self.client.post(f'/user/cron/{cj.id}/toggle/')
        self.assertEqual(toggle_resp.status_code, 302)
        cj.refresh_from_db()
        self.assertFalse(cj.is_active)

        # 4. Delete cron job
        del_resp = self.client.post(f'/user/cron/{cj.id}/delete/')
        self.assertEqual(del_resp.status_code, 302)
        self.assertFalse(CronJob.objects.filter(id=cj.id).exists())

        # 5. Admin GET cron page
        admin_user = User.objects.create_user('admin_cron_test', 'admin_cron@test.com', 'Pass123!', role='admin')
        self.client.force_login(admin_user)
        admin_session = self.client.session
        admin_session['user_id'] = admin_user.id
        admin_session.save()

        admin_cron_resp = self.client.get('/services/cron/')
        self.assertEqual(admin_cron_resp.status_code, 200)
        self.assertContains(admin_cron_resp, 'Scheduled Tasks')

    def test_multiphp_and_dns_zone_editor(self):
        from packages.core.models import DNSRecord
        self.client.force_login(self.user)
        session = self.client.session
        session['user_id'] = self.user.id
        session.save()

        # 1. MultiPHP INI GET
        php_get = self.client.get(f'/user/php/?domain_id={self.website.id}')
        self.assertEqual(php_get.status_code, 200)
        self.assertContains(php_get, 'MultiPHP INI Editor')

        # 2. MultiPHP INI POST
        php_post = self.client.post(f'/user/php/?domain_id={self.website.id}', {
            'php_version': '8.3',
            'memory_limit': '512M',
            'upload_max_filesize': '128M',
            'post_max_size': '128M',
            'max_execution_time': '300',
            'display_errors': 'Off',
        })
        self.assertEqual(php_post.status_code, 302)

        # 3. Zone Editor GET
        dns_get = self.client.get(f'/user/dns/?domain_id={self.website.id}')
        self.assertEqual(dns_get.status_code, 200)
        self.assertContains(dns_get, 'Zone Editor')

        # 4. Zone Editor POST add record
        dns_add = self.client.post(f'/user/dns/?domain_id={self.website.id}', {
            'action': 'add_record',
            'record_type': 'A',
            'name': 'blog',
            'value': '192.0.2.123',
            'ttl': '3600',
        })
        self.assertEqual(dns_add.status_code, 302)
        self.assertTrue(DNSRecord.objects.filter(domain=self.website, name='blog').exists())
        rec = DNSRecord.objects.get(domain=self.website, name='blog')
        self.assertEqual(rec.value, '192.0.2.123')

        # 5. Zone Editor delete record
        dns_del = self.client.post(f'/user/dns/{rec.id}/delete/')
        self.assertEqual(dns_del.status_code, 302)
        self.assertFalse(DNSRecord.objects.filter(id=rec.id).exists())

