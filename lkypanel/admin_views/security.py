"""Security management — admin views."""
import json
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect

from lkypanel.admin_views.decorators import admin_required
from lkypanel.services.security import get_jails, get_jail_status, ban_ip, unban_ip, get_logs
from lkypanel.services.packages import is_plugin_installed

@admin_required
@require_http_methods(['GET'])
def security_dashboard(request):
    """Render the security (Fail2Ban) management page."""
    jail_names = get_jails()
    jails = {name: get_jail_status(name) for name in jail_names}
    logs = get_logs(30)

    return render(request, 'admin/security.html', {
        'jails': jails,
        'logs': logs,
        'fail2ban_installed': is_plugin_installed('fail2ban'),
        'active_page': 'security',
        'panel_user': request.panel_user
    })

@admin_required
@csrf_protect
@require_http_methods(['POST'])
def manage_ban(request):
    """Ban or unban an IP."""
    try:
        data = json.loads(request.body)
        action = data.get('action') # 'ban' or 'unban'
        jail = data.get('jail')
        ip = data.get('ip')
        
        if not jail or not ip:
            return JsonResponse({'error': 'Missing jail or IP'}, status=400)
            
        if action == 'ban':
            success, message = ban_ip(jail, ip)
        elif action == 'unban':
            success, message = unban_ip(jail, ip)
        else:
            return JsonResponse({'error': 'Invalid action'}, status=400)
            
        if success:
            return JsonResponse({'status': 'success', 'message': message})
        else:
            return JsonResponse({'status': 'error', 'message': message}, status=500)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
