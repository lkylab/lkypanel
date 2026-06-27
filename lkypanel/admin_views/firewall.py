"""Firewall management — admin views."""
import json
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect

from lkypanel.admin_views.decorators import admin_required
from lkypanel.services.firewall import get_rules, add_rule, delete_rule, get_ufw_status

@admin_required
@require_http_methods(['GET'])
def list_firewall(request):
    """Render the firewall management page."""
    rules = get_rules()
    is_active = get_ufw_status()
    return render(request, 'admin/firewall.html', {
        'rules': rules,
        'is_active': is_active,
        'active_page': 'firewall',
        'panel_user': request.panel_user
    })

@admin_required
@csrf_protect
@require_http_methods(['POST'])
def add_firewall_rule(request):
    """Add a firewall rule."""
    try:
        data = json.loads(request.body)
        port = data.get('port')
        from_ip = data.get('from_ip', 'Anywhere')
        proto = data.get('proto', 'tcp')
        action = data.get('action', 'allow')
        
        if not port:
            return JsonResponse({'error': 'Missing port'}, status=400)
            
        success, message = add_rule(port, proto, from_ip, action)
        if success:
            return JsonResponse({'status': 'success', 'message': message})
        else:
            return JsonResponse({'status': 'error', 'message': message}, status=500)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@admin_required
@csrf_protect
@require_http_methods(['POST'])
def remove_firewall_rule(request):
    """Delete a firewall rule."""
    try:
        data = json.loads(request.body)
        index = data.get('index')
        if not index:
            return JsonResponse({'error': 'Missing rule index'}, status=400)
            
        success, message = delete_rule(index)
        if success:
            return JsonResponse({'status': 'success', 'message': message})
        else:
            return JsonResponse({'status': 'error', 'message': message}, status=500)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
