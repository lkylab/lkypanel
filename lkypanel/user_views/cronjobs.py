"""Cronjob management — user views."""
import json
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect

from lkypanel.models import Cronjob, Website
from lkypanel.user_views.decorators import login_required, owns_website
from lkypanel.audit import log_action


@login_required
@owns_website
@require_http_methods(['GET'])
def list_cronjobs(request, site_id):
    site = request.panel_website
    jobs = site.cronjobs.all().order_by('-created_at')
    return render(request, 'user/site_cronjobs.html', {
        'site': site,
        'cronjobs': jobs,
        'active_page': 'websites',
        'panel_user': request.panel_user,
    })


@login_required
@owns_website
@csrf_protect
@require_http_methods(['POST'])
def create_cronjob(request, site_id):
    data = json.loads(request.body)
    command = data.get('command', '').strip()
    schedule = data.get('schedule', '').strip()
    description = data.get('description', '').strip()
    if not command or not schedule:
        return JsonResponse({'error': 'Command and schedule are required.'}, status=400)
    job = Cronjob.objects.create(
        website=request.panel_website,
        command=command,
        schedule=schedule,
        description=description,
    )
    log_action(request.panel_user, 'cronjob_create', command[:80], request.META.get('REMOTE_ADDR', '0.0.0.0'))
    return JsonResponse({'id': job.pk, 'schedule': job.schedule, 'command': job.command}, status=201)


@login_required
@owns_website
@csrf_protect
@require_http_methods(['POST'])
def delete_cronjob(request, site_id, job_id):
    job = get_object_or_404(Cronjob, pk=job_id, website=request.panel_website)
    cmd = job.command[:80]
    job.delete()
    log_action(request.panel_user, 'cronjob_delete', cmd, request.META.get('REMOTE_ADDR', '0.0.0.0'))
    return JsonResponse({'deleted': job_id})


@login_required
@require_http_methods(['GET'])
def all_user_cronjobs(request):
    """List all cronjobs across all sites owned by the user."""
    user_id = request.session.get('user_id')
    jobs = Cronjob.objects.filter(website__owner_id=user_id).select_related('website').order_by('-created_at')
    return render(request, 'user/cronjobs_all.html', {
        'cronjobs': jobs,
        'active_page': 'cronjobs',
        'panel_user': request.panel_user,
    })
