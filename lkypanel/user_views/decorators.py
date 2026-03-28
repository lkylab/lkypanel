"""Decorators for user views."""
from functools import wraps
from django.http import HttpResponseForbidden
from lkypanel.models import User


def login_required(view_func):
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
        request.panel_user = user
        return view_func(request, *args, **kwargs)
    return wrapper


def owns_website(view_func):
    """Ensure the panel_user owns the website identified by site_id kwarg."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from lkypanel.models import Website
        site_id = kwargs.get('site_id')
        try:
            site = Website.objects.get(pk=site_id)
        except Website.DoesNotExist:
            from django.http import JsonResponse
            return JsonResponse({'error': 'Not found', 'code': 'NOT_FOUND', 'details': {}}, status=404)
        user = request.panel_user
        if user.role != 'admin' and site.owner_id != user.pk:
            from lkypanel.audit import log_action
            log_action(user, 'unauthorized_access', f'website:{site_id}',
                       request.META.get('REMOTE_ADDR', '0.0.0.0'))
            return HttpResponseForbidden('Access denied.')
        request.panel_website = site
        return view_func(request, *args, **kwargs)
    return wrapper
