"""FTP administration views."""
import json
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect

from lkypanel.admin_views.decorators import admin_required
from lkypanel.models import FTPAccount, Website
from lkypanel.services.ftp import create_ftp_account, delete_ftp_account, is_pureftpd_installed
from lkypanel.audit import log_action


@admin_required
@require_http_methods(['GET'])
def list_ftp_accounts(request):
    accounts = FTPAccount.objects.select_related('website', 'website__owner').all().order_by('username')
    websites = Website.objects.select_related('owner').all().order_by('domain')
    return render(request, 'admin/ftp.html', {
        'accounts': accounts,
        'websites': websites,
        'active_page': 'ftp',
        'panel_user': request.panel_user,
    })


@admin_required
@csrf_protect
@require_http_methods(['POST'])
def admin_create_ftp(request):
    if not is_pureftpd_installed():
        return JsonResponse({'error': 'Pure-FTPd not installed'}, status=400)
    data = json.loads(request.body)
    site_id = data.get('site_id')
    username = data.get('username', '').strip()
    password = data.get('password', '')
    quota_mb = int(data.get('quota_mb', 1024))
    if not site_id or not username or not password:
        return JsonResponse({'error': 'All fields are required.'}, status=400)
    website = get_object_or_404(Website, pk=site_id)
    try:
        account = create_ftp_account(website, username, password, quota_mb)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
    log_action(request.panel_user, 'admin_ftp_create', username, request.META.get('REMOTE_ADDR', '0.0.0.0'))
    return JsonResponse({'id': account.pk, 'username': account.username}, status=201)


@admin_required
@csrf_protect
@require_http_methods(['POST'])
def admin_delete_ftp(request, account_id):
    account = get_object_or_404(FTPAccount, pk=account_id)
    username = account.username
    delete_ftp_account(account)
    log_action(request.panel_user, 'admin_ftp_delete', username, request.META.get('REMOTE_ADDR', '0.0.0.0'))
    return JsonResponse({'deleted': username})
