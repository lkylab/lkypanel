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

    if log_id.startswith('site_') and not selected_domain:
        first_site = Website.objects.first()
        if first_site:
            selected_domain = first_site.domain

    log_content = get_log_content(log_id, 100, domain=selected_domain)

    log_types = [
        ('panel',       'Panel Log'),
        ('ols_error',   'OLS Error'),
        ('ols_access',  'OLS Access'),
        ('auth',        'Auth Log'),
        ('syslog',      'Syslog'),
        ('fail2ban',    'Fail2Ban'),
        ('site_access', 'Site Access'),
        ('site_error',  'Site Error'),
    ]

    names = dict(log_types)
    log_name = names.get(log_id, 'Log Viewer')
    if log_id in ('site_access', 'site_error') and selected_domain:
        log_name = f'{names[log_id]} — {selected_domain}'

    return render(request, 'admin/logs.html', {
        'active_page': 'logs',
        'panel_user': request.panel_user,
        'log_id': log_id,
        'log_name': log_name,
        'log_content': log_content,
        'log_types': log_types,
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
