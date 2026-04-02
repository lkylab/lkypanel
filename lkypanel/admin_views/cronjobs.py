"""Cronjob administration views."""
from django.shortcuts import render
from lkypanel.admin_views.decorators import admin_required
from lkypanel.models import Cronjob


@admin_required
def list_cronjobs(request):
    jobs = Cronjob.objects.select_related('website', 'website__owner').all().order_by('-created_at')
    return render(request, 'admin/cronjobs.html', {
        'cronjobs': jobs,
        'active_page': 'cronjobs',
        'panel_user': request.panel_user,
    })
