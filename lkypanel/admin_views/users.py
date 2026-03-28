"""User management — admin only."""
import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect

from lkypanel.models import User
from lkypanel.admin_views.decorators import admin_required
from lkypanel.audit import log_action


@admin_required
@require_http_methods(['GET'])
def list_users(request):
    from django.shortcuts import render
    users = User.objects.all().order_by('-created_at')
    return render(request, 'admin/users.html', {
        'users': users,
        'active_page': 'users',
        'panel_user': request.panel_user
    })


@admin_required
@csrf_protect
@require_http_methods(['POST'])
def create_user(request):
    data = json.loads(request.body)
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    role = data.get('role', 'user')

    if role not in ('admin', 'user'):
        return JsonResponse({'error': 'Invalid role', 'code': 'INVALID_ROLE', 'details': {}}, status=400)
    if User.objects.filter(username=username).exists():
        return JsonResponse({'error': 'Username already exists', 'code': 'DUPLICATE_USER', 'details': {}}, status=400)

    user = User.objects.create_user(username=username, email=email, password=password, role=role)
    log_action(request.panel_user, 'user_create', username, request.META.get('REMOTE_ADDR', '0.0.0.0'))
    return JsonResponse({'id': user.pk, 'username': user.username, 'role': user.role}, status=201)


@admin_required
@csrf_protect
@require_http_methods(['POST'])
def delete_user(request, user_id):
    try:
        target = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found', 'code': 'NOT_FOUND', 'details': {}}, status=404)

    username = target.username
    # Invalidate sessions by flushing — Django session store keyed by user
    from django.contrib.sessions.backends.db import SessionStore
    from django.contrib.sessions.models import Session
    for session in Session.objects.all():
        data = session.get_decoded()
        if data.get('user_id') == user_id:
            session.delete()

    target.delete()
    log_action(request.panel_user, 'user_delete', username, request.META.get('REMOTE_ADDR', '0.0.0.0'))
    return JsonResponse({'deleted': username})


@admin_required
@csrf_protect
@require_http_methods(['POST'])
def reset_password(request, user_id):
    try:
        target = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found', 'code': 'NOT_FOUND', 'details': {}}, status=404)

    data = json.loads(request.body)
    new_password = data.get('password', '')
    target.set_password(new_password)
    target.save(update_fields=['password'])
    log_action(request.panel_user, 'password_reset', target.username, request.META.get('REMOTE_ADDR', '0.0.0.0'))
    return JsonResponse({'reset': target.username})
