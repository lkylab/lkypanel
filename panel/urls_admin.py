"""
W3Panel v2 — W3Host Manager Admin URLs (Port 2087)
Dedicated URL routing for W3Host Manager administrator panel.
"""
from django.urls import path, include

urlpatterns = [
    # Top-level admin routes (W3Host standard)
    path('', include('apps.admin.urls')),
    
    # API endpoints
    path('api/v1/', include('apps.api.urls')),
]
