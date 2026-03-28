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
        if user.role != 'admin':
            return HttpResponseForbidden('Admin access required.')
        request.panel_user = user
        return view_func(request, *args, **kwargs)
    return wrapper
