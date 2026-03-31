"""Website management — admin views."""
import json
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect

from lkypanel.models import Website, User, Notification
from lkypanel.admin_views.decorators import admin_required
from lkypanel.audit import log_action
from lkypanel.services import ols

logger = logging.getLogger(__name__)


@admin_required
@require_http_methods(['GET'])
def list_websites(request):
    from django.shortcuts import render
    sites = Website.objects.select_related('owner').all().order_by('-created_at')
    users = User.objects.all().order_by('username')
    return render(request, 'admin/websites.html', {
        'websites': sites,
        'users': users,
        'active_page': 'websites',
        'panel_user': request.panel_user
    })


@admin_required
@require_http_methods(['GET'])
def website_detail(request, site_id):
    from django.shortcuts import render, get_object_or_404
    from lkypanel.models import FTPAccount, Database, GitRepo
    from lkypanel.services.packages import is_plugin_installed
    site = get_object_or_404(Website, pk=site_id)
    return render(request, 'admin/website_detail.html', {
        'site': site,
        'ftp_count': FTPAccount.objects.filter(website=site).count(),
        'db_count': Database.objects.filter(website=site).count(),
        'git_count': GitRepo.objects.filter(website=site).count(),
        'mariadb_installed': is_plugin_installed('mariadb'),
        'pureftpd_installed': is_plugin_installed('pureftpd'),
        'active_page': 'websites',
        'panel_user': request.panel_user
    })


@admin_required
@require_http_methods(['GET'])
def admin_dashboard(request):
    from django.shortcuts import render
    import json, time, random
    import psutil
    from django.db import connection
    from django.db.models import Count
    from lkypanel.models import Database, AuditLog, BackupJob

    def _table_exists(name):
        return name in connection.introspection.table_names()

    sites    = Website.objects.select_related('owner').all().order_by('-created_at')
    users_qs = User.objects.all()

    # ── System stats ──────────────────────────────────────────────────────
    cpu  = psutil.cpu_percent(interval=0.3)
    ram  = psutil.virtual_memory()
    disk = psutil.disk_usage('/')

    circumference = 251.2
    def dashoffset(pct):
        return round(circumference - (pct / 100) * circumference, 2)

    def fmt_bytes(b):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if b < 1024:
                return f'{b:.1f} {unit}'
            b /= 1024
        return f'{b:.1f} PB'

    uptime_secs = int(time.time() - psutil.boot_time())
    days, rem   = divmod(uptime_secs, 86400)
    hours, rem  = divmod(rem, 3600)
    uptime_str  = f'{days}d {hours}h' if days else f'{hours}h {rem//60}m'

    load     = psutil.getloadavg()
    load_str = f'{load[0]:.2f}, {load[1]:.2f}, {load[2]:.2f}'

    cpu_history = [round(max(0, min(100, cpu + random.uniform(-8, 8))), 1) for _ in range(9)] + [cpu]
    ram_history = [round(max(0, min(100, ram.percent + random.uniform(-5, 5))), 1) for _ in range(9)] + [ram.percent]

    # ── PHP breakdown ─────────────────────────────────────────────────────
    php_data   = Website.objects.values('php_version').annotate(count=Count('id'))
    php_labels = [d['php_version'] for d in php_data] or ['None']
    php_counts = [d['count'] for d in php_data] or [0]

    return render(request, 'admin/dashboard.html', {
        'total_sites':      sites.count(),
        'total_users':      users_qs.count(),
        'ssl_sites':        sites.filter(ssl_enabled=True).count(),
        'total_dbs':        Database.objects.count(),
        'total_backups':    BackupJob.objects.count() if _table_exists('lkypanel_backupjob') else 0,
        'cpu_percent':      round(cpu, 1),
        'ram_percent':      round(ram.percent, 1),
        'disk_percent':     round(disk.percent, 1),
        'disk_free_percent':round(100 - disk.percent, 1),
        'cpu_dashoffset':   dashoffset(cpu),
        'ram_dashoffset':   dashoffset(ram.percent),
        'disk_dashoffset':  dashoffset(disk.percent),
        'ram_total':        fmt_bytes(ram.total),
        'disk_total':       fmt_bytes(disk.total),
        'uptime':           uptime_str,
        'load_avg':         load_str,
        'cpu_history':      cpu_history,
        'ram_history':      ram_history,
        'php_labels':       php_labels,
        'php_counts':       php_counts,
        'recent_sites':     sites[:6],
        'audit_logs':       AuditLog.objects.select_related('user').order_by('-timestamp')[:8],
        'notifications_list': Notification.objects.filter(user=request.panel_user, is_read=False).order_by('-created_at')[:5],
        'active_page':      'dashboard',
        'panel_user':       request.panel_user,
    })


@admin_required
@csrf_protect
@require_http_methods(['POST'])
def create_website(request):
    from lkypanel.services.frameworks import install_framework
    
    data = json.loads(request.body)
    domain = data.get('domain', '').strip().lower()
    owner_id = data.get('owner_id')
    php_version = data.get('php_version', '8.1')
    framework = data.get('framework', Website.FRAMEWORK_NONE)

    try:
        owner = User.objects.get(pk=owner_id)
    except User.DoesNotExist:
        return JsonResponse({'error': 'Owner not found', 'code': 'NOT_FOUND', 'details': {}}, status=400)

    if Website.objects.filter(domain=domain).exists():
        return JsonResponse({'error': 'Domain already exists', 'code': 'DUPLICATE_DOMAIN', 'details': {}}, status=400)

    try:
        doc_root = f'/home/{domain}/public_html'
        site = Website(owner=owner, domain=domain, php_version=php_version, doc_root=doc_root, framework=framework)
        site.full_clean()
        site.save()
        
        ols.create_docroot(domain)
        ols.write_vhost_config(domain, php_version, framework=framework)
        
        # Trigger framework installation
        if framework != Website.FRAMEWORK_NONE:
            install_framework(site, framework)
            
        ols.reload_ols()
        log_action(request.panel_user, 'Website Created', f'Domain: {domain}, Framework: {framework}')
        return JsonResponse({'status': 'success', 'site_id': site.id})
    except Exception as e:
        logger.error('Failed to create website: %s', e)
        return JsonResponse({'error': str(e), 'code': 'INTERNAL_ERROR', 'details': {}}, status=500)


@admin_required
@csrf_protect
@require_http_methods(['POST'])
def delete_website(request, site_id):
    data = json.loads(request.body)
    if not data.get('confirm'):
        return JsonResponse({'error': 'Confirmation required', 'code': 'CONFIRM_REQUIRED', 'details': {}}, status=400)

    try:
        site = Website.objects.get(pk=site_id)
    except Website.DoesNotExist:
        return JsonResponse({'error': 'Website not found', 'code': 'NOT_FOUND', 'details': {}}, status=404)

    domain = site.domain
    delete_files = data.get('delete_files', False)

    # Remove OLS config — non-fatal if OLS not installed
    try:
        ols.delete_vhost_config(domain)
        ols.reload_ols()
    except Exception as e:
        logger.warning('OLS cleanup failed for %s: %s', domain, e)

    # Optionally remove files — non-fatal
    if delete_files:
        import shutil
        import pathlib
        home = pathlib.Path(f'/home/{domain}')
        if home.exists():
            try:
                shutil.rmtree(str(home))
            except Exception as e:
                logger.warning('Failed to delete files for %s: %s', domain, e)

    site.delete()
    log_action(request.panel_user, 'website_delete', domain, request.META.get('REMOTE_ADDR', '0.0.0.0'))
    return JsonResponse({'deleted': domain})


@admin_required
@csrf_protect
@require_http_methods(['POST'])
def configure_website(request, site_id):
    data = json.loads(request.body)
    try:
        site = Website.objects.get(pk=site_id)
    except Website.DoesNotExist:
        return JsonResponse({'error': 'Website not found', 'code': 'NOT_FOUND', 'details': {}}, status=404)

    php_version = data.get('php_version', site.php_version)
    site.php_version = php_version
    site.save(update_fields=['php_version'])

    try:
        ols.write_vhost_config(site.domain, php_version, ssl=site.ssl_enabled)
        ols.reload_ols()
    except Exception as e:
        return JsonResponse({'error': str(e), 'code': 'CONFIG_FAILED', 'details': {}}, status=500)

    log_action(request.panel_user, 'website_config', site.domain, request.META.get('REMOTE_ADDR', '0.0.0.0'))
    return JsonResponse({'domain': site.domain, 'php_version': php_version})


@admin_required
@csrf_protect
@require_http_methods(['POST'])
def request_ssl_admin(request, site_id):
    """Admin-side SSL certificate request."""
    try:
        site = Website.objects.get(pk=site_id)
    except Website.DoesNotExist:
        return JsonResponse({'error': 'Website not found', 'code': 'NOT_FOUND', 'details': {}}, status=404)

    from lkypanel.services.ssl import request_certificate
    try:
        cert = request_certificate(site)
    except ValueError as e:
        return JsonResponse({'error': str(e), 'code': 'DNS_CHECK_FAILED', 'details': {}}, status=400)
    except RuntimeError as e:
        return JsonResponse({'error': str(e), 'code': 'CERTBOT_FAILED', 'details': {}}, status=500)
    log_action(request.panel_user, 'ssl_request', site.domain, request.META.get('REMOTE_ADDR', '0.0.0.0'))
    return JsonResponse({'cert_path': cert.cert_path, 'expires_at': cert.expires_at.isoformat()}, status=201)
