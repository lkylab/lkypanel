from django.shortcuts import render
from lkypanel.admin_views.decorators import admin_required

@admin_required
def database_dashboard(request):
    """Placeholder for database management."""
    return render(request, 'admin/databases.html', {
        'active_page': 'databases',
        'panel_user': request.panel_user,
    })
