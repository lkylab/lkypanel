"""
W3Panel v2 — Admin Views
Complete administration interface implementations.
"""
import os
import shutil
import psutil
import platform
import subprocess
import logging
from pathlib import Path
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.conf import settings

from packages.core.models import (
    User, Website, Package, SystemSetting, AuditLog, Notification,
    Database, Mailbox, DNSRecord, FTPAccount, CronJob, Backup, FirewallRule, APIToken
)
from packages.plugins.manager import PluginManager

logger = logging.getLogger('w3panel.admin')


def _sidebar_context(active_page=''):
    """Build sidebar navigation data matching OpenPanel reference."""
    unread_count = Notification.objects.filter(is_read=False).count()
    return {
        'active_page': active_page,
        'unread_notifications_count': unread_count,
        'sidebar_accounts': [
            {'label': 'List Accounts', 'url': '/users/', 'active': 'users'},
            {'label': 'Create a New Account', 'url': '/users/create/', 'active': 'user_create'},
            {'label': 'Resellers', 'url': '/resellers/', 'active': 'resellers'},
            {'label': 'Administrators', 'url': '/administrators/', 'active': 'administrators'},
        ],
        'sidebar_plans': [
            {'label': 'Hosting Packages', 'url': '/plans/', 'active': 'plans'},
            {'label': 'Feature Manager', 'url': '/features/', 'active': 'features'},
        ],
        'sidebar_domains': [
            {'label': 'List Websites', 'url': '/websites/', 'active': 'websites'},
            {'label': 'DNS Zone Editor', 'url': '/domains/dns/', 'active': 'dns'},
            {'label': 'DNS Cluster', 'url': '/domains/dns-cluster/', 'active': 'dns-cluster'},
        ],
        'sidebar_services': [
            {'label': 'Service Manager', 'url': '/services/', 'active': 'services'},
            {'label': 'Terminal Console', 'url': '/terminal/', 'active': 'terminal'},
            {'label': 'Cron Jobs & Tasks', 'url': '/services/cron/', 'active': 'cron'},
            {'label': 'System Logs', 'url': '/services/logs/', 'active': 'logs'},
        ],
        'sidebar_settings': [
            {'label': 'Basic WebHost Setup', 'url': '/settings/', 'active': 'settings'},
            {'label': 'PHP Configuration', 'url': '/settings/php/', 'active': 'php'},
            {'label': 'API Access', 'url': '/settings/api/', 'active': 'api'},
        ],
        'sidebar_security': [
            {'label': 'Firewall Manager', 'url': '/security/firewall/', 'active': 'firewall'},
            {'label': 'Two-Factor Auth', 'url': '/security/2fa/', 'active': '2fa'},
        ],
    }


# ===========================================================================
# 1. Auth & Dashboard
# ===========================================================================

def admin_login(request):
    """Admin login page (W3Host Manager style)."""
    if request.method == 'POST':
        from packages.core.auth import authenticate_user, create_session
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        
        try:
            user, is_2fa_required = authenticate_user(username, password, request.META.get('REMOTE_ADDR', ''))
            if user.role not in ('admin', 'reseller'):
                return render(request, 'login.html', {'error': 'Administrator / Reseller access only on W3Host Manager (port 2087).', 'username': username, 'panel_type': 'host'})
            
            create_session(request, user)
            return redirect('admin_dashboard')
        except ValueError as e:
            return render(request, 'login.html', {'error': str(e), 'username': username, 'panel_type': 'host'})
    
    return render(request, 'login.html', {'panel_type': 'host'})


def admin_logout(request):
    """Admin logout."""
    from packages.core.auth import destroy_session
    destroy_session(request)
    return redirect('admin_login')


def admin_dashboard(request):
    """Admin dashboard."""
    stats = {
        'users': User.objects.filter(is_active=True).count(),
        'websites': Website.objects.filter(is_active=True).count(),
        'databases': Database.objects.count(),
        'plugins': len(PluginManager().list_plugins()),
    }
    
    cpu_percent = psutil.cpu_percent(interval=0.1)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    load = psutil.getloadavg()
    
    metrics = {
        'cpu': round(cpu_percent, 1),
        'ram_used': round(ram.used / (1024 * 1024)),
        'ram_total': round(ram.total / (1024 * 1024)),
        'ram_percent': round(ram.percent, 1),
        'disk_used': round(disk.used / (1024 ** 3), 1),
        'disk_total': round(disk.total / (1024 ** 3), 1),
        'disk_percent': round(disk.percent, 1),
        'load': round(load[0], 2),
        'load5': round(load[1], 2),
        'load15': round(load[2], 2),
    }
    
    activity_logs = AuditLog.objects.select_related('user').all()[:10]
    
    os_name = platform.system()
    try:
        with open('/etc/os-release') as f:
            for line in f:
                if line.startswith('PRETTY_NAME='):
                    os_name = line.split('=', 1)[1].strip().strip('"')
                    break
    except Exception:
        os_name = f"{platform.system()} {platform.release()}"

    system = {
        'hostname': platform.node(),
        'kernel': platform.release(),
        'os': os_name,
        'python_version': platform.python_version(),
        'django_version': '4.2',
        'podman_version': _get_podman_version(),
    }
    
    license_tier = SystemSetting.get('license_tier', 'free')
    
    return render(request, 'admin/dashboard.html', {
        **_sidebar_context('dashboard'),
        'stats': stats,
        'metrics': metrics,
        'activity_logs': activity_logs,
        'system': system,
        'license_tier': license_tier,
        'panel_version': getattr(settings, 'W3PANEL_VERSION', '2.0.0'),
    })


# ===========================================================================
# 2. Accounts (Users, Resellers, Administrators)
# ===========================================================================

def admin_users(request):
    """List standard users."""
    users = User.objects.filter(role='user').select_related('package')
    return render(request, 'admin/users.html', {
        **_sidebar_context('users'),
        'users': users,
        'account_type': 'User',
    })


def admin_user_create(request):
    """Create user, with optional primary domain auto-provisioning."""
    packages = Package.objects.all()
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        domain = request.POST.get('domain', '').strip().lower()
        package_id = request.POST.get('package')
        role = request.POST.get('role', 'user')
        shell_enabled = request.POST.get('shell_enabled') in ('1', 'true', 'on')
        
        if username and password:
            if User.objects.filter(username=username).exists():
                messages.error(request, f'Username "{username}" already exists.')
            elif domain and Website.objects.filter(domain=domain).exists():
                messages.error(request, f'Domain "{domain}" is already registered.')
            else:
                pkg = Package.objects.filter(id=package_id).first() if package_id else None
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    role=role,
                    package=pkg,
                    shell_enabled=shell_enabled
                )

                # Sync Linux system password & shell
                from services.webserver import sync_system_user_shell, sync_system_user_password
                sync_system_user_shell(user.username, shell_enabled)
                sync_system_user_password(user.username, password)
                
                # If optional primary domain is provided, provision website immediately
                if domain:
                    doc_root = f"/home/{user.username}/{domain}/public_html"
                    site = Website.objects.create(
                        owner=user,
                        domain=domain,
                        doc_root=doc_root,
                        framework='none',
                        php_version='8.3',
                    )
                    DNSRecord.objects.create(domain=site, record_type='A', name='@', value='127.0.0.1')
                    DNSRecord.objects.create(domain=site, record_type='CNAME', name='www', value=domain)
                    try:
                        from services.webserver import create_vhost
                        create_vhost(site)
                    except Exception as e:
                        logger.warning(f"Could not provision vhost for {domain}: {e}")
                    AuditLog.objects.create(user=user, action='website_created', target=domain)
                    messages.success(request, f'{role.capitalize()} "{username}" created with primary site "{domain}".')
                else:
                    try:
                        from services.webserver import create_user_php_pool
                        create_user_php_pool(username=user.username, php_version='8.3')
                    except Exception as e:
                        logger.warning(f"Could not provision PHP pool for {user.username}: {e}")
                    messages.success(request, f'{role.capitalize()} "{username}" created successfully.')

                if role == 'reseller':
                    return redirect('admin_resellers')
                elif role == 'admin':
                    return redirect('admin_administrators')
                return redirect('admin_users')
        else:
            messages.error(request, 'Username and password are required.')

    return render(request, 'admin/user_create.html', {
        **_sidebar_context('users'),
        'packages': packages,
        'default_role': 'user',
    })


def admin_user_edit(request, user_id):
    """Edit user account: email, package, role, password reset, active status, shell access."""
    target_user = get_object_or_404(User, id=user_id)
    packages = Package.objects.all()

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        package_id = request.POST.get('package')
        role = request.POST.get('role', 'user')
        new_password = request.POST.get('password', '').strip()
        is_active = request.POST.get('is_active') in ('1', 'true', 'on')
        shell_enabled = request.POST.get('shell_enabled') in ('1', 'true', 'on')

        target_user.email = email
        target_user.role = role
        target_user.package = Package.objects.filter(id=package_id).first() if package_id else None

        status_changed = (target_user.is_active != is_active)
        shell_changed = (target_user.shell_enabled != shell_enabled)

        target_user.is_active = is_active
        target_user.shell_enabled = shell_enabled

        if new_password:
            target_user.set_password(new_password)
            from services.webserver import sync_system_user_password
            sync_system_user_password(target_user.username, new_password)

        target_user.save()

        from services.webserver import sync_system_user_shell, sync_system_user_status
        if shell_changed:
            sync_system_user_shell(target_user.username, shell_enabled)
        if status_changed:
            sync_system_user_status(target_user.username, is_active)

        AuditLog.objects.create(
            user=request.panel_user,
            action='user_modified',
            target=target_user.username,
            ip_address=request.META.get('REMOTE_ADDR')
        )
        messages.success(request, f'User "{target_user.username}" updated successfully.')
        if target_user.role == 'reseller':
            return redirect('admin_resellers')
        elif target_user.role == 'admin':
            return redirect('admin_administrators')
        return redirect('admin_users')

    return render(request, 'admin/user_edit.html', {
        **_sidebar_context('users'),
        'target_user': target_user,
        'packages': packages,
    })


def admin_user_toggle_status(request, user_id):
    """Toggle user active / suspended status."""
    if request.method == 'POST':
        target_user = get_object_or_404(User, id=user_id)
        if target_user.username == 'admin' or target_user.id == request.session.get('user_id'):
            messages.error(request, 'Cannot suspend primary administrator account.')
        else:
            target_user.is_active = not target_user.is_active
            target_user.save(update_fields=['is_active'])
            from services.webserver import sync_system_user_status
            sync_system_user_status(target_user.username, target_user.is_active)
            status_str = "activated" if target_user.is_active else "suspended"
            messages.success(request, f'User "{target_user.username}" {status_str}.')
    return redirect('admin_users')


def admin_user_toggle_shell(request, user_id):
    """Toggle user SSH / Terminal shell permission."""
    if request.method == 'POST':
        target_user = get_object_or_404(User, id=user_id)
        target_user.shell_enabled = not target_user.shell_enabled
        target_user.save(update_fields=['shell_enabled'])
        from services.webserver import sync_system_user_shell
        sync_system_user_shell(target_user.username, target_user.shell_enabled)
        state_str = "enabled" if target_user.shell_enabled else "disabled"
        messages.success(request, f'Terminal access {state_str} for "{target_user.username}".')
    return redirect('admin_users')


def admin_user_autologin(request, user_id):
    """W3Host-style 1-click autologin into W3Client Portal in a new tab."""
    admin_user = getattr(request, 'panel_user', None)
    if not admin_user:
        uid = request.session.get('user_id')
        if uid:
            admin_user = User.objects.filter(pk=uid, is_active=True).first()

    if not admin_user or admin_user.role not in ('admin', 'reseller'):
        messages.error(request, 'Unauthorized: Administrator access required.')
        return redirect('admin_login')

    target_user = get_object_or_404(User, id=user_id)

    # If reseller, restrict to accounts under their delegation
    if admin_user.role == 'reseller' and target_user.parent_reseller_id != admin_user.id and target_user.id != admin_user.id:
        messages.error(request, 'Permission denied: Cannot access accounts outside your reseller scope.')
        return redirect('admin_users')

    from packages.core.models import LoginToken
    token_obj = LoginToken.create_for_user(target_user, created_by=admin_user, validity_seconds=120)

    host = request.get_host()
    scheme = 'https' if request.is_secure() or request.META.get('HTTP_X_FORWARDED_PROTO') == 'https' else (request.scheme or 'http')

    if ':12087' in host:
        user_host = host.replace(':12087', ':12083')
    elif ':2087' in host:
        user_host = host.replace(':2087', ':2083')
    elif ':' in host:
        # Development / custom port (e.g. localhost:8000)
        user_host = host
    else:
        server_port = request.META.get('SERVER_PORT', '')
        if server_port in ('2087', '12087'):
            user_host = f"{host}:2083"
        else:
            user_host = host

    sso_url = f"{scheme}://{user_host}/sso/?token={token_obj.token}"
    return redirect(sso_url)


# Alias for backward compatibility
admin_user_impersonate = admin_user_autologin


def admin_terminal(request):
    """Admin Web Terminal Console."""
    server_ip = request.META.get('SERVER_NAME', '127.0.0.1')
    return render(request, 'admin/terminal.html', {
        **_sidebar_context('terminal'),
        'active_section': 'services',
        'server_ip': server_ip,
    })


def admin_terminal_exec(request):
    """Execute command in admin context."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    cmd = request.POST.get('command', '').strip()
    if not cmd:
        return JsonResponse({'stdout': '', 'stderr': '', 'returncode': 0})

    blocked = ['rm -rf /', 'mkfs', ':(){ :|:& };:']
    if any(b in cmd for b in blocked):
        return JsonResponse({'stderr': 'Command blocked by safety filter.', 'returncode': 1})

    try:
        from services.webserver.manager import _has_sudo
        if _has_sudo():
            run_cmd = ['sudo', '-n', 'bash', '-c', cmd]
        else:
            run_cmd = ['bash', '-c', cmd]

        res = subprocess.run(run_cmd, capture_output=True, text=True, timeout=20)
        return JsonResponse({
            'stdout': res.stdout,
            'stderr': res.stderr,
            'returncode': res.returncode,
            'cwd': '/root',
        })
    except subprocess.TimeoutExpired:
        return JsonResponse({'stderr': 'Command execution timed out after 20 seconds.', 'returncode': 124})
    except Exception as e:
        return JsonResponse({'stderr': str(e), 'returncode': 1})


def admin_user_delete(request, user_id):
    """Delete a user and clean up their tenant resources."""
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)
        if user.username == 'admin' or user.id == request.session.get('user_id'):
            messages.error(request, 'You cannot delete the primary admin account.')
        else:
            username = user.username
            role = user.role
            try:
                from services.webserver import remove_user_php_pool
                remove_user_php_pool(username=username)
            except Exception as e:
                logger.warning(f"Could not remove PHP pool for {username}: {e}")
            user.delete()
            messages.success(request, f'Account "{username}" has been deleted.')
            if role == 'reseller':
                return redirect('admin_resellers')
            elif role == 'admin':
                return redirect('admin_administrators')
    return redirect('admin_users')


def admin_resellers(request):
    """List resellers."""
    resellers = User.objects.filter(role='reseller')
    return render(request, 'admin/resellers.html', {
        **_sidebar_context('resellers'),
        'resellers': resellers,
    })


def admin_administrators(request):
    """List administrators."""
    admins = User.objects.filter(role='admin')
    return render(request, 'admin/administrators.html', {
        **_sidebar_context('administrators'),
        'administrators': admins,
    })


# ===========================================================================
# 3. Hosting Plans & Feature Manager
# ===========================================================================

def admin_plans(request):
    """List and create hosting plans."""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        websites_limit = int(request.POST.get('websites_limit', 5))
        databases_limit = int(request.POST.get('databases_limit', 5))
        ftp_limit = int(request.POST.get('ftp_limit', 5))
        email_limit = int(request.POST.get('email_limit', 10))
        disk_limit_mb = int(request.POST.get('disk_limit_mb', 10240))
        bandwidth_limit_gb = int(request.POST.get('bandwidth_limit_gb', 100))

        if name:
            Package.objects.create(
                name=name,
                description=description,
                websites_limit=websites_limit,
                databases_limit=databases_limit,
                ftp_limit=ftp_limit,
                email_limit=email_limit,
                disk_limit_mb=disk_limit_mb,
                bandwidth_limit_gb=bandwidth_limit_gb
            )
            messages.success(request, f'Package "{name}" created successfully.')
            return redirect('admin_plans')

    plans = Package.objects.all()
    return render(request, 'admin/plans.html', {
        **_sidebar_context('plans'),
        'plans': plans,
    })


def admin_plan_delete(request, plan_id):
    """Delete package plan."""
    if request.method == 'POST':
        plan = get_object_or_404(Package, id=plan_id)
        name = plan.name
        plan.delete()
        messages.success(request, f'Package "{name}" deleted successfully.')
    return redirect('admin_plans')


def admin_features(request):
    """Feature Manager matrix."""
    return render(request, 'admin/features.html', {
        **_sidebar_context('features'),
    })


# ===========================================================================
# 4. Domains, DNS & Websites
# ===========================================================================

def admin_websites(request):
    """Websites management."""
    websites = Website.objects.select_related('owner').all()
    is_nginx_installed = bool(shutil.which('nginx'))
    return render(request, 'admin/websites.html', {
        **_sidebar_context('domains'),
        'websites': websites,
        'is_nginx_installed': is_nginx_installed,
    })



def admin_website_toggle_proxy(request, website_id):
    """Toggle Reverse Proxy Real-IP setting for a website."""
    if request.method == 'POST':
        site = get_object_or_404(Website, id=website_id)
        site.proxy_real_ip = not site.proxy_real_ip
        site.save(update_fields=['proxy_real_ip'])
        from services.webserver import create_vhost
        create_vhost(site)
        state = "enabled (Cloudflare/Proxy mode)" if site.proxy_real_ip else "disabled (Direct traffic mode)"
        messages.success(request, f'Reverse Proxy Client IP {state} for {site.domain}.')
    return redirect('admin_websites')


def admin_website_delete(request, website_id):
    """Delete a website."""
    if request.method == 'POST':
        site = get_object_or_404(Website, id=website_id)
        domain = site.domain
        from services.webserver import remove_vhost
        remove_vhost(domain)
        site.delete()
        messages.success(request, f'Domain "{domain}" and its VirtualHost configuration were removed.')
    return redirect('admin_websites')


def admin_website_vhost(request, website_id):
    """Host VirtualHost (Nginx configuration) editor with safety check and rollback."""
    site = get_object_or_404(Website, id=website_id)
    from services.webserver import get_vhost_content, save_custom_vhost, reset_vhost_to_default

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'save_vhost':
            content = request.POST.get('vhost_content', '')
            res = save_custom_vhost(site, content)
            if res.get('success'):
                messages.success(request, f'VirtualHost configuration for {site.domain} updated and validated successfully.')
                return redirect('admin_website_vhost', website_id=site.id)
            else:
                messages.error(request, f"Configuration Error: {res.get('error')}")
        elif action == 'reset_vhost':
            reset_vhost_to_default(site)
            messages.success(request, f'VirtualHost configuration for {site.domain} reset to default template.')
            return redirect('admin_website_vhost', website_id=site.id)

    vhost_content = get_vhost_content(site)
    return render(request, 'admin/website_vhost.html', {
        **_sidebar_context('websites'),
        'site': site,
        'vhost_content': vhost_content,
        'is_nginx_installed': bool(shutil.which('nginx')),
    })


def admin_dns_editor(request):
    """DNS Zone Editor."""
    websites = Website.objects.prefetch_related('dns_records').all()
    selected_domain_id = request.GET.get('domain_id')
    selected_domain = None
    records = []

    if selected_domain_id:
        selected_domain = Website.objects.filter(id=selected_domain_id).first()
    elif websites.exists():
        selected_domain = websites.first()

    if selected_domain:
        records = selected_domain.dns_records.all()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_record' and selected_domain:
            rtype = request.POST.get('record_type', 'A')
            name = request.POST.get('name', '@').strip()
            value = request.POST.get('value', '').strip()
            ttl = int(request.POST.get('ttl', 3600))
            priority = request.POST.get('priority')
            priority_val = int(priority) if priority and priority.isdigit() else None
            if value:
                DNSRecord.objects.create(
                    domain=selected_domain,
                    record_type=rtype,
                    name=name,
                    value=value,
                    ttl=ttl,
                    priority=priority_val
                )
                from services.dns import export_zone_file
                export_zone_file(selected_domain.domain, selected_domain.dns_records.all())
                messages.success(request, f'DNS Record {name} {rtype} added and zone exported.')
                return redirect(f'/domains/dns/?domain_id={selected_domain.id}')

        elif action == 'delete_record':
            record_id = request.POST.get('record_id')
            DNSRecord.objects.filter(id=record_id).delete()
            if selected_domain:
                from services.dns import export_zone_file
                export_zone_file(selected_domain.domain, selected_domain.dns_records.all())
            messages.success(request, 'DNS record deleted and zone updated.')
            return redirect(f'/domains/dns/?domain_id={selected_domain.id if selected_domain else ""}')

    return render(request, 'admin/dns_editor.html', {
        **_sidebar_context('dns'),
        'websites': websites,
        'selected_domain': selected_domain,
        'records': records,
    })


def admin_dns_cluster(request):
    """DNS Cluster Configuration."""
    return render(request, 'admin/dns_cluster.html', {
        **_sidebar_context('dns-cluster'),
    })


# ===========================================================================
# 5. Services & Core Manager
# ===========================================================================

def admin_plugins(request):
    """Plugin management page."""
    manager = PluginManager()
    plugins = manager.list_plugins()
    
    if request.method == 'POST':
        plugin_id = request.POST.get('plugin_id')
        action = request.POST.get('action')
        
        if action == 'install':
            result = manager.install(plugin_id)
            if result['success']:
                messages.success(request, f'Plugin {plugin_id} installed successfully')
            else:
                messages.error(request, f'Failed to install plugin: {result["error"]}')
        elif action == 'uninstall':
            result = manager.uninstall(plugin_id)
            if result['success']:
                messages.success(request, f'Plugin {plugin_id} uninstalled successfully')
            else:
                messages.error(request, f'Failed to uninstall plugin: {result["error"]}')
        elif action == 'start':
            result = manager.start(plugin_id)
            if result['success']:
                messages.success(request, f'Plugin {plugin_id} started')
            else:
                messages.error(request, f'Failed to start plugin: {result["error"]}')
        elif action == 'stop':
            result = manager.stop(plugin_id)
            if result['success']:
                messages.success(request, f'Plugin {plugin_id} stopped')
            else:
                messages.error(request, f'Failed to stop plugin: {result["error"]}')
        
        return redirect('admin_plugins')
    
    return render(request, 'admin/plugins.html', {
        **_sidebar_context('plugins'),
        'plugins': plugins,
    })


def admin_services_status(request):
    """Services status and individual 1-click management/installation."""
    if request.method == 'POST':
        service_name = request.POST.get('service')
        action = request.POST.get('action')

        if action == 'install_service' and service_name:
            # Package mapping for individual services
            pkg_map = {
                'nginx': ['nginx'],
                'mariadb': ['mariadb-server', 'mariadb-client'],
                'postgresql': ['postgresql', 'postgresql-contrib'],
                'redis': ['redis-server'],
                'ufw': ['ufw'],
                'php': ['php-fpm', 'php-mysql', 'php-pgsql', 'php-curl', 'php-zip', 'php-gd', 'php-mbstring', 'php-xml'],
                'certbot': ['certbot', 'python3-certbot-nginx'],
            }
            pkgs = pkg_map.get(service_name, [service_name])
            try:
                subprocess.run(['sudo', 'apt-get', 'update', '-y'], timeout=60)
                cmd = ['sudo', 'apt-get', 'install', '-y'] + pkgs
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
                if res.returncode == 0:
                    daemon_name = 'mariadb' if service_name == 'mariadb' else service_name
                    subprocess.run(['sudo', 'systemctl', 'enable', '--now', daemon_name], timeout=10)
                    messages.success(request, f'{service_name.capitalize()} installed and started successfully!')
                else:
                    messages.error(request, f'Installation failed: {res.stderr}')
            except Exception as e:
                messages.error(request, f'Error installing {service_name}: {e}')
            return redirect('admin_services_status')

        elif action == 'uninstall_service' and service_name:
            pkg_map = {
                'nginx': ['nginx', 'nginx-common'],
                'mariadb': ['mariadb-server', 'mariadb-client'],
                'postgresql': ['postgresql', 'postgresql-contrib'],
                'redis': ['redis-server'],
                'ufw': ['ufw'],
            }
            pkgs = pkg_map.get(service_name, [service_name])
            try:
                subprocess.run(['sudo', 'systemctl', 'stop', service_name], timeout=10)
                cmd = ['sudo', 'apt-get', 'remove', '-y'] + pkgs
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                if res.returncode == 0:
                    messages.success(request, f'{service_name.capitalize()} uninstalled successfully.')
                else:
                    messages.error(request, f'Uninstall failed: {res.stderr}')
            except Exception as e:
                messages.error(request, f'Error uninstalling {service_name}: {e}')
            return redirect('admin_services_status')

        elif action == 'optimize_database':
            from services.database import apply_database_tuning
            res = apply_database_tuning()
            if res.get('success'):
                messages.success(request, 'MariaDB tuned successfully! Applied skip-name-resolve, low-RAM buffer pool, and performance_schema=OFF.')
            else:
                messages.error(request, 'Failed to apply MariaDB optimization.')
            return redirect('admin_services_status')

        elif action in ('start', 'stop', 'restart') and service_name:
            try:
                subprocess.run(['sudo', '-n', 'systemctl', action, service_name], timeout=10)
                messages.success(request, f'Service {service_name} {action}ed successfully.')
            except Exception as e:
                messages.error(request, f'Error executing {action} on {service_name}: {e}')
            return redirect('admin_services_status')

    from services.database import get_database_tuning_status
    db_tuning = get_database_tuning_status()

    services_list = [
        {'name': 'w3panel-admin', 'display': 'W3Host Manager (Port 2087)', 'icon': 'ti ti-shield-check', 'cmd': 'gunicorn', 'desc': 'Core Host Manager Administrative Server'},
        {'name': 'w3panel-user', 'display': 'W3Client Portal (Port 2083)', 'icon': 'ti ti-user-check', 'cmd': 'gunicorn', 'desc': 'End-User Client Hosting Portal Server'},
        {'name': 'nginx', 'display': 'Nginx Web Server', 'icon': 'ti ti-world', 'cmd': 'nginx', 'desc': 'High-Performance Web Server for User Websites (Ports 80 & 443)'},
        {'name': 'mariadb', 'display': 'MariaDB Database Server', 'icon': 'ti ti-database', 'cmd': 'mariadbd', 'desc': 'Relational MySQL Database Engine'},
        {'name': 'postgresql', 'display': 'PostgreSQL Database Server', 'icon': 'ti ti-database-import', 'cmd': 'psql', 'desc': 'Advanced Object-Relational SQL Database Engine'},
        {'name': 'php8.3-fpm', 'display': 'PHP-FPM 8.3 Daemon', 'icon': 'ti ti-brand-php', 'cmd': 'php-fpm8.3', 'desc': 'PHP FastCGI Process Manager for VirtualHosts'},
        {'name': 'ufw', 'display': 'UFW Host Firewall', 'icon': 'ti ti-shield', 'cmd': 'ufw', 'desc': 'Host Inbound Access Firewall'},
        {'name': 'ssh', 'display': 'SSH Remote Access', 'icon': 'ti ti-terminal-2', 'cmd': 'sshd', 'desc': 'Secure Shell Remote Administration'},
    ]

    for s in services_list:
        cmd_check = s.get('cmd', s['name'])
        is_installed = bool(shutil.which(cmd_check) or shutil.which(s['name']))
        if not is_installed:
            s['status'] = 'not_installed'
        else:
            try:
                res = subprocess.run(['systemctl', 'is-active', s['name']], capture_output=True, text=True, timeout=2)
                s['status'] = 'running' if res.stdout.strip() == 'active' else 'stopped'
            except Exception:
                s['status'] = 'stopped'

    return render(request, 'admin/services.html', {
        **_sidebar_context('services'),
        'services': services_list,
        'db_tuning': db_tuning,
    })


def admin_ftp_service(request):
    """FTP management."""
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        directory = request.POST.get('directory', '/').strip()
        if username:
            if FTPAccount.objects.filter(username=username).exists():
                messages.error(request, f'FTP username "{username}" already exists.')
            else:
                owner = request.panel_user or User.objects.filter(role='admin').first()
                FTPAccount.objects.create(owner=owner, username=username, directory=directory)
                messages.success(request, f'FTP user "{username}" created.')
                return redirect('admin_ftp_service')

    ftp_accounts = FTPAccount.objects.select_related('owner').all()
    return render(request, 'admin/ftp.html', {
        **_sidebar_context('ftp'),
        'ftp_accounts': ftp_accounts,
    })


def admin_system_logs(request):
    """Log file viewer."""
    log_files = {
        'panel': '/var/log/w3panel/error.log',
        'access': '/var/log/w3panel/access.log',
        'syslog': '/var/log/syslog',
        'auth': '/var/log/auth.log',
    }
    selected_log = request.GET.get('log', 'panel')
    file_path = log_files.get(selected_log, log_files['panel'])
    
    content = ""
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', errors='ignore') as f:
                lines = f.readlines()
                content = "".join(lines[-150:])  # last 150 lines
        except Exception as e:
            content = f"Error reading log file: {e}"
    else:
        content = f"Log file {file_path} does not exist yet or is empty."

    return render(request, 'admin/logs.html', {
        **_sidebar_context('logs'),
        'selected_log': selected_log,
        'log_content': content,
    })


def admin_cron(request):
    """Host Scheduled Tasks & Cron Jobs manager across all accounts."""
    cron_jobs = CronJob.objects.select_related('owner').all().order_by('-created_at')
    
    system_cron_files = []
    cron_d = Path('/etc/cron.d')
    if cron_d.exists():
        try:
            for p in sorted(cron_d.glob('*')):
                if p.is_file():
                    system_cron_files.append({
                        'name': p.name,
                        'path': str(p),
                        'size': p.stat().st_size,
                    })
        except Exception:
            pass

    return render(request, 'admin/cron.html', {
        **_sidebar_context('cron'),
        'cron_jobs': cron_jobs,
        'system_cron_files': system_cron_files,
    })


# ===========================================================================
# 7. Settings & License
# ===========================================================================

def admin_settings(request):
    """General panel settings."""
    if request.method == 'POST':
        panel_name = request.POST.get('panel_name', 'W3Panel')
        server_hostname = request.POST.get('server_hostname', platform.node())
        default_php = request.POST.get('default_php', '8.3')
        api_rate_limit = request.POST.get('api_rate_limit', '50')
        
        SystemSetting.set('panel_name', panel_name)
        SystemSetting.set('server_hostname', server_hostname)
        SystemSetting.set('default_php', default_php)
        SystemSetting.set('api_rate_limit', api_rate_limit)
        
        messages.success(request, 'Settings saved successfully.')
        return redirect('admin_settings')

    return render(request, 'admin/settings.html', {
        **_sidebar_context('settings'),
        'panel_name': SystemSetting.get('panel_name', 'W3Panel'),
        'server_hostname': SystemSetting.get('server_hostname', platform.node()),
        'default_php': SystemSetting.get('default_php', '8.3'),
        'api_rate_limit': SystemSetting.get('api_rate_limit', '50'),
    })


def admin_license(request):
    """License management page."""
    from packages.license.models import License
    license_obj = License.objects.filter(is_active=True).first()
    
    if request.method == 'POST':
        license_key = request.POST.get('license_key', '').strip()
        if license_key:
            from packages.license.service import activate_license
            result = activate_license(license_key)
            if result['success']:
                messages.success(request, 'License activated successfully!')
                return redirect('admin_license')
            else:
                messages.error(request, f'License activation failed: {result["error"]}')
    
    return render(request, 'admin/license.html', {
        **_sidebar_context('license'),
        'license': license_obj,
        'tier': license_obj.tier if license_obj else 'free',
    })


def admin_api_settings(request):
    """API tokens and access management."""
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'generate_token':
            name = request.POST.get('token_name', 'Default API Token')
            user = request.panel_user or User.objects.filter(role='admin').first()
            raw_token = user.generate_api_token()
            messages.success(request, f'New API Token created: {raw_token} (Save it now, it won\'t be shown again!)')
            return redirect('admin_api_settings')
        elif action == 'revoke_token':
            token_id = request.POST.get('token_id')
            APIToken.objects.filter(id=token_id).delete()
            messages.success(request, 'API Token revoked.')
            return redirect('admin_api_settings')

    tokens = APIToken.objects.select_related('user').all()
    return render(request, 'admin/api_settings.html', {
        **_sidebar_context('api'),
        'tokens': tokens,
        'rate_limit': SystemSetting.get('api_rate_limit', '50'),
    })


def admin_php_settings(request):
    """PHP versions, performance tuning, and per-tenant pool configuration."""
    from services.webserver import apply_system_tuning, get_system_tuning_status, reload_php_fpm

    default_php = SystemSetting.get('default_php', '8.3')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'apply_tuning':
            res = apply_system_tuning(default_php)
            if res.get('success'):
                applied_str = ", ".join(res.get('applied', []))
                messages.success(request, f"Production performance tuning applied successfully: {applied_str}.")
            else:
                messages.error(request, f"Could not apply tuning: {res.get('errors', ['Unknown error'])}")
            return redirect('admin_php_settings')

        if action == 'reload_fpm':
            if reload_php_fpm(default_php):
                messages.success(request, f"PHP-FPM {default_php} reloaded successfully.")
            else:
                messages.warning(request, f"PHP-FPM {default_php} reload bypassed or service not active.")
            return redirect('admin_php_settings')

        default_php = request.POST.get('default_php', '8.3')
        memory_limit = request.POST.get('memory_limit', '256M')
        max_execution = request.POST.get('max_execution_time', '120')
        upload_max = request.POST.get('upload_max_filesize', '64M')
        
        SystemSetting.set('default_php', default_php)
        SystemSetting.set('php_memory_limit', memory_limit)
        SystemSetting.set('php_max_execution_time', max_execution)
        SystemSetting.set('php_upload_max_filesize', upload_max)
        messages.success(request, 'PHP configuration updated.')
        return redirect('admin_php_settings')

    tuning_status = get_system_tuning_status(default_php)

    return render(request, 'admin/php_settings.html', {
        **_sidebar_context('php'),
        'default_php': default_php,
        'memory_limit': SystemSetting.get('php_memory_limit', '256M'),
        'max_execution_time': SystemSetting.get('php_max_execution_time', '120'),
        'upload_max_filesize': SystemSetting.get('php_upload_max_filesize', '64M'),
        'tuning_status': tuning_status,
    })


def admin_notifications_settings(request):
    """Notification alert channels."""
    if request.method == 'POST':
        email_alerts = request.POST.get('email_alerts', '').strip()
        webhook_url = request.POST.get('webhook_url', '').strip()
        
        SystemSetting.set('notify_email', email_alerts)
        SystemSetting.set('notify_webhook', webhook_url)
        messages.success(request, 'Notification channels saved.')
        return redirect('admin_notifications_settings')

    return render(request, 'admin/notifications_settings.html', {
        **_sidebar_context('notifications'),
        'notify_email': SystemSetting.get('notify_email', ''),
        'notify_webhook': SystemSetting.get('notify_webhook', ''),
    })


# ===========================================================================
# 8. Security (Firewall & 2FA)
# ===========================================================================

def admin_firewall(request):
    """Firewall management."""
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_rule':
            port = request.POST.get('port', '').strip()
            protocol = request.POST.get('protocol', 'tcp')
            f_action = request.POST.get('f_action', 'ALLOW')
            source_ip = request.POST.get('source_ip', '0.0.0.0/0').strip() or '0.0.0.0/0'
            comment = request.POST.get('comment', '').strip()

            if port:
                FirewallRule.objects.create(
                    port=port,
                    protocol=protocol,
                    action=f_action,
                    source_ip=source_ip,
                    comment=comment
                )
                try:
                    cmd = ['sudo', 'ufw', f_action.lower(), f'{port}/{protocol}']
                    subprocess.run(cmd, timeout=5)
                except Exception:
                    pass
                messages.success(request, f'Firewall rule for port {port}/{protocol} added.')
                return redirect('admin_firewall')

        elif action == 'delete_rule':
            rule_id = request.POST.get('rule_id')
            rule = get_object_or_404(FirewallRule, id=rule_id)
            try:
                subprocess.run(['sudo', 'ufw', 'delete', rule.action.lower(), f'{rule.port}/{rule.protocol}'], timeout=5)
            except Exception:
                pass
            rule.delete()
            messages.success(request, 'Firewall rule removed.')
            return redirect('admin_firewall')

    rules = FirewallRule.objects.all()
    return render(request, 'admin/firewall.html', {
        **_sidebar_context('firewall'),
        'rules': rules,
    })


def admin_2fa_settings(request):
    """Two-factor authentication management."""
    return render(request, 'admin/2fa.html', {
        **_sidebar_context('2fa'),
    })


# ===========================================================================
# 9. General (Notifications, Wizards, Monitoring)
# ===========================================================================

def admin_notifications(request):
    """Notifications inbox."""
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'mark_all_read':
            Notification.objects.filter(is_read=False).update(is_read=True)
            messages.success(request, 'All notifications marked as read.')
            return redirect('admin_notifications')

    notifs = Notification.objects.all()[:50]
    return render(request, 'admin/notifications.html', {
        **_sidebar_context('notifications'),
        'notifications': notifs,
    })


def wizard_dashboard(request):
    """Setup Wizards dashboard."""
    websites = Website.objects.all()
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'install_wordpress':
            website_id = request.POST.get('website_id')
            site = get_object_or_404(Website, id=website_id)
            from services.wizards import install_wordpress
            res = install_wordpress(site)
            if res.get('success'):
                messages.success(request, f'WordPress installed successfully for {site.domain}! Database: {res.get("db_name")}')
            else:
                messages.error(request, f'Failed to install WordPress: {res.get("error")}')
            return redirect('admin_wizards')
        elif action == 'install_laravel':
            website_id = request.POST.get('website_id')
            site = get_object_or_404(Website, id=website_id)
            from services.wizards import install_laravel
            res = install_laravel(site)
            if res.get('success'):
                messages.success(request, f'Laravel configured successfully for {site.domain}! Database: {res.get("db_name")}')
            else:
                messages.error(request, f'Failed to install Laravel: {res.get("error")}')
            return redirect('admin_wizards')

    return render(request, 'admin/wizards.html', {
        **_sidebar_context('wizards'),
        'websites': websites,
    })


def monitoring_dashboard(request):
    """Resource monitoring page with live metrics and processes."""
    processes = []
    try:
        for p in sorted(psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent']), key=lambda x: x.info['cpu_percent'] or 0, reverse=True)[:15]:
            processes.append(p.info)
    except Exception:
        pass

    return render(request, 'admin/monitoring.html', {
        **_sidebar_context('monitoring'),
        'processes': processes,
    })


def api_metrics(request):
    """JSON endpoint for live metrics polling."""
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    load = psutil.getloadavg()
    return JsonResponse({
        'cpu': round(psutil.cpu_percent(interval=0.1), 1),
        'ram_used': round(mem.used / (1024 * 1024)),
        'ram_total': round(mem.total / (1024 * 1024)),
        'ram_percent': round(mem.percent, 1),
        'disk_used': round(disk.used / (1024 ** 3), 1),
        'disk_total': round(disk.total / (1024 ** 3), 1),
        'disk_percent': round(disk.percent, 1),
        'load': round(load[0], 2),
        'load5': round(load[1], 2),
        'load15': round(load[2], 2),
    })


def _get_podman_version():
    """Get Podman version."""
    try:
        result = subprocess.run(['podman', '--version'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return result.stdout.strip().replace('podman version ', '')
    except Exception:
        pass
    return 'N/A'