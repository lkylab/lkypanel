"""PHP admin views — INI editor and package manager."""
import json
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect

from lkypanel.admin_views.decorators import admin_required
from lkypanel.audit import log_action
from lkypanel.services import php as php_svc


def _ip(request):
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


@admin_required
@require_http_methods(['GET'])
def php_dashboard(request):
    versions = php_svc.get_installed_versions()
    selected = request.GET.get('version', versions[0] if versions else '8.3')
    tab = request.GET.get('tab', 'ini')
    return render(request, 'admin/php.html', {
        'versions': versions,
        'selected': selected,
        'tab': tab,
        'panel_user': request.panel_user,
        'active_page': 'php',
    })


@admin_required
@require_http_methods(['GET'])
def get_ini(request):
    version = request.GET.get('version', '8.3')
    result = php_svc.get_ini_values(version)
    return JsonResponse(result)


@admin_required
@require_http_methods(['POST'])
@csrf_protect
def save_ini(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    version = data.get('version', '8.3')
    content = data.get('content', '')
    result = php_svc.write_ini(version, content)
    if 'error' in result:
        return JsonResponse({'status': 0, 'error': result['error']})
    log_action(request.panel_user, 'php_ini_save', f'php{version}', _ip(request))
    return JsonResponse({'status': 1})


@admin_required
@require_http_methods(['GET'])
def get_packages(request):
    version = request.GET.get('version', '8.3')
    result = php_svc.get_packages(version)
    return JsonResponse(result)


@admin_required
@require_http_methods(['POST'])
@csrf_protect
def manage_packages(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    version = data.get('version', '8.3')
    action = data.get('action')  # 'install' or 'remove'
    extensions = data.get('extensions', [])
    if not extensions:
        return JsonResponse({'status': 0, 'error': 'No extensions selected'})
    if action == 'install':
        result = php_svc.install_packages(version, extensions)
        log_action(request.panel_user, 'php_pkg_install', f"php{version}: {','.join(extensions)}", _ip(request))
    elif action == 'remove':
        result = php_svc.remove_packages(version, extensions)
        log_action(request.panel_user, 'php_pkg_remove', f"php{version}: {','.join(extensions)}", _ip(request))
    else:
        return JsonResponse({'status': 0, 'error': 'Invalid action'})
    if 'error' in result:
        return JsonResponse({'status': 0, 'error': result['error']})
    return JsonResponse({'status': 1})
