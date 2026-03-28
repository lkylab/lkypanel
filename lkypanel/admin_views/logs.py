"""Log viewer — admin views."""
import subprocess
from pathlib import Path
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from lkypanel.admin_views.decorators import admin_required

PANEL_LOG   = '/var/log/lkypanel/panel.log'
LSWS_ERROR  = '/usr/local/lsws/logs/error.log'
LSWS_ACCESS = '/usr/local/lsws/logs/access.log'
FAIL2BAN    = '/var/log/fail2ban.log'
SYSLOG      = '/var/log/syslog'
AUTH_LOG    = '/var/log/auth.log'


def _tail(path: str, lines: int = 200) -> str:
    """Read last N lines of a file via sudo tail."""
    if not path:
        return ''
    result = subprocess.run(
        ['sudo', 'tail', '-n', str(lines), path],
        capture_output=True, text=True, timeout=10
    )
    return result.stdout if result.returncode == 0 else f'[Cannot read {path}: {result.stderr.strip()}]'


def _site_log(domain: str, log_type: str, lines: int = 200) -> str:
    """Read access or error log for a specific site."""
    # CyberPanel/LKYPanel convention: /home/domain/logs/
    base = Path(f'/home/{domain}/logs')
    if log_type == 'access':
        candidates = [
            base / f'{domain}.access_log',
            base / 'access.log',
            Path(f'/usr/local/lsws/logs/{domain}.access_log'),
        ]
    else:
        candidates = [
            base / f'{domain}.error_log',
            base / 'error.log',
            Path(f'/usr/local/lsws/logs/{domain}.error_log'),
        ]
    for p in candidates:
        result = subprocess.run(
            ['sudo', 'tail', '-n', str(lines), str(p)],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return result.stdout or '[Log file is empty]'
    return f'[Log file not found for {domain}]'


# ── System-wide log views ─────────────────────────────────────────────────────

@admin_required
@require_http_methods(['GET'])
def logs_page(request):
    from django.shortcuts import render
    from lkypanel.models import Website
    sites = Website.objects.values('id', 'domain').order_by('domain')
    return render(request, 'admin/logs.html', {
        'sites': sites,
        'active_page': 'logs',
        'panel_user': request.panel_user,
    })


@admin_required
@require_http_methods(['GET'])
def get_log(request):
    """AJAX endpoint — returns log content as JSON."""
    log_type = request.GET.get('type', '')
    lines    = min(int(request.GET.get('lines', 200)), 1000)
    domain   = request.GET.get('domain', '')

    LOG_MAP = {
        'panel':       PANEL_LOG,
        'lsws_error':  LSWS_ERROR,
        'lsws_access': LSWS_ACCESS,
        'fail2ban':    FAIL2BAN,
        'syslog':      SYSLOG,
        'auth':        AUTH_LOG,
    }

    if log_type in ('site_access', 'site_error') and domain:
        content = _site_log(domain, 'access' if log_type == 'site_access' else 'error', lines)
    elif log_type in LOG_MAP:
        content = _tail(LOG_MAP[log_type], lines)
    else:
        return JsonResponse({'error': 'Unknown log type'}, status=400)

    return JsonResponse({'content': content, 'type': log_type, 'domain': domain})
