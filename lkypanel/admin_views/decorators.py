"""Decorators for admin-only and user-only views."""
from functools import wraps
from django.http import HttpResponseForbidden
from lkypanel.models import User


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        uid = request.session.get('user_id')
        if not uid:
            from django.shortcuts import redirect
            return redirect('/')
        try:
            user = User.objects.get(pk=uid, is_active=True)
        except User.DoesNotExist:
            return HttpResponseForbidden('Access denied.')
        if user.role not in ('admin', 'reseller'):
            return HttpResponseForbidden('Management access required.')
        request.panel_user = user
        return view_func(request, *args, **kwargs)
    return wrapper


def panel_login_required(view_func):
    """Ensure any panel user is logged in and populate request.panel_user."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        uid = request.session.get('user_id')
        if not uid:
            from django.shortcuts import redirect
            return redirect('/')
        try:
            user = User.objects.get(pk=uid, is_active=True)
        except User.DoesNotExist:
            from django.shortcuts import redirect
            return redirect('/')
        request.panel_user = user
        return view_func(request, *args, **kwargs)
    return wrapper
