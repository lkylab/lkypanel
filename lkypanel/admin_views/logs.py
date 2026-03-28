"""Logs management — admin views."""
from django.shortcuts import render
from lkypanel.admin_views.decorators import admin_required
from django.http import JsonResponse
from lkypanel.services.logs import get_log_content
from lkypanel.models import Website

@admin_required
def logs_page(request):
    """Show the logs dashboard with the selected log."""
    log_id = request.GET.get('id', 'panel')
    selected_domain = request.GET.get('domain')
    
    # If it's a website log but no domain is selected, try to get the first website
    if log_id.startswith('site_') and not selected_domain:
        first_site = Website.objects.first()
        if first_site:
            selected_domain = first_site.domain

    log_content = get_log_content(log_id, 100, domain=selected_domain)
    
    # Map ID to human name
    names = {
        'ols_error': 'OLS Error Log',
        'ols_access': 'OLS Access Log',
        'panel': 'Panel Log',
        'fail2ban': 'Fail2Ban Log',
        'auth': 'Auth Log',
        'syslog': 'System Syslog',
        'site_access': f'Site Access Log ({selected_domain})',
        'site_error': f'Site Error Log ({selected_domain})',
    }
    
    return render(request, 'admin/logs.html', {
        'active_page': 'logs',
        'panel_user': request.panel_user,
        'log_id': log_id,
        'log_name': names.get(log_id, 'Log Viewer'),
        'log_content': log_content,
        'websites': Website.objects.all(),
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
