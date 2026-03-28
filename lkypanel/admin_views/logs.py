"""Logs management — admin views."""
from django.shortcuts import render
from lkypanel.admin_views.decorators import admin_required
from lkypanel.services.logs import get_log_content
from lkypanel.models import Website

@admin_required
def logs_dashboard(request):
    """Show the logs dashboard."""
    websites = Website.objects.all()
    selected_domain = request.GET.get('domain')
    
    # We load them on demand via AJAX or just pass some initial data?
    # The user asked for "collapse by default", so maybe I just load names first
    # or load the last 50 lines for each.
    
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
