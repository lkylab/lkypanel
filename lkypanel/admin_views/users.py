"""User management — admin only."""
import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect

from lkypanel.models import User, Package
from lkypanel.admin_views.decorators import admin_required
from lkypanel.audit import log_action
from lkypanel.utils.ip import get_client_ip


@admin_required
def list_users(request):
    from django.shortcuts import render
    if request.panel_user.role == 'reseller':
        users = User.objects.filter(parent_reseller=request.panel_user).select_related('package').order_by('-created_at')
    else:
        users = User.objects.all().select_related('package', 'parent_reseller').order_by('-created_at')
    
    packages = Package.objects.all().order_by('name')
    return render(request, 'admin/users.html', {
        'users': users,
        'packages': packages,
        'active_page': 'users',
        'panel_user': request.panel_user
    })


@admin_required
@csrf_protect
@require_http_methods(['POST'])
def create_user(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    role = data.get('role', 'user')
    package_id = data.get('package_id')

    if role not in ('admin', 'reseller', 'user'):
        return JsonResponse({'error': 'Invalid role', 'code': 'INVALID_ROLE'}, status=400)
    if User.objects.filter(username=username).exists():
        return JsonResponse({'error': 'Username already exists', 'code': 'DUPLICATE_USER'}, status=400)

    package = None
    if package_id:
        package = Package.objects.filter(pk=package_id).first()

    user = User.objects.create_user(
        username=username, 
        email=email, 
        password=password, 
        role=role,
        package=package,
        parent_reseller=request.panel_user if request.panel_user.role == 'reseller' else None
    )
    
    log_action(request.panel_user, 'user_create', username, get_client_ip(request))
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
    log_action(request.panel_user, 'user_delete', username, get_client_ip(request))
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
    log_action(request.panel_user, 'password_reset', target.username, get_client_ip(request))
    return JsonResponse({'reset': target.username})
