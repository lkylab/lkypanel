"""
W3Panel v2 — W3Host Manager Admin URLs (Port 2087)
Dedicated URL routing for W3Host Manager administrator panel.
"""
from django.urls import path, include
from apps.user import views as user_views

urlpatterns = [
    # Direct SSO endpoint (WHM to cPanel 1-click autologin)
    path('sso/', user_views.user_sso, name='admin_sso_direct'),
    path('user/sso/', user_views.user_sso, name='admin_user_sso_direct'),

    # Top-level admin routes (W3Host standard)
    path('', include('apps.admin.urls')),
    
    # API endpoints
    path('api/v1/', include('apps.api.urls')),
]
