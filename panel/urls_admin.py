"""
W3Panel v2 — WHM Admin URLs (Port 2087)
Dedicated URL routing for WebHost Manager administrator panel.
"""
from django.urls import path, include

urlpatterns = [
    # Top-level admin routes (WHM standard)
    path('', include('apps.admin.urls')),
    
    # API endpoints
    path('api/v1/', include('apps.api.urls')),
]
