"""
W3Panel v2 — User URLs
Full URL routing for user interface.
"""
from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('login/', views.user_login, name='user_login'),
    path('logout/', views.user_logout, name='user_logout'),
    
    # Dashboard
    path('', views.user_dashboard, name='user_dashboard'),
    path('dashboard/', views.user_dashboard, name='user_dashboard'),
    
    # Websites
    path('websites/', views.user_websites, name='user_websites'),
    path('websites/create/', views.user_website_create, name='user_website_create'),
    path('websites/<int:website_id>/manage/', views.user_website_manage, name='user_website_manage'),
    path('websites/<int:website_id>/vhost/', views.user_website_vhost, name='user_website_vhost'),
    path('websites/<int:website_id>/logs/', views.user_website_logs, name='user_website_logs'),
    path('websites/<int:website_id>/app-action/', views.user_website_app_action, name='user_website_app_action'),
    path('websites/<int:website_id>/release-deploy/', views.user_website_deploy_release, name='user_website_deploy_release'),
    path('websites/<int:website_id>/release-rollback/', views.user_website_rollback_release, name='user_website_rollback_release'),
    path('websites/<int:website_id>/toggle-proxy/', views.user_website_toggle_proxy, name='user_website_toggle_proxy'),
    path('websites/<int:website_id>/delete/', views.user_website_delete, name='user_website_delete'),
    
    # Databases
    path('databases/', views.user_databases, name='user_databases'),
    path('databases/<int:db_id>/delete/', views.user_database_delete, name='user_database_delete'),
    
    # File Manager
    path('filemanager/', views.user_files, name='user_filemanager'),
    path('files/', views.user_files, name='user_files'),
    
    # FTP
    path('ftp/', views.user_ftp, name='user_ftp'),
    path('ftp/<int:ftp_id>/delete/', views.user_ftp_delete, name='user_ftp_delete'),
    
    # SSL
    path('ssl/', views.user_ssl, name='user_ssl'),
    
    # DNS Zone Editor
    path('dns/', views.user_dns, name='user_dns'),
    path('dns/<int:record_id>/delete/', views.user_dns_delete, name='user_dns_delete'),
    
    # Backups
    path('backups/', views.user_backups, name='user_backups'),
    path('backups/<int:backup_id>/delete/', views.user_backup_delete, name='user_backup_delete'),
    
    # PHP Settings & INI
    path('php/', views.user_php, name='user_php'),
    
    # Cron Jobs
    path('cron/', views.user_cron, name='user_cron'),
    path('cron/<int:cron_id>/toggle/', views.user_cron_toggle, name='user_cron_toggle'),
    path('cron/<int:cron_id>/delete/', views.user_cron_delete, name='user_cron_delete'),
    
    # Profile
    path('profile/', views.user_profile, name='user_profile'),
    
    # SSO Impersonation
    path('sso/', views.user_sso, name='user_sso'),
    
    # Web Terminal
    path('terminal/', views.user_terminal, name='user_terminal'),
    path('terminal/exec/', views.user_terminal_exec, name='user_terminal_exec'),
]