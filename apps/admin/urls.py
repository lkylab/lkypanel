"""
W3Panel v2 — Admin URLs
Full URL routing for admin interface.
"""
from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('login/', views.admin_login, name='admin_login'),
    path('logout/', views.admin_logout, name='admin_logout'),
    
    # Dashboard
    path('', views.admin_dashboard, name='admin_dashboard'),
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    
    # Accounts
    path('users/', views.admin_users, name='admin_users'),
    path('users/create/', views.admin_user_create, name='admin_user_create'),
    path('users/<int:user_id>/edit/', views.admin_user_edit, name='admin_user_edit'),
    path('users/<int:user_id>/autologin/', views.admin_user_autologin, name='admin_user_autologin'),
    path('users/<int:user_id>/impersonate/', views.admin_user_autologin, name='admin_user_impersonate'),
    path('users/<int:user_id>/toggle-status/', views.admin_user_toggle_status, name='admin_user_toggle_status'),
    path('users/<int:user_id>/toggle-shell/', views.admin_user_toggle_shell, name='admin_user_toggle_shell'),
    path('users/<int:user_id>/delete/', views.admin_user_delete, name='admin_user_delete'),
    path('resellers/', views.admin_resellers, name='admin_resellers'),
    path('administrators/', views.admin_administrators, name='admin_administrators'),
    
    # Plans & Features
    path('plans/', views.admin_plans, name='admin_plans'),
    path('plans/<int:plan_id>/delete/', views.admin_plan_delete, name='admin_plan_delete'),
    path('features/', views.admin_features, name='admin_features'),
    
    # Domains & Websites
    path('domains/', views.admin_websites, name='admin_domains'),
    path('websites/', views.admin_websites, name='admin_websites'),
    path('websites/<int:website_id>/vhost/', views.admin_website_vhost, name='admin_website_vhost'),
    path('websites/<int:website_id>/toggle-proxy/', views.admin_website_toggle_proxy, name='admin_website_toggle_proxy'),
    path('websites/<int:website_id>/delete/', views.admin_website_delete, name='admin_website_delete'),
    path('domains/dns/', views.admin_dns_editor, name='admin_dns_editor'),
    path('domains/dns-cluster/', views.admin_dns_cluster, name='admin_dns_cluster'),
    
    # Services & Plugins
    path('plugins/', views.admin_plugins, name='admin_plugins'),
    path('services/', views.admin_services_status, name='admin_services_status'),
    path('services/cron/', views.admin_cron, name='admin_cron'),
    path('services/ftp/', views.admin_ftp_service, name='admin_ftp_service'),
    path('services/logs/', views.admin_system_logs, name='admin_system_logs'),
    
    # Settings & License
    path('settings/', views.admin_settings, name='admin_settings'),
    path('license/', views.license_management if hasattr(views, 'license_management') else views.admin_license, name='admin_license'),
    path('settings/api/', views.admin_api_settings, name='admin_api_settings'),
    path('settings/php/', views.admin_php_settings, name='admin_php_settings'),
    path('settings/notifications/', views.admin_notifications_settings, name='admin_notifications_settings'),
    
    # Security
    path('security/firewall/', views.admin_firewall, name='admin_firewall'),
    path('security/2fa/', views.admin_2fa_settings, name='admin_2fa_settings'),
    
    # Notifications, Wizards & Monitoring
    path('notifications/', views.admin_notifications, name='admin_notifications'),
    path('wizards/', views.wizard_dashboard, name='admin_wizard_dashboard'),
    path('wizards/', views.wizard_dashboard, name='admin_wizards'),
    path('monitoring/', views.monitoring_dashboard, name='admin_monitoring'),

    # Web Terminal
    path('terminal/', views.admin_terminal, name='admin_terminal'),
    path('terminal/exec/', views.admin_terminal_exec, name='admin_terminal_exec'),

    # API metrics
    path('api/metrics/', views.api_metrics, name='admin_api_metrics'),
]