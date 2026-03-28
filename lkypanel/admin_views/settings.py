"""Settings — admin view."""
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from lkypanel.admin_views.decorators import admin_required


@admin_required
@require_http_methods(['GET'])
def settings_page(request):
    return render(request, 'admin/settings.html', {
        'active_page': 'settings',
        'panel_user': request.panel_user
    })
