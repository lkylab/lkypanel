"""Mail administration views."""
import json
import logging
import os
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.shortcuts import render

from lkypanel.admin_views.decorators import admin_required
from lkypanel.audit import log_action
from lkypanel.services.mail import install_snappymail, INSTALL_PATH

logger = logging.getLogger(__name__)

@admin_required
@require_http_methods(['GET'])
def mail_dashboard(request):
    return render(request, 'admin/mail.html', {
        'active_page': 'mail',
        'panel_user': request.panel_user
    })

@admin_required
@require_http_methods(['GET'])
def mail_status(request):
    installed = os.path.exists(os.path.join(INSTALL_PATH, 'index.php'))
    return JsonResponse({'installed': installed})

@admin_required
@csrf_protect
@require_http_methods(['POST'])
def run_install_snappymail(request):
    success = install_snappymail()
    if success:
        log_action(request.panel_user, 'SnappyMail Installed', 'Admin triggered SnappyMail installation')
        return JsonResponse({'status': 'success'})
    else:
        return JsonResponse({'status': 'error', 'error': 'Installation failed. Check server logs.'}, status=500)
