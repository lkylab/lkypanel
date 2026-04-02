"""FTP account management — user views."""
import json
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect

from lkypanel.models import FTPAccount, Website
from lkypanel.user_views.decorators import login_required, owns_website
from lkypanel.services.ftp import (
    create_ftp_account, delete_ftp_account, change_ftp_password, is_pureftpd_installed
)
from lkypanel.audit import log_action


@login_required
@owns_website
@require_http_methods(['GET'])
def list_ftp(request, site_id):
    site = request.panel_website
    accounts = site.ftp_accounts.all()
    return render(request, 'user/site_ftp.html', {
        'site': site,
        'ftp_accounts': accounts,
        'ftp_installed': is_pureftpd_installed(),
        'active_page': 'websites',
        'panel_user': request.panel_user,
    })


@login_required
@owns_website
@csrf_protect
@require_http_methods(['POST'])
def create_ftp(request, site_id):
    if not is_pureftpd_installed():
        return JsonResponse({'error': 'Pure-FTPd not installed', 'code': 'FTP_NOT_INSTALLED', 'details': {}}, status=400)

    data = json.loads(request.body)
    username = data.get('username', '').strip()
    password = data.get('password', '')
    quota_mb = int(data.get('quota_mb', 1024))

    from lkypanel.utils.limits import check_limit
    allowed, msg = check_limit(request.panel_user, 'ftp')
    if not allowed:
        return JsonResponse({'error': msg, 'code': 'LIMIT_EXCEEDED', 'details': {}}, status=400)

    try:
        account = create_ftp_account(request.panel_website, username, password, quota_mb)
    except Exception as e:
        return JsonResponse({'error': str(e), 'code': 'FTP_CREATE_FAILED', 'details': {}}, status=400)

    log_action(request.panel_user, 'ftp_create', username, request.META.get('REMOTE_ADDR', '0.0.0.0'))
    return JsonResponse({'id': account.pk, 'username': account.username}, status=201)


@login_required
@owns_website
@csrf_protect
@require_http_methods(['POST'])
def delete_ftp(request, site_id, account_id):
    try:
        account = FTPAccount.objects.get(pk=account_id, website=request.panel_website)
    except FTPAccount.DoesNotExist:
        return JsonResponse({'error': 'Not found', 'code': 'NOT_FOUND', 'details': {}}, status=404)

    username = account.username
    delete_ftp_account(account)
    log_action(request.panel_user, 'ftp_delete', username, request.META.get('REMOTE_ADDR', '0.0.0.0'))
    return JsonResponse({'deleted': username})


@login_required
@owns_website
@csrf_protect
@require_http_methods(['POST'])
def change_ftp_pw(request, site_id, account_id):
    try:
        account = FTPAccount.objects.get(pk=account_id, website=request.panel_website)
    except FTPAccount.DoesNotExist:
        return JsonResponse({'error': 'Not found', 'code': 'NOT_FOUND', 'details': {}}, status=404)

    data = json.loads(request.body)
    new_password = data.get('password', '')
    change_ftp_password(account, new_password)
    return JsonResponse({'updated': account.username})
