"""Settings — admin view."""
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from django.contrib import messages

from lkypanel.admin_views.decorators import admin_required
from lkypanel.models import SystemSetting


@admin_required
@require_http_methods(['GET', 'POST'])
def settings_page(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'update_smtp':
            SystemSetting.set_val('smtp_host', request.POST.get('smtp_host', ''))
            SystemSetting.set_val('smtp_port', request.POST.get('smtp_port', '587'))
            SystemSetting.set_val('smtp_user', request.POST.get('smtp_user', ''))
            SystemSetting.set_val('smtp_pass', request.POST.get('smtp_pass', ''))
            SystemSetting.set_val('smtp_from', request.POST.get('smtp_from', ''))
            SystemSetting.set_val('alert_recipient', request.POST.get('alert_recipient', ''))
            messages.success(request, "SMTP settings updated successfully.")
            
        elif action == 'update_thresholds':
            SystemSetting.set_val('threshold_cpu', request.POST.get('threshold_cpu', '90'))
            SystemSetting.set_val('threshold_ram', request.POST.get('threshold_ram', '90'))
            SystemSetting.set_val('threshold_disk', request.POST.get('threshold_disk', '90'))
            messages.success(request, "Alert thresholds updated successfully.")
            
        return redirect('admin_settings')

    # GET
    settings = {
        'smtp_host': SystemSetting.get_val('smtp_host', ''),
        'smtp_port': SystemSetting.get_val('smtp_port', '587'),
        'smtp_user': SystemSetting.get_val('smtp_user', ''),
        'smtp_pass': SystemSetting.get_val('smtp_pass', ''),
        'smtp_from': SystemSetting.get_val('smtp_from', ''),
        'alert_recipient': SystemSetting.get_val('alert_recipient', ''),
        'threshold_cpu': SystemSetting.get_val('threshold_cpu', '90'),
        'threshold_ram': SystemSetting.get_val('threshold_ram', '90'),
        'threshold_disk': SystemSetting.get_val('threshold_disk', '90'),
    }

    return render(request, 'admin/settings.html', {
        'active_page': 'settings',
        'panel_user': request.panel_user,
        'settings': settings
    })
