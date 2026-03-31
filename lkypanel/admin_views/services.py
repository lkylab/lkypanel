"""System Services management — admin only."""
import subprocess
from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.http import require_http_methods

from lkypanel.admin_views.decorators import admin_required
from lkypanel.services.monitoring import check_services

@admin_required
@require_http_methods(['GET'])
def list_services(request):
    """List system services and their statuses."""
    services = check_services()
    return render(request, 'admin/services.html', {
        'services': services,
        'active_page': 'services',
        'panel_user': request.panel_user
    })

@admin_required
@require_http_methods(['POST'])
def restart_service(request, service_name):
    """Restart a specific system service."""
    # Whitelist services to prevent arbitrary command execution
    allowed_services = [
        'lky-admin', 'lky-user', 'lshttpd', 'mariadb', 
        'pure-ftpd', 'postfix', 'dovecot'
    ]
    
    if service_name not in allowed_services:
        messages.error(request, f"Service '{service_name}' is not manageable.")
        return redirect('admin_list_services')
        
    try:
        subprocess.run(['sudo', 'systemctl', 'restart', service_name], check=True)
        messages.success(request, f"Service '{service_name}' restarted successfully.")
    except subprocess.CalledProcessError as e:
        messages.error(request, f"Failed to restart '{service_name}': {str(e)}")
        
    return redirect('admin_list_services')
