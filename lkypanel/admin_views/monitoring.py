"""
Monitoring and Notification views.
"""
import json
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect

from lkypanel.models import Notification
from lkypanel.admin_views.decorators import admin_required
from lkypanel.services.monitoring import get_system_stats

@admin_required
@require_http_methods(['GET'])
def system_stats_api(request):
    """
    API endpoint for real-time system stats.
    """
    stats = get_system_stats()
    return JsonResponse(stats)

@admin_required
@require_http_methods(['GET'])
def list_notifications(request):
    """
    List all notifications for the admin.
    """
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'admin/notifications.html', {
        'notifications': notifications,
        'active_page': 'notifications',
        'panel_user': request.panel_user
    })

@admin_required
@csrf_protect
@require_http_methods(['POST'])
def mark_notification_read(request, notification_id):
    """
    Mark a specific notification as read.
    """
    notification = get_object_or_404(Notification, pk=notification_id, user=request.user)
    notification.is_read = True
    notification.save()
    return JsonResponse({'status': 'success'})

@admin_required
@csrf_protect
@require_http_methods(['POST'])
def mark_all_read(request):
    """
    Mark all unread notifications for the user as read.
    """
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'status': 'success'})
