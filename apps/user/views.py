"""
W3Panel v2 — User Views
End-user management interface and services.
"""
import os
import shutil
import subprocess
from pathlib import Path
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone

from packages.core.models import (
    User, Website, Package, SystemSetting, AuditLog, Notification,
    Database, Mailbox, DNSRecord, FTPAccount, CronJob, Backup
)


def _user_sidebar_context(request, active_page=''):
    user = request.panel_user
    unread_count = Notification.objects.filter(user=user, is_read=False).count() if user else 0
    return {
        'active_page': active_page,
        'unread_notifications_count': unread_count,
        'sidebar_user_items': [
            {'label': 'Tools', 'url': '/', 'icon': 'ti ti-layout-grid', 'active': 'dashboard'},
            {'label': 'Domains', 'url': '/websites/', 'icon': 'ti ti-world', 'active': 'websites'},
            {'label': 'Databases', 'url': '/databases/', 'icon': 'ti ti-database', 'active': 'databases'},
            {'label': 'File Manager', 'url': '/filemanager/', 'icon': 'ti ti-folder', 'active': 'files'},
            {'label': 'SSL / TLS', 'url': '/ssl/', 'icon': 'ti ti-lock', 'active': 'ssl'},
            {'label': 'PHP Version', 'url': '/php/', 'icon': 'ti ti-brand-php', 'active': 'php'},
            {'label': 'Zone Editor', 'url': '/dns/', 'icon': 'ti ti-dns', 'active': 'dns'},
            {'label': 'Cron Jobs', 'url': '/cron/', 'icon': 'ti ti-clock', 'active': 'cron'},
            {'label': 'Terminal', 'url': '/terminal/', 'icon': 'ti ti-terminal-2', 'active': 'terminal'},
            {'label': 'Account Settings', 'url': '/profile/', 'icon': 'ti ti-user-cog', 'active': 'profile'},
        ]
    }


def user_login(request):
    """User login page (W3Client Portal style)."""
    if request.method == 'POST':
        from packages.core.auth import authenticate_user, create_session
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        
        try:
            user, is_2fa_required = authenticate_user(username, password, request.META.get('REMOTE_ADDR', ''))
            create_session(request, user)
            return redirect('user_dashboard')
        except ValueError as e:
            return render(request, 'login.html', {'error': str(e), 'username': username, 'panel_type': 'client'})
    
    return render(request, 'login.html', {'panel_type': 'client'})


def user_logout(request):
    """User logout."""
    from packages.core.auth import destroy_session
    destroy_session(request)
    return redirect('user_login')


def user_dashboard(request):
    """Client-style user dashboard with categorized tool groups and statistics."""
    user = request.panel_user
    if not user:
        return redirect('user_login')

    websites = Website.objects.filter(owner=user, is_active=True)
    databases = Database.objects.filter(owner=user)
    mariadb_databases = databases.filter(db_type='mariadb')
    postgres_databases = databases.filter(db_type='postgresql')
    
    pkg = user.package if user.package else None
    limits = {
        'websites': pkg.websites_limit if pkg else 5,
        'databases': pkg.databases_limit if pkg else 5,
        'disk': pkg.disk_limit_mb if pkg else 10240,
        'bandwidth': pkg.bandwidth_limit_gb if pkg else 100,
    }
    
    disk_used_mb = sum(db.size_mb for db in databases) + 45.0  # approximate base
    
    websites_count = websites.count()
    databases_count = databases.count()
    mariadb_count = mariadb_databases.count()
    postgres_count = postgres_databases.count()
    
    websites_percent = min(100, (websites_count / limits['websites']) * 100) if limits['websites'] > 0 else 0
    databases_percent = min(100, (databases_count / limits['databases']) * 100) if limits['databases'] > 0 else 0
    disk_percent = min(100, (disk_used_mb / limits['disk']) * 100) if limits['disk'] > 0 else 0

    first_site = websites.first()
    primary_domain = first_site.domain if first_site else 'None'

    return render(request, 'user/dashboard.html', {
        **_user_sidebar_context(request, 'dashboard'),
        'websites': websites,
        'databases': databases,
        'mariadb_databases': mariadb_databases,
        'postgres_databases': postgres_databases,
        'websites_count': websites_count,
        'databases_count': databases_count,
        'mariadb_count': mariadb_count,
        'postgres_count': postgres_count,
        'limits': limits,
        'websites_percent': round(websites_percent, 1),
        'databases_percent': round(databases_percent, 1),
        'disk_used_mb': round(disk_used_mb, 1),
        'disk_percent': round(disk_percent, 1),
        'primary_domain': primary_domain,
    })


def user_websites(request):
    """User websites list."""
    websites = Website.objects.filter(owner=request.panel_user)
    is_nginx_installed = bool(shutil.which('nginx'))
    return render(request, 'user/websites.html', {
        **_user_sidebar_context(request, 'websites'),
        'websites': websites,
        'is_nginx_installed': is_nginx_installed,
    })


def user_website_create(request):
    """User website create."""
    is_nginx_installed = bool(shutil.which('nginx'))
    if request.method == 'POST':
        domain = request.POST.get('domain', '').strip().lower()
        framework = request.POST.get('framework', 'none')
        php_version = request.POST.get('php_version', '8.3')
        proxy_real_ip = request.POST.get('proxy_real_ip') in ('1', 'true', 'on')
        
        if domain:
            if Website.objects.filter(domain=domain).exists():
                messages.error(request, f'Domain "{domain}" is already in use.')
            else:
                user = request.panel_user
                username = user.username if user else 'guest'
                doc_root = f"/home/{username}/{domain}/public_html"
                site = Website.objects.create(
                    owner=user,
                    domain=domain,
                    doc_root=doc_root,
                    framework=framework,
                    php_version=php_version,
                    proxy_real_ip=proxy_real_ip,
                )
                DNSRecord.objects.create(domain=site, record_type='A', name='@', value='127.0.0.1')
                DNSRecord.objects.create(domain=site, record_type='CNAME', name='www', value=domain)

                # Provision vhost configuration and docroot
                from services.webserver import create_vhost
                create_vhost(site)

                messages.success(request, f'Website "{domain}" created and VirtualHost provisioned successfully!')
                return redirect('user_websites')

    return render(request, 'user/website_create.html', {
        **_user_sidebar_context(request, 'websites'),
        'is_nginx_installed': is_nginx_installed,
    })


def user_website_toggle_proxy(request, website_id):
    """Toggle Reverse Proxy Real-IP restoration for a specific website."""
    if request.method == 'POST':
        site = get_object_or_404(Website, id=website_id, owner=request.panel_user)
        site.proxy_real_ip = not site.proxy_real_ip
        site.save(update_fields=['proxy_real_ip'])

        # Re-generate vhost configuration and reload webserver
        from services.webserver import create_vhost
        create_vhost(site)

        state = "enabled (Cloudflare/Proxy mode)" if site.proxy_real_ip else "disabled (Direct traffic mode)"
        messages.success(request, f'Reverse Proxy Client IP {state} for {site.domain}.')
    return redirect('user_websites')


def user_website_delete(request, website_id):
    """User website delete."""
    if request.method == 'POST':
        site = get_object_or_404(Website, id=website_id, owner=request.panel_user)
        domain = site.domain
        from services.webserver import remove_vhost
        remove_vhost(domain)
        site.delete()
        messages.success(request, f'Website "{domain}" deleted.')
    return redirect('user_websites')


def user_website_manage(request, website_id):
    """User website detail management page: Node.js process supervisor, atomic releases, and PHP config."""
    site = get_object_or_404(Website, id=website_id, owner=request.panel_user)
    is_nginx_installed = bool(shutil.which('nginx'))

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'update_settings':
            site.port = int(request.POST.get('port', 3000) or 3000)
            site.app_entrypoint = request.POST.get('app_entrypoint', 'app.js').strip()
            site.app_env_vars = request.POST.get('app_env_vars', '').strip()
            site.php_version = request.POST.get('php_version', '8.3').strip()
            site.save()

            # Re-generate vhost with updated port/config
            from services.webserver import create_vhost
            create_vhost(site)

            # Re-configure process supervisor if nodejs
            if site.framework == 'nodejs':
                from services.process_manager import setup_app_service
                setup_app_service(site)

            messages.success(request, f'Settings for "{site.domain}" updated successfully.')
            return redirect('user_website_manage', website_id=site.id)

    # Fetch real-time process manager status and logs
    from services.process_manager import get_app_status, get_app_logs
    app_status = get_app_status(site)
    app_logs = get_app_logs(site, lines=50) if site.framework == 'nodejs' else ''

    # Fetch release deployment history
    from services.releases import list_releases
    releases = list_releases(site)

    return render(request, 'user/website_manage.html', {
        **_user_sidebar_context(request, 'websites'),
        'site': site,
        'app_status': app_status,
        'app_logs': app_logs,
        'releases': releases,
        'is_nginx_installed': is_nginx_installed,
    })


def user_website_app_action(request, website_id):
    """Control daemon process (start, stop, restart) via systemd."""
    if request.method == 'POST':
        site = get_object_or_404(Website, id=website_id, owner=request.panel_user)
        action = request.POST.get('action')
        from services.process_manager import start_app, stop_app, restart_app
        if action == 'start':
            start_app(site)
            messages.success(request, f'Application process started for {site.domain}.')
        elif action == 'stop':
            stop_app(site)
            messages.success(request, f'Application process stopped for {site.domain}.')
        elif action == 'restart':
            restart_app(site)
            messages.success(request, f'Application process restarted for {site.domain}.')
    return redirect('user_website_manage', website_id=website_id)


def user_website_deploy_release(request, website_id):
    """Deploy new atomic release."""
    if request.method == 'POST':
        site = get_object_or_404(Website, id=website_id, owner=request.panel_user)
        commit = request.POST.get('commit_version', '').strip()
        notes = request.POST.get('notes', '').strip()
        from services.releases import deploy_release
        res = deploy_release(site, commit_or_version=commit, notes=notes)
        if res.get('success'):
            messages.success(request, f'Release {res.get("release_id")} deployed atomically with zero downtime!')
        else:
            messages.error(request, f'Deployment failed: {res.get("error")}')
    return redirect('user_website_manage', website_id=website_id)


def user_website_rollback_release(request, website_id):
    """Roll back to previous release atomically."""
    if request.method == 'POST':
        site = get_object_or_404(Website, id=website_id, owner=request.panel_user)
        target_id = request.POST.get('target_release_id')
        from services.releases import rollback_release
        res = rollback_release(site, target_release_id=target_id)
        if res.get('success'):
            messages.success(request, f'Successfully rolled back to release {res.get("rolled_back_to")}!')
        else:
            messages.error(request, f'Rollback failed: {res.get("error")}')
    return redirect('user_website_manage', website_id=website_id)


def user_website_vhost(request, website_id):
    """VirtualHost (Nginx configuration) editor with safety check and rollback."""
    site = get_object_or_404(Website, id=website_id, owner=request.panel_user)
    from services.webserver import get_vhost_content, save_custom_vhost, reset_vhost_to_default

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'save_vhost':
            content = request.POST.get('vhost_content', '')
            res = save_custom_vhost(site, content)
            if res.get('success'):
                messages.success(request, f'VirtualHost configuration for {site.domain} updated and validated successfully.')
                return redirect('user_website_vhost', website_id=site.id)
            else:
                messages.error(request, f"Configuration Error: {res.get('error')}")
        elif action == 'reset_vhost':
            reset_vhost_to_default(site)
            messages.success(request, f'VirtualHost configuration for {site.domain} reset to default template.')
            return redirect('user_website_vhost', website_id=site.id)

    vhost_content = get_vhost_content(site)
    return render(request, 'user/website_vhost.html', {
        **_user_sidebar_context(request, 'websites'),
        'site': site,
        'vhost_content': vhost_content,
        'is_nginx_installed': bool(shutil.which('nginx')),
    })


def user_website_logs(request, website_id):
    """View domain error or access logs."""
    site = get_object_or_404(Website, id=website_id, owner=request.panel_user)
    from services.webserver import get_website_logs
    log_type = request.GET.get('type', 'error')
    if log_type not in ('error', 'access'):
        log_type = 'error'
    logs = get_website_logs(site, log_type=log_type, lines=150)

    return render(request, 'user/website_logs.html', {
        **_user_sidebar_context(request, 'websites'),
        'site': site,
        'log_type': log_type,
        'logs': logs,
    })



def user_databases(request):
    """Client database management for MariaDB and PostgreSQL."""
    from services.database import (
        create_database, delete_database,
        create_database_user, grant_user_privileges,
        change_user_password, delete_database_user,
        is_mariadb_installed, is_postgresql_installed,
        generate_secure_password
    )

    mariadb_ok = is_mariadb_installed()
    postgres_ok = is_postgresql_installed()
    user = request.panel_user
    username = user.username if user else 'user'

    if request.method == 'POST':
        action = request.POST.get('action', 'create_database')

        if action == 'create_database':
            raw_name = request.POST.get('name', '').strip().lower()
            db_type = request.POST.get('db_type', 'mariadb')
            if raw_name:
                full_name = f"{username}_{raw_name}" if not raw_name.startswith(f"{username}_") else raw_name
                if Database.objects.filter(owner=user, name=full_name).exists():
                    messages.error(request, f'Database "{full_name}" already exists.')
                else:
                    default_user = f"{username}_user"
                    default_pass = generate_secure_password()
                    res = create_database(full_name, default_user, default_pass, db_type=db_type)
                    Database.objects.create(owner=user, name=full_name, db_type=db_type, db_user=default_user)
                    messages.success(request, f'{db_type.capitalize()} database "{full_name}" created successfully!')
                    return redirect('user_databases')

        elif action == 'create_user':
            raw_user = request.POST.get('db_user', '').strip().lower()
            password = request.POST.get('db_password', '').strip()
            db_type = request.POST.get('db_type', 'mariadb')
            if raw_user:
                full_user = f"{username}_{raw_user}" if not raw_user.startswith(f"{username}_") else raw_user
                if not password:
                    password = generate_secure_password()
                res = create_database_user(full_user, password, db_type=db_type)
                messages.success(request, f'{db_type.capitalize()} user "{full_user}" created! (Password: {password})')
                return redirect('user_databases')

        elif action == 'grant_privileges':
            db_id = request.POST.get('database_id')
            db_user = request.POST.get('db_user', '').strip()
            db_obj = get_object_or_404(Database, id=db_id, owner=user)
            if db_user:
                grant_user_privileges(db_obj.name, db_user, db_type=db_obj.db_type)
                db_obj.db_user = db_user
                db_obj.save(update_fields=['db_user'])
                messages.success(request, f'Granted privileges on "{db_obj.name}" to user "{db_user}".')
                return redirect('user_databases')

        elif action == 'change_password':
            db_user = request.POST.get('db_user', '').strip()
            new_pass = request.POST.get('new_password', '').strip()
            db_type = request.POST.get('db_type', 'mariadb')
            if db_user and new_pass:
                change_user_password(db_user, new_pass, db_type=db_type)
                messages.success(request, f'Password for user "{db_user}" updated.')
                return redirect('user_databases')

    databases = Database.objects.filter(owner=request.panel_user)
    mariadb_list = databases.filter(db_type='mariadb')
    postgres_list = databases.filter(db_type='postgresql')

    return render(request, 'user/databases.html', {
        **_user_sidebar_context(request, 'databases'),
        'databases': databases,
        'mariadb_databases': mariadb_list,
        'postgres_databases': postgres_list,
        'is_mariadb_installed': mariadb_ok,
        'is_postgresql_installed': postgres_ok,
    })


def user_database_delete(request, db_id):
    """User database delete."""
    if request.method == 'POST':
        db = get_object_or_404(Database, id=db_id, owner=request.panel_user)
        name = db.name
        from services.database import delete_database
        delete_database(name, db.db_user, db.db_type)
        db.delete()
        messages.success(request, f'Database "{name}" deleted.')
    return redirect('user_databases')


def _format_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def _file_icon(name: str, is_dir: bool) -> str:
    if is_dir:
        low = name.lower()
        if low == 'public_html':
            return 'ti ti-world text-blue-500'
        elif low == 'mail':
            return 'ti ti-mail text-blue-600'
        elif low == 'public_ftp':
            return 'ti ti-arrows-exchange text-emerald-600'
        elif low == 'ssl':
            return 'ti ti-folder text-amber-500'
        return 'ti ti-folder-filled text-amber-500'
    ext = os.path.splitext(name)[1].lower()
    if ext in ('.php', '.phtml'):
        return 'ti ti-brand-php text-indigo-500'
    elif ext in ('.html', '.htm'):
        return 'ti ti-brand-html5 text-orange-500'
    elif ext in ('.css', '.scss', '.sass', '.less'):
        return 'ti ti-brand-css3 text-blue-500'
    elif ext in ('.js', '.ts', '.jsx', '.tsx'):
        return 'ti ti-brand-javascript text-yellow-500'
    elif ext in ('.json', '.xml', '.yaml', '.yml'):
        return 'ti ti-code text-cyan-500'
    elif ext in ('.zip', '.tar', '.gz', '.tgz', '.bz2', '.xz', '.rar', '.7z'):
        return 'ti ti-file-zip text-emerald-600'
    elif ext in ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico'):
        return 'ti ti-photo text-purple-500'
    elif ext in ('.sql', '.db', '.sqlite'):
        return 'ti ti-database text-amber-600'
    elif ext in ('.txt', '.md', '.log', '.env', '.conf', '.ini', '.htaccess'):
        return 'ti ti-file-text text-slate-500'
    elif ext in ('.py', '.sh', '.bash'):
        return 'ti ti-brand-python text-emerald-500'
    return 'ti ti-file text-slate-400'


def _file_mime_type(name: str, is_dir: bool) -> str:
    if is_dir:
        return 'httpd/unix-directory'
    ext = os.path.splitext(name)[1].lower()
    types_map = {
        '.html': 'text/html',
        '.htm': 'text/html',
        '.php': 'application/x-httpd-php',
        '.phtml': 'application/x-httpd-php',
        '.css': 'text/css',
        '.js': 'application/javascript',
        '.json': 'application/json',
        '.txt': 'text/plain',
        '.log': 'text/plain',
        '.env': 'text/plain',
        '.htaccess': 'text/plain',
        '.zip': 'application/zip',
        '.tar': 'application/x-tar',
        '.gz': 'application/gzip',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.svg': 'image/svg+xml',
        '.webp': 'image/webp',
        '.ico': 'image/x-icon',
        '.pdf': 'application/pdf',
        '.sql': 'application/sql',
        '.py': 'text/x-python',
        '.sh': 'application/x-sh',
    }
    return types_map.get(ext, 'application/octet-stream')


def _format_mtime(dt) -> str:
    now = timezone.now()
    if dt.date() == now.date():
        return dt.strftime('Today, %I:%M %p').lstrip('0')
    elif (now.date() - dt.date()).days == 1:
        return dt.strftime('Yesterday, %I:%M %p').lstrip('0')
    elif dt.year == now.year:
        return dt.strftime('%b %d, %I:%M %p')
    else:
        return dt.strftime('%b %d, %Y, %I:%M %p')


def _parse_ts(val, default_time='00:00:00'):
    if not val:
        return 0
    try:
        return int(val)
    except ValueError:
        pass
    try:
        from datetime import datetime
        dt = datetime.strptime(f"{val} {default_time}", "%Y-%m-%d %H:%M:%S")
        return int(dt.timestamp())
    except Exception:
        return 0


def user_files(request):
    """Full-featured Web File Manager for end-users."""
    import json
    from apps.filemanager import filemanager as fm
    from apps.filemanager.filemanager import _safe_path

    user = request.panel_user
    username = user.username if user else 'nobody'

    # 1. Base directory resolution (/home/{username})
    base_path = Path(f"/home/{username}")
    if not base_path.exists():
        try:
            base_path.mkdir(parents=True, exist_ok=True)
            subprocess.run(['sudo', 'chown', '-R', f'{username}:{username}', str(base_path)], timeout=5)
            subprocess.run(['sudo', 'chmod', '0755', str(base_path)], timeout=5)
        except Exception:
            base_path = Path(f"/tmp/w3panel_users/{username}")
            base_path.mkdir(parents=True, exist_ok=True)

    base_str = str(base_path.resolve())
    current_rel = request.GET.get('path', '').strip('/')
    target_dir = (base_path / current_rel).resolve()

    # Path jail check
    if not str(target_dir).startswith(base_str):
        target_dir = base_path.resolve()
        current_rel = ''

    # Validate that requested directory exists
    if current_rel and (not target_dir.exists() or not target_dir.is_dir()):
        messages.error(request, f'Directory "/{current_rel}" does not exist.')
        return redirect('/filemanager/')

    # Handle direct file download
    if request.GET.get('action') == 'download' and request.GET.get('file'):
        file_rel = request.GET.get('file', '').strip('/')
        return fm.download_file(base_str, file_rel)

    # Handle recursive search API action (JSON response for live search)
    if request.GET.get('action') == 'search':
        q = request.GET.get('q', '').strip()
        scope = request.GET.get('scope', 'all')
        time_filter = request.GET.get('time_filter', 'all').strip()
        mtime_from = _parse_ts(request.GET.get('mtime_from'), '00:00:00')
        mtime_to = _parse_ts(request.GET.get('mtime_to'), '23:59:59')
        type_filter = request.GET.get('type_filter', 'all').strip()
        size_filter = request.GET.get('size_filter', 'all').strip()
        try:
            size_min = int(request.GET.get('size_min', 0))
        except ValueError:
            size_min = 0
        try:
            size_max = int(request.GET.get('size_max', 0))
        except ValueError:
            size_max = 0

        if scope == 'current':
            search_rel = current_rel
        elif scope == 'public_html':
            search_rel = 'public_html'
        else:
            search_rel = ''

        search_res = fm.search_files(base_str, search_rel, q,
                                     time_filter=time_filter, mtime_from=mtime_from, mtime_to=mtime_to,
                                     type_filter=type_filter, size_filter=size_filter,
                                     size_min=size_min, size_max=size_max)
        res_data = json.loads(search_res.content) if hasattr(search_res, 'content') else {}
        if res_data.get('status') == 1:
            formatted_results = []
            for it in res_data.get('results', []):
                name = it['name']
                is_dir = it['is_dir']
                size = it['size']
                perms = it['perms']
                mtime_ts = it['mtime_ts']
                dt = timezone.datetime.fromtimestamp(mtime_ts) if mtime_ts else timezone.now()
                ext = os.path.splitext(name)[1].lower()
                formatted_results.append({
                    'name': name,
                    'rel_path': it['rel_path'],
                    'is_dir': is_dir,
                    'is_archive': ext in ('.zip', '.tar', '.gz', '.tgz', '.bz2', '.xz', '.rar', '.7z'),
                    'is_image': ext in ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico'),
                    'is_code': ext in ('.php', '.phtml', '.html', '.htm', '.css', '.scss', '.js', '.ts', '.json', '.sql', '.py', '.sh', '.env', '.htaccess', '.conf', '.ini', '.xml', '.txt', '.md', '.yaml', '.yml'),
                    'size': size,
                    'size_human': _format_size(size) if not is_dir else '4 KB',
                    'file_type': _file_mime_type(name, is_dir),
                    'perms': perms,
                    'modified': _format_mtime(dt),
                    'modified_ts': mtime_ts,
                    'icon': _file_icon(name, is_dir),
                })
            return JsonResponse({'status': 1, 'results': formatted_results, 'count': len(formatted_results)})
        return JsonResponse({'status': 0, 'error': res_data.get('error', 'Search failed.')})

    # Handle POST actions
    if request.method == 'POST':
        action = request.POST.get('action')
        redirect_url = f"/filemanager/?path={current_rel}"

        if action == 'upload':
            files = request.FILES.getlist('files')
            count = 0
            for f in files:
                res = fm.upload_file(base_str, current_rel, f)
                if hasattr(res, 'status_code') and res.status_code == 200:
                    count += 1
            if count > 0:
                messages.success(request, f'Uploaded {count} file(s) successfully.')
            else:
                messages.error(request, 'No files were uploaded.')
            return redirect(redirect_url)

        elif action == 'create_file':
            filename = request.POST.get('filename', '').strip()
            if filename:
                rel = f"{current_rel}/{filename}".strip('/')
                res = fm.create_file(base_str, rel)
                res_data = json.loads(res.content) if hasattr(res, 'content') else {}
                if res_data.get('status') == 1:
                    messages.success(request, f'File "{filename}" created.')
                else:
                    messages.error(request, res_data.get('error', f'Failed to create "{filename}".'))
            return redirect(redirect_url)

        elif action == 'create_dir':
            dirname = request.POST.get('dirname', '').strip()
            if dirname:
                rel = f"{current_rel}/{dirname}".strip('/')
                res = fm.create_folder(base_str, rel)
                res_data = json.loads(res.content) if hasattr(res, 'content') else {}
                if res_data.get('status') == 1:
                    messages.success(request, f'Directory "{dirname}" created.')
                else:
                    messages.error(request, res_data.get('error', f'Failed to create directory "{dirname}".'))
            return redirect(redirect_url)

        elif action == 'save_file':
            file_rel = request.POST.get('file_path', '').strip('/')
            content = request.POST.get('content', '')
            res = fm.write_file(base_str, file_rel, content)
            res_data = json.loads(res.content) if hasattr(res, 'content') else {}
            if res_data.get('status') == 1:
                messages.success(request, f'File "{os.path.basename(file_rel)}" saved successfully.')
            else:
                messages.error(request, res_data.get('error', 'Failed to save file.'))
            parent_dir = os.path.dirname(file_rel)
            return redirect(f"/filemanager/?path={parent_dir}")

        elif action == 'delete':
            items = request.POST.getlist('items')
            if not items and request.POST.get('item_path'):
                items = [request.POST.get('item_path')]
            skip_trash = request.POST.get('skip_trash') in ('1', 'true', 'on')
            if items:
                clean_items = [it.strip('/') for it in items if it.strip('/')]
                if current_rel == '.trash' or skip_trash:
                    res = fm.delete_permanent(base_str, '', clean_items)
                    res_data = json.loads(res.content) if hasattr(res, 'content') else {}
                    if res_data.get('status') == 1:
                        messages.success(request, f'Permanently deleted {len(clean_items)} item(s).')
                    else:
                        messages.error(request, res_data.get('error', 'Failed to delete item(s).'))
                else:
                    res = fm.trash_items(base_str, '', clean_items)
                    res_data = json.loads(res.content) if hasattr(res, 'content') else {}
                    if res_data.get('status') == 1:
                        messages.success(request, f'Moved {len(clean_items)} item(s) to Trash.')
                    else:
                        messages.error(request, res_data.get('error', 'Failed to move item(s) to Trash.'))
            return redirect(redirect_url)

        elif action == 'restore':
            items = request.POST.getlist('items')
            if not items and request.POST.get('item_path'):
                items = [request.POST.get('item_path')]
            if items:
                clean_items = [it.strip('/') for it in items if it.strip('/')]
                res = fm.restore_trash(base_str, clean_items)
                res_data = json.loads(res.content) if hasattr(res, 'content') else {}
                if res_data.get('status') == 1:
                    restored_count = res_data.get('restored_count', len(clean_items))
                    messages.success(request, f'Successfully restored {restored_count} item(s) to original location.')
                else:
                    messages.error(request, res_data.get('error', 'Failed to restore item(s).'))
            return redirect(redirect_url)

        elif action == 'empty_trash':
            res = fm.empty_trash(base_str)
            res_data = json.loads(res.content) if hasattr(res, 'content') else {}
            if res_data.get('status') == 1:
                messages.success(request, 'Trash has been emptied successfully.')
            else:
                messages.error(request, res_data.get('error', 'Failed to empty Trash.'))
            return redirect(redirect_url)

        elif action == 'rename':
            old_name = request.POST.get('old_name', '').strip()
            new_name = request.POST.get('new_name', '').strip()
            if old_name and new_name:
                if '/' in old_name:
                    item_dir = os.path.dirname(old_name)
                    old_base = os.path.basename(old_name)
                    res = fm.rename(base_str, item_dir, old_base, new_name)
                else:
                    res = fm.rename(base_str, current_rel, old_name, new_name)
                res_data = json.loads(res.content) if hasattr(res, 'content') else {}
                if res_data.get('status') == 1:
                    messages.success(request, f'Renamed "{os.path.basename(old_name)}" to "{new_name}".')
                else:
                    messages.error(request, res_data.get('error', 'Failed to rename item.'))
            return redirect(redirect_url)

        elif action == 'chmod':
            item_rel = request.POST.get('item_path', '').strip('/')
            mode = request.POST.get('mode', '0755').strip()
            recursive = request.POST.get('recursive') in ('1', 'true', 'on')
            res = fm.change_permissions(base_str, item_rel, mode, recursive)
            res_data = json.loads(res.content) if hasattr(res, 'content') else {}
            if res_data.get('status') == 1:
                messages.success(request, f'Permissions for "{os.path.basename(item_rel)}" changed to {mode}.')
            else:
                messages.error(request, res_data.get('error', 'Failed to change permissions.'))
            return redirect(redirect_url)

        elif action == 'fix_permissions':
            target_rel = request.POST.get('target_path', current_rel).strip('/')
            res = fm.fix_permissions(base_str, target_rel, username=username)
            res_data = json.loads(res.content) if hasattr(res, 'content') else {}
            if res_data.get('status') == 1:
                target_label = os.path.basename(target_rel) if target_rel else f"home ({username})"
                messages.success(request, f'Permissions recursively normalized for "{target_label}"! Directories set to 0755, Files set to 0644, Owner set to {username}.')
            else:
                messages.error(request, res_data.get('error', 'Failed to fix permissions.'))
            return redirect(redirect_url)

        elif action == 'compress':
            items = request.POST.getlist('items')
            if not items and request.POST.get('item_path'):
                items = [request.POST.get('item_path')]
            archive_name = request.POST.get('archive_name', 'archive').strip()
            dest_dir = request.POST.get('dest_dir', current_rel).strip('/')
            fmt = request.POST.get('format', 'zip')
            if items and archive_name:
                clean_items = [it.strip('/') for it in items if it.strip('/')]
                res = fm.compress_items(base_str, '', clean_items, archive_name, fmt, dest_dir=dest_dir)
                res_data = json.loads(res.content) if hasattr(res, 'content') else {}
                if res_data.get('status') == 1:
                    messages.success(request, f'Archive "{res_data.get("archive")}" created successfully.')
                else:
                    messages.error(request, res_data.get('error', 'Compression failed.'))
            return redirect(redirect_url)

        elif action == 'extract':
            archive_rel = request.POST.get('archive_path', '').strip('/')
            dest_rel = request.POST.get('dest_dir', current_rel).strip('/')
            if archive_rel:
                res = fm.extract_archive(base_str, archive_rel, dest_rel)
                res_data = json.loads(res.content) if hasattr(res, 'content') else {}
                if res_data.get('status') == 1:
                    messages.success(request, f'Archive "{os.path.basename(archive_rel)}" extracted successfully.')
                else:
                    messages.error(request, res_data.get('error', 'Archive extraction failed.'))
            return redirect(redirect_url)

        elif action == 'copy':
            items = request.POST.getlist('items')
            if not items and request.POST.get('item_path'):
                items = [request.POST.get('item_path')]
            dst_dir = request.POST.get('dest_dir', '').strip('/')
            if items:
                clean_items = [it.strip('/') for it in items if it.strip('/')]
                res = fm.copy_items(base_str, '', clean_items, dst_dir)
                res_data = json.loads(res.content) if hasattr(res, 'content') else {}
                if res_data.get('status') == 1:
                    messages.success(request, f'Copied {len(clean_items)} item(s) to "{dst_dir or "/"}".')
                else:
                    messages.error(request, res_data.get('error', 'Copy operation failed.'))
            return redirect(redirect_url)

        elif action == 'move':
            items = request.POST.getlist('items')
            if not items and request.POST.get('item_path'):
                items = [request.POST.get('item_path')]
            dst_dir = request.POST.get('dest_dir', '').strip('/')
            if items:
                clean_items = [it.strip('/') for it in items if it.strip('/')]
                res = fm.move_items(base_str, '', clean_items, dst_dir)
                res_data = json.loads(res.content) if hasattr(res, 'content') else {}
                if res_data.get('status') == 1:
                    messages.success(request, f'Moved {len(clean_items)} item(s) to "{dst_dir or "/"}".')
                else:
                    messages.error(request, res_data.get('error', 'Move operation failed.'))
            return redirect(redirect_url)

    # In-browser Code Editing mode
    edit_rel = request.GET.get('edit', '').strip('/')
    editing_file = None
    file_content = ""
    if edit_rel:
        edit_target = _safe_path(base_str, edit_rel)
        if edit_target and os.path.isfile(edit_target):
            editing_file = edit_rel
            try:
                if os.path.getsize(edit_target) > 5 * 1024 * 1024:
                    file_content = "// File exceeds 5 MB limit. Please edit or download locally."
                else:
                    with open(edit_target, 'r', encoding='utf-8', errors='replace') as f:
                        file_content = f.read()
            except Exception:
                file_content = "// Binary or unreadable file."

    # List items with metadata (or recursive search results)
    items = []
    search_query = request.GET.get('search', '').strip()
    search_scope = request.GET.get('scope', 'all')
    time_filter = request.GET.get('time_filter', 'all').strip()
    type_filter = request.GET.get('type_filter', 'all').strip()
    size_filter = request.GET.get('size_filter', 'all').strip()
    mtime_from = _parse_ts(request.GET.get('mtime_from'), '00:00:00')
    mtime_to = _parse_ts(request.GET.get('mtime_to'), '23:59:59')
    try:
        size_min = int(request.GET.get('size_min', 0))
    except ValueError:
        size_min = 0
    try:
        size_max = int(request.GET.get('size_max', 0))
    except ValueError:
        size_max = 0

    has_search = bool(search_query) or (time_filter and time_filter != 'all') or (type_filter and type_filter != 'all') or (size_filter and size_filter != 'all')
    try:
        if has_search:
            if search_scope == 'current':
                search_rel = current_rel
            elif search_scope == 'public_html':
                search_rel = 'public_html'
            else:
                search_rel = ''
            search_res = fm.search_files(base_str, search_rel, search_query,
                                         time_filter=time_filter, mtime_from=mtime_from, mtime_to=mtime_to,
                                         type_filter=type_filter, size_filter=size_filter,
                                         size_min=size_min, size_max=size_max)
            res_data = json.loads(search_res.content) if hasattr(search_res, 'content') else {}
            if res_data.get('status') == 1:
                for it in res_data.get('results', []):
                    name = it['name']
                    is_dir = it['is_dir']
                    size = it['size']
                    perms = it['perms']
                    mtime_ts = it['mtime_ts']
                    dt = timezone.datetime.fromtimestamp(mtime_ts) if mtime_ts else timezone.now()
                    ext = os.path.splitext(name)[1].lower()
                    items.append({
                        'name': name,
                        'is_dir': is_dir,
                        'is_archive': ext in ('.zip', '.tar', '.gz', '.tgz', '.bz2', '.xz', '.rar', '.7z'),
                        'is_image': ext in ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico'),
                        'is_code': ext in ('.php', '.phtml', '.html', '.htm', '.css', '.scss', '.js', '.ts', '.json', '.sql', '.py', '.sh', '.env', '.htaccess', '.conf', '.ini', '.xml', '.txt', '.md', '.yaml', '.yml'),
                        'size': size,
                        'size_human': _format_size(size) if not is_dir else '4 KB',
                        'file_type': _file_mime_type(name, is_dir),
                        'perms': perms,
                        'modified': _format_mtime(dt),
                        'modified_ts': mtime_ts,
                        'icon': _file_icon(name, is_dir),
                        'rel_path': it['rel_path'],
                    })
        elif os.path.exists(target_dir):
            trash_info = fm._load_trash_info(base_str) if current_rel == '.trash' else {}
            for entry in os.scandir(target_dir):
                name = entry.name
                if name == '.trash_info.json':
                    continue
                if current_rel != '.trash' and name.startswith('.') and name not in ('.htaccess', '.env', '.trash'):
                    continue
                is_dir = entry.is_dir()
                size = 0
                perms = "0755" if is_dir else "0644"
                mtime_str = "-"
                mtime_ts = 0
                try:
                    st = entry.stat()
                    size = st.st_size if not is_dir else 4096
                    perms = oct(st.st_mode)[-4:] if len(oct(st.st_mode)) >= 4 else oct(st.st_mode)[-3:].zfill(4)
                    mtime_ts = int(st.st_mtime)
                    dt = timezone.datetime.fromtimestamp(st.st_mtime)
                    mtime_str = _format_mtime(dt)
                except Exception:
                    pass

                ext = os.path.splitext(name)[1].lower()
                is_archive = ext in ('.zip', '.tar', '.gz', '.tgz', '.bz2', '.xz', '.rar', '.7z')
                is_image = ext in ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico')
                is_code = ext in ('.php', '.phtml', '.html', '.htm', '.css', '.scss', '.js', '.ts', '.json', '.sql', '.py', '.sh', '.env', '.htaccess', '.conf', '.ini', '.xml', '.txt', '.md', '.yaml', '.yml')

                orig_info = trash_info.get(name, {}) if isinstance(trash_info.get(name), dict) else {}
                orig_path = orig_info.get('original_path', name) if orig_info else (trash_info.get(name) if isinstance(trash_info.get(name), str) else '')
                deleted_at = orig_info.get('deleted_at', '')

                items.append({
                    'name': name,
                    'is_dir': is_dir,
                    'is_archive': is_archive,
                    'is_image': is_image,
                    'is_code': is_code,
                    'size': size,
                    'size_human': _format_size(size) if not is_dir else '4 KB',
                    'file_type': _file_mime_type(name, is_dir),
                    'perms': perms,
                    'modified': mtime_str,
                    'modified_ts': mtime_ts,
                    'icon': _file_icon(name, is_dir),
                    'rel_path': f"{current_rel}/{name}".strip('/'),
                    'original_path': orig_path,
                    'deleted_at': deleted_at,
                })
    except Exception as e:
        logger.warning(f"File manager scandir error: {e}")

    # Build folder directory tree for Left Pane
    folder_tree = []
    try:
        if os.path.exists(base_str):
            for entry in os.scandir(base_str):
                if entry.is_dir():
                    name = entry.name
                    if name.startswith('.') and name not in ('.trash',):
                        continue
                    rel = name
                    subdirs = []
                    try:
                        for sub in os.scandir(entry.path):
                            if sub.is_dir() and not sub.name.startswith('.'):
                                subdirs.append({
                                    'name': sub.name,
                                    'path': f"{rel}/{sub.name}",
                                    'is_active': (current_rel == f"{rel}/{sub.name}" or current_rel.startswith(f"{rel}/{sub.name}/")),
                                })
                        subdirs.sort(key=lambda s: s['name'].lower())
                    except Exception:
                        pass
                    folder_tree.append({
                        'name': name,
                        'path': rel,
                        'subdirs': subdirs,
                        'is_active': (current_rel == rel or current_rel.startswith(f"{rel}/")),
                    })
            folder_tree.sort(key=lambda d: (d['name'] != 'public_html', d['name'].lower()))
    except Exception as e:
        logger.warning(f"Error building folder tree: {e}")

    # Breadcrumbs
    crumbs = [{'name': f"~/{username}", 'path': ''}]
    if current_rel:
        accum = []
        for segment in current_rel.split('/'):
            if segment:
                accum.append(segment)
    parent_path = ''
    if current_rel:
        parent_parts = current_rel.split('/')[:-1]
        parent_path = '/'.join(parent_parts)

    # Gather all existing directories under user's home for tab autocompletion & validation
    all_directories = ['']
    try:
        if os.path.exists(base_str):
            for root, dirs, _ in os.walk(base_str):
                dirs[:] = [d for d in dirs if not d.startswith('.') or d in ('.trash',)]
                rel_root = os.path.relpath(root, base_str)
                if rel_root != '.':
                    all_directories.append(rel_root)
                depth = rel_root.count(os.sep)
                if depth >= 5:
                    dirs.clear()
    except Exception as e:
        logger.warning(f"Error building directory list: {e}")
    all_directories = sorted(list(set(all_directories)))

    items_sorted = sorted(items, key=lambda x: (not x['is_dir'], x['name'].lower()))

    return render(request, 'user/files.html', {
        **_user_sidebar_context(request, 'files'),
        'current_path': current_rel,
        'parent_path': parent_path,
        'breadcrumbs': crumbs,
        'items': items_sorted,
        'items_json': json.dumps(items_sorted),
        'folder_tree': folder_tree,
        'valid_directories_json': json.dumps(all_directories),
        'search_query': search_query,
        'search_scope': search_scope,
        'time_filter': time_filter,
        'type_filter': type_filter,
        'size_filter': size_filter,
        'mtime_from': request.GET.get('mtime_from', ''),
        'mtime_to': request.GET.get('mtime_to', ''),
        'size_min': request.GET.get('size_min', ''),
        'size_max': request.GET.get('size_max', ''),
        'editing_file': editing_file,
        'file_content': file_content,
        'base_path_display': f"/home/{username}" + (f"/{current_rel}" if current_rel else ""),
    })


def user_ftp(request):
    """User FTP accounts."""
    user = request.panel_user
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        directory = request.POST.get('directory', '/').strip()
        
        if username:
            full_user = f"{user.username}_{username}"
            if FTPAccount.objects.filter(username=full_user).exists():
                messages.error(request, f'FTP User "{full_user}" already exists.')
            else:
                from services.database import generate_secure_password
                pwd = generate_secure_password(12)
                from services.ftp import create_ftp_user
                create_ftp_user(full_user, pwd, directory)

                FTPAccount.objects.create(owner=user, username=full_user, directory=directory)
                messages.success(request, f'FTP User "{full_user}" created successfully (Password: {pwd})')
                return redirect('user_ftp')

    ftp_accounts = FTPAccount.objects.filter(owner=user)
    return render(request, 'user/ftp.html', {
        **_user_sidebar_context(request, 'ftp'),
        'ftp_accounts': ftp_accounts,
    })


def user_ftp_delete(request, ftp_id):
    """User FTP account delete."""
    if request.method == 'POST':
        ftp = get_object_or_404(FTPAccount, id=ftp_id, owner=request.panel_user)
        username = ftp.username
        from services.ftp import delete_ftp_user
        delete_ftp_user(username)
        ftp.delete()
        messages.success(request, f'FTP user "{username}" deleted.')
    return redirect('user_ftp')


def user_ssl(request):
    """User SSL certificates manager."""
    user = request.panel_user
    websites = Website.objects.filter(owner=user)
    
    if request.method == 'POST':
        website_id = request.POST.get('website_id')
        site = get_object_or_404(Website, id=website_id, owner=user)
        from services.ssl import issue_certificate
        res = issue_certificate(site, email=user.email if user else '')
        if res.get('success'):
            messages.success(request, f'SSL certificate ({res.get("type", "TLS")}) activated successfully for {site.domain}!')
        else:
            messages.error(request, f'Failed to issue SSL: {res.get("error", "Unknown error")}')
        return redirect('user_ssl')

    return render(request, 'user/ssl.html', {
        **_user_sidebar_context(request, 'ssl'),
        'websites': websites,
    })


def user_backups(request):
    """User backups manager."""
    user = request.panel_user
    if request.method == 'POST':
        from services.backup import create_user_backup
        res = create_user_backup(user)
        if res.get('success'):
            Backup.objects.create(
                owner=user,
                name=res.get('name'),
                size_bytes=int(res.get('size_mb', 1) * 1024 * 1024),
                backup_type='full',
                status='completed'
            )
            messages.success(request, f'Backup "{res.get("name")}" generated successfully.')
        else:
            messages.error(request, f'Failed to create backup: {res.get("error")}')
        return redirect('user_backups')

    backups = Backup.objects.filter(owner=user)
    return render(request, 'user/backups.html', {
        **_user_sidebar_context(request, 'backups'),
        'backups': backups,
    })


def user_backup_delete(request, backup_id):
    """User backup delete."""
    if request.method == 'POST':
        b = get_object_or_404(Backup, id=backup_id, owner=request.panel_user)
        name = b.name
        from services.backup import delete_user_backup
        user = request.panel_user
        delete_user_backup(user.username if user else 'user', name)
        b.delete()
        messages.success(request, f'Backup "{name}" deleted.')
    return redirect('user_backups')


def user_php(request):
    """Client MultiPHP INI & Version Editor."""
    user = request.panel_user
    websites = Website.objects.filter(owner=user)
    selected_domain_id = request.GET.get('domain_id')
    selected_domain = None
    if selected_domain_id:
        selected_domain = websites.filter(id=selected_domain_id).first()
    elif websites.exists():
        selected_domain = websites.first()

    php_ini_values = {
        'memory_limit': '256M',
        'upload_max_filesize': '64M',
        'post_max_size': '64M',
        'max_execution_time': '120',
        'display_errors': 'Off',
    }

    if selected_domain and selected_domain.doc_root:
        user_ini = Path(selected_domain.doc_root) / '.user.ini'
        if user_ini.exists():
            try:
                for line in user_ini.read_text().splitlines():
                    if '=' in line and not line.strip().startswith(';'):
                        parts = line.split('=', 1)
                        k = parts[0].strip()
                        if k in php_ini_values:
                            php_ini_values[k] = parts[1].strip()
            except Exception:
                pass

    if request.method == 'POST' and selected_domain:
        mem = request.POST.get('memory_limit', '256M').strip()
        upload = request.POST.get('upload_max_filesize', '64M').strip()
        post = request.POST.get('post_max_size', '64M').strip()
        exec_time = request.POST.get('max_execution_time', '120').strip()
        errors = request.POST.get('display_errors', 'Off').strip()
        php_ver = request.POST.get('php_version', selected_domain.php_version)

        # Update PHP version on website
        if php_ver and php_ver != selected_domain.php_version:
            selected_domain.php_version = php_ver
            selected_domain.save(update_fields=['php_version'])
            from services.webserver import create_vhost
            create_vhost(selected_domain)

        # Write .user.ini
        if selected_domain.doc_root:
            try:
                doc_root = Path(selected_domain.doc_root)
                doc_root.mkdir(parents=True, exist_ok=True)
                ini_content = f"""; W3Panel MultiPHP INI Overrides for {selected_domain.domain}
memory_limit = {mem}
upload_max_filesize = {upload}
post_max_size = {post}
max_execution_time = {exec_time}
display_errors = {errors}
"""
                (doc_root / '.user.ini').write_text(ini_content)
            except Exception:
                pass

        messages.success(request, f'PHP configuration for {selected_domain.domain} updated successfully.')
        return redirect(f'/user/php/?domain_id={selected_domain.id}')

    return render(request, 'user/php.html', {
        **_user_sidebar_context(request, 'php'),
        'websites': websites,
        'selected_domain': selected_domain,
        'php_ini': php_ini_values,
    })


def user_cron(request):
    """Client Cron Jobs manager with presets and 5-field crontab syntax."""
    user = request.panel_user
    if request.method == 'POST':
        schedule = request.POST.get('schedule', '').strip()
        minute = request.POST.get('minute', '').strip()
        hour = request.POST.get('hour', '').strip()
        day = request.POST.get('day', '').strip()
        month = request.POST.get('month', '').strip()
        weekday = request.POST.get('weekday', '').strip()

        if minute and hour and day and month and weekday:
            schedule = f"{minute} {hour} {day} {month} {weekday}"
        elif not schedule:
            schedule = '0 0 * * *'

        command = request.POST.get('command', '').strip()
        description = request.POST.get('description', '').strip()
        
        if command:
            CronJob.objects.create(owner=user, schedule=schedule, command=command, description=description)
            from services.cron import sync_cron_jobs
            sync_cron_jobs(user.username if user else 'user', CronJob.objects.filter(owner=user))
            messages.success(request, 'Cron job created and system crontab updated successfully.')
            return redirect('user_cron')

    cron_jobs = CronJob.objects.filter(owner=user)
    return render(request, 'user/cron.html', {
        **_user_sidebar_context(request, 'cron'),
        'cron_jobs': cron_jobs,
    })


def user_cron_toggle(request, cron_id):
    """Toggle cron job active state (pause/resume)."""
    if request.method == 'POST':
        cj = get_object_or_404(CronJob, id=cron_id, owner=request.panel_user)
        cj.is_active = not cj.is_active
        cj.save(update_fields=['is_active'])
        from services.cron import sync_cron_jobs
        user = request.panel_user
        sync_cron_jobs(user.username if user else 'user', CronJob.objects.filter(owner=user))
        status = 'activated' if cj.is_active else 'paused'
        messages.success(request, f'Cron job {status}.')
    return redirect('user_cron')


def user_cron_delete(request, cron_id):
    """User cron job delete."""
    if request.method == 'POST':
        cj = get_object_or_404(CronJob, id=cron_id, owner=request.panel_user)
        cj.delete()
        from services.cron import sync_cron_jobs
        user = request.panel_user
        sync_cron_jobs(user.username if user else 'user', CronJob.objects.filter(owner=user))
        messages.success(request, 'Cron job deleted.')
    return redirect('user_cron')


def user_dns(request):
    """Client DNS Zone Editor for domain records."""
    user = request.panel_user
    websites = Website.objects.filter(owner=user)
    selected_domain_id = request.GET.get('domain_id')
    selected_domain = None
    if selected_domain_id:
        selected_domain = websites.filter(id=selected_domain_id).first()
    elif websites.exists():
        selected_domain = websites.first()

    records = selected_domain.dns_records.all() if selected_domain else []

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_record' and selected_domain:
            rec_type = request.POST.get('record_type', 'A')
            name = request.POST.get('name', '@').strip()
            value = request.POST.get('value', '').strip()
            ttl = int(request.POST.get('ttl', 3600) or 3600)
            priority = request.POST.get('priority')
            priority = int(priority) if priority and priority.isdigit() else None
            
            if name and value:
                DNSRecord.objects.create(
                    domain=selected_domain,
                    record_type=rec_type,
                    name=name,
                    value=value,
                    ttl=ttl,
                    priority=priority
                )
                messages.success(request, f'DNS {rec_type} record for "{name}" added successfully.')
                return redirect(f'/user/dns/?domain_id={selected_domain.id}')

    return render(request, 'user/dns.html', {
        **_user_sidebar_context(request, 'dns'),
        'websites': websites,
        'selected_domain': selected_domain,
        'records': records,
    })


def user_dns_delete(request, record_id):
    """Delete a DNS record."""
    if request.method == 'POST':
        rec = get_object_or_404(DNSRecord, id=record_id, domain__owner=request.panel_user)
        dom_id = rec.domain.id
        rec.delete()
        messages.success(request, 'DNS record deleted successfully.')
        return redirect(f'/user/dns/?domain_id={dom_id}')
    return redirect('user_dns')


def user_profile(request):
    """User profile and account settings."""
    user = request.panel_user
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        
        if email:
            user.email = email
        if password:
            user.set_password(password)
        user.save()
        messages.success(request, 'Profile updated successfully.')
        return redirect('user_profile')

    return render(request, 'user/profile.html', {
        **_user_sidebar_context(request, 'profile'),
        'user_obj': user,
    })


def user_sso(request):
    """Single Sign-On endpoint for 1-click admin impersonation."""
    token_str = request.GET.get('token', '').strip()
    if not token_str:
        messages.error(request, 'Missing authentication token.')
        return redirect('user_login')

    from packages.core.models import LoginToken
    from packages.core.auth import create_session

    token_obj = LoginToken.objects.filter(token=token_str).select_related('user', 'created_by').first()
    if not token_obj or not token_obj.is_valid():
        messages.error(request, 'This single sign-on link is invalid or has expired.')
        return redirect('user_login')

    # Consume one-time token
    token_obj.is_used = True
    token_obj.save(update_fields=['is_used'])

    # Authenticate user session (fresh client session)
    user = token_obj.user
    request.session.flush()
    create_session(request, user)
    admin_name = token_obj.created_by.username if token_obj.created_by else 'Administrator'
    request.session['impersonated_by'] = admin_name
    return redirect('user_dashboard')


def user_terminal(request):
    """Web Terminal interface for tenant user."""
    user = request.panel_user
    server_ip = request.META.get('SERVER_NAME', '127.0.0.1')
    return render(request, 'user/terminal.html', {
        **_user_sidebar_context(request, 'terminal'),
        'shell_enabled': getattr(user, 'shell_enabled', False),
        'server_ip': server_ip,
    })


def user_terminal_exec(request):
    """Execute command in tenant sandbox for Web Terminal."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    user = request.panel_user
    if not user:
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    if not getattr(user, 'shell_enabled', False):
        return JsonResponse({'error': 'Terminal/SSH access is not enabled for your account.'}, status=403)

    cmd = request.POST.get('command', '').strip()
    if not cmd:
        return JsonResponse({'stdout': '', 'stderr': '', 'returncode': 0})

    # Dangerous blacklist protection
    blocked = ['rm -rf /', 'mkfs', ':(){ :|:& };:', 'dd if=']
    if any(b in cmd for b in blocked):
        return JsonResponse({'stderr': 'Command rejected by security filter.', 'returncode': 1})

    user_home = Path(f"/home/{user.username}")
    if not user_home.exists():
        user_home = Path(f"/tmp/w3panel_test/users/{user.username}")
        user_home.mkdir(parents=True, exist_ok=True)

    try:
        import pwd
        from services.webserver.manager import _has_sudo
        
        posix_user_exists = False
        try:
            pwd.getpwnam(user.username)
            posix_user_exists = True
        except KeyError:
            posix_user_exists = False

        if _has_sudo() and posix_user_exists:
            run_cmd = ['sudo', '-n', '-u', user.username, 'bash', '-c', f"cd '{user_home}' && {cmd}"]
        else:
            run_cmd = ['bash', '-c', f"cd '{user_home}' && {cmd}"]

        res = subprocess.run(run_cmd, capture_output=True, text=True, timeout=15)
        return JsonResponse({
            'stdout': res.stdout,
            'stderr': res.stderr,
            'returncode': res.returncode,
            'cwd': f"~/{Path(user_home).name}",
        })
    except subprocess.TimeoutExpired:
        return JsonResponse({'stderr': 'Command execution timed out after 15 seconds.', 'returncode': 124})
    except Exception as e:
        return JsonResponse({'stderr': str(e), 'returncode': 1})