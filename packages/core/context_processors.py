"""
W3Panel v2 — Context Processors
Inject global state into templates.
"""
from packages.core.models import SystemSetting


def panel_context(request):
    """Globally inject panel_user and common state."""
    impersonated_by = None
    admin_panel_url = '/users/'

    if hasattr(request, 'session'):
        impersonated_by = request.session.get('impersonated_by', None)

    try:
        host = request.get_host()
        scheme = 'https' if request.is_secure() or request.META.get('HTTP_X_FORWARDED_PROTO') == 'https' else (request.scheme or 'http')
        if ':2083' in host:
            admin_host = host.replace(':2083', ':2087')
            admin_panel_url = f"{scheme}://{admin_host}/users/"
        elif ':12083' in host:
            admin_host = host.replace(':12083', ':12087')
            admin_panel_url = f"{scheme}://{admin_host}/users/"
        elif ':2087' in host or ':12087' in host:
            admin_panel_url = f"{scheme}://{host}/users/"
        else:
            admin_panel_url = '/users/'
    except Exception:
        admin_panel_url = '/users/'

    return {
        'panel_user': getattr(request, 'panel_user', None),
        'impersonated_by': impersonated_by,
        'admin_panel_url': admin_panel_url,
    }


def system_metrics(request):
    """Inject live system metrics and system info into every admin template."""
    import platform
    import socket
    import psutil

    # Get OS info from /etc/os-release
    os_name = platform.system()
    try:
        with open('/etc/os-release') as f:
            for line in f:
                if line.startswith('PRETTY_NAME='):
                    os_name = line.split('=', 1)[1].strip().strip('"')
                    break
    except Exception:
        os_name = f"{platform.system()} {platform.release()}"

    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    load = psutil.getloadavg()

    return {
        'system': {
            'hostname': socket.gethostname(),
            'kernel': platform.release(),
            'os': os_name,
        },
        'metrics': {
            'cpu': round(psutil.cpu_percent(interval=0.1), 1),
            'ram_used': round(mem.used / 1024 / 1024),
            'ram_total': round(mem.total / 1024 / 1024),
            'ram_percent': round(mem.percent, 1),
            'disk_used': round(disk.used / 1024 / 1024 / 1024, 1),
            'disk_total': round(disk.total / 1024 / 1024 / 1024, 1),
            'disk_percent': round(disk.percent, 1),
            'load': round(load[0], 2),
            'load5': round(load[1], 2),
            'load15': round(load[2], 2),
        },
    }


def plugin_states(request):
    """Inject plugin installed states."""
    return {
        'mariadb_installed': _is_installed('mariadb'),
        'postgresql_installed': _is_installed('postgresql'),
        'redis_installed': _is_installed('redis'),
        'nginx_installed': _is_installed('nginx'),
        'snappymail_installed': _is_installed('snappymail'),
    }


def license_context(request):
    """Inject license state."""
    tier = SystemSetting.get('license_tier', 'free')
    features = SystemSetting.get('license_features', '[]')
    
    import json
    try:
        features = json.loads(features)
    except (json.JSONDecodeError, TypeError):
        features = []

    return {
        'license_tier': tier,
        'license_features': features,
        'is_licensed': tier != 'free',
    }


def _is_installed(plugin_id):
    """Check if a plugin is installed."""
    from packages.plugins.models import PluginState
    state = PluginState.get(plugin_id)
    return state.installed
