"""FTP administration views."""
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from lkypanel.admin_views.decorators import admin_required
from lkypanel.models import FTPAccount

@admin_required
@require_http_methods(['GET'])
def list_ftp_accounts(request):
    """List all FTP accounts across all websites."""
    accounts = FTPAccount.objects.select_related('website', 'website__owner').all().order_by('username')
    return render(request, 'admin/ftp.html', {
        'accounts': accounts,
        'active_page': 'ftp',
        'panel_user': request.panel_user
    })
