"""
W3Panel v2 — URL Configuration
"""
from django.urls import path, include
from django.shortcuts import redirect

from apps.user import views as user_views

def root_redirect(request):
    """Redirect root to appropriate login page."""
    import os
    env_port = os.environ.get('SERVER_PORT')
    meta_port = request.META.get('SERVER_PORT', 0)
    try:
        port = int(env_port) if env_port else int(meta_port)
    except (ValueError, TypeError):
        port = 0

    if port in (2083, 12083) or env_port == '2083':
        return redirect('user_login')
    elif port in (2087, 12087) or env_port == '2087':
        return redirect('admin_login')
    else:
        return redirect('admin_login')

urlpatterns = [
    # Root redirect
    path('', root_redirect),
    
    # Direct SSO endpoint (WHM to cPanel 1-click autologin)
    path('sso/', user_views.user_sso, name='sso_direct'),

    # Admin
    path('', include('apps.admin.urls')),
    
    # User
    path('user/', include('apps.user.urls')),
    
    # API
    path('api/v1/', include('apps.api.urls')),
]