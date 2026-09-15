"""
W3Panel v2 — W3Client Portal URLs (Port 2083)
Dedicated URL routing for end-user panel without '/user/' prefix.
"""
from django.urls import path, include
from apps.user import views

urlpatterns = [
    # Backward compatibility alias
    path('user/', include('apps.user.urls')),

    # Top-level user routes (W3Client standard)
    path('', include('apps.user.urls')),
    
    # API endpoints
    path('api/v1/', include('apps.api.urls')),
]
