"""Logs management — admin views."""
from django.shortcuts import render
from lkypanel.admin_views.decorators import admin_required
from django.http import JsonResponse
from lkypanel.services.logs import get_log_content
from lkypanel.models import Website

@admin_required
def logs_page(request):
    """Show the logs dashboard."""
    websites = Website.objects.all()
    selected_domain = request.GET.get('domain')
    
    logs_data = {
        'ols_error': get_log_content('ols_error', 50),
        'ols_access': get_log_content('ols_access', 50),
        'panel': get_log_content('panel', 50),
        'fail2ban': get_log_content('fail2ban', 50),
        'auth': get_log_content('auth', 50),
        'syslog': get_log_content('syslog', 50),
    }
    
    if selected_domain:
        logs_data['site_access'] = get_log_content('site_access', 50, domain=selected_domain)
        logs_data['site_error'] = get_log_content('site_error', 50, domain=selected_domain)

    return render(request, 'admin/logs.html', {
        'active_page': 'logs',
        'panel_user': request.panel_user,
        'logs': logs_data,
        'websites': websites,
        'selected_domain': selected_domain,
    })

@admin_required
def get_log(request):
    """API endpoint to get log content."""
    log_id = request.GET.get('id')
    domain = request.GET.get('domain')
    lines = int(request.GET.get('lines', 100))
    content = get_log_content(log_id, lines, domain)
    return JsonResponse({'content': content})
