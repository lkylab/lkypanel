"""
W3Panel v2 — API URLs
REST API routing table for v1 endpoints.
"""
from django.urls import path
from . import views

urlpatterns = [
    # System
    path('system/', views.system_metrics, name='api_system_metrics'),

    # Websites (GET list, POST create, DELETE <id>)
    path('websites/', views.website_endpoint, name='api_websites'),
    path('websites/<int:website_id>/', views.website_delete, name='api_website_delete'),
    
    # Databases (GET list, POST create)
    path('databases/', views.database_endpoint, name='api_databases'),

    # Emails (GET list, POST create)
    path('emails/', views.email_endpoint, name='api_emails'),

    # Users (GET list, POST create)
    path('users/', views.user_endpoint, name='api_users'),

    # License
    path('license/activate/', views.license_activate, name='api_license_activate'),
    path('license/status/', views.license_status, name='api_license_status'),
]
