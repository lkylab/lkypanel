"""URL configuration for Lite Hosting Panel."""
from django.urls import path
from lkypanel.views.auth import login_index, admin_login, user_login, logout_view
from lkypanel.admin_views import users as au, websites as aw, backup as ab, packages as ap, firewall as af, security as as_
from lkypanel.admin_views import settings as aset, email as ae
from lkypanel.admin_views import logs as al
from lkypanel.user_views import ftp as uf, git as ug, ssl as us, databases as ud, websites as uw
from lkypanel.api import views as av

urlpatterns = [
    # ── Login / logout ────────────────────────────────────────────────────
    path('',          login_index,  name='login_index'),
    path('login/',    user_login,   name='user_login'),
    path('admin/login/', admin_login, name='admin_login'),
    path('logout/',   logout_view,  name='logout'),

    # ── Admin views ───────────────────────────────────────────────────────
    path('admin/dashboard/',                aw.admin_dashboard,  name='admin_dashboard'),
    path('admin/users/',                    au.list_users,      name='admin_list_users'),
    path('admin/packages/',                 ap.list_packages,    name='admin_list_packages'),
    path('admin/packages/trigger/',         ap.trigger_plugin,   name='admin_trigger_plugin'),
    path('admin/packages/status/',          ap.poll_status,      name='admin_poll_status'),
    path('admin/backup/',                   ab.list_backups,      name='admin_list_backups'),
    path('admin/backup/create/',            ab.create_config,     name='admin_create_backup'),
    path('admin/backup/trigger/',           ab.trigger_backup,    name='admin_trigger_backup'),
    path('admin/backup/restore/',           ab.restore_backup,    name='admin_restore_backup'),
    path('admin/firewall/',                 af.list_firewall,     name='admin_firewall'),
    path('admin/firewall/add/',             af.add_firewall_rule, name='admin_firewall_add'),
    path('admin/firewall/remove/',          af.remove_firewall_rule, name='admin_firewall_remove'),
    path('admin/security/',                 as_.security_dashboard, name='admin_security'),
    path('admin/security/manage-ban/',      as_.manage_ban,       name='admin_manage_ban'),
    path('admin/settings/',                 aset.settings_page,   name='admin_settings'),
    path('admin/logs/',                     al.logs_page,         name='admin_logs'),
    path('admin/logs/get/',                 al.get_log,           name='admin_get_log'),
    path('admin/email/',                    ae.email_dashboard,   name='admin_email'),
    path('admin/users/create/',             au.create_user,     name='admin_create_user'),
    path('admin/users/<int:user_id>/delete/', au.delete_user,   name='admin_delete_user'),
    path('admin/users/<int:user_id>/reset-password/', au.reset_password, name='admin_reset_password'),

    path('admin/websites/',                             aw.list_websites,    name='admin_list_websites'),
    path('admin/websites/create/',                      aw.create_website,   name='admin_create_website'),
    path('admin/websites/<int:site_id>/delete/',        aw.delete_website,   name='admin_delete_website'),
    path('admin/websites/<int:site_id>/config/',        aw.configure_website,name='admin_config_website'),
    path('admin/websites/<int:site_id>/detail/',        aw.website_detail,   name='admin_website_detail'),
    path('admin/websites/<int:site_id>/ssl/',           aw.request_ssl_admin,name='admin_request_ssl'),

    path('admin/export/websites/', ab.export_websites, name='admin_export_websites'),
    path('admin/export/users/',    ab.export_users,    name='admin_export_users'),

    # ── User views ────────────────────────────────────────────────────────
    path('user/dashboard/',                 uw.user_dashboard,  name='user_dashboard'),
    path('user/sites/<int:site_id>/ftp/',                        uf.list_ftp,     name='user_list_ftp'),
    path('user/sites/<int:site_id>/ftp/create/',                 uf.create_ftp,   name='user_create_ftp'),
    path('user/sites/<int:site_id>/ftp/<int:account_id>/delete/',uf.delete_ftp,   name='user_delete_ftp'),
    path('user/sites/<int:site_id>/ftp/<int:account_id>/passwd/',uf.change_ftp_pw,name='user_ftp_passwd'),

    path('user/sites/<int:site_id>/git/',         ug.list_repos, name='user_list_git'),
    path('user/sites/<int:site_id>/git/link/',    ug.link_repo,  name='user_link_git'),
    path('user/sites/<int:site_id>/git/pull/',    ug.git_pull,   name='user_git_pull'),
    path('user/sites/<int:site_id>/git/push/',    ug.git_push,   name='user_git_push'),

    path('user/sites/<int:site_id>/ssl/',         us.ssl_status, name='user_ssl_status'),
    path('user/sites/<int:site_id>/ssl/request/', us.request_ssl,name='user_ssl_request'),

    path('user/sites/<int:site_id>/databases/',                    ud.list_databases, name='user_list_db'),
    path('user/sites/<int:site_id>/databases/create/',             ud.create_db,      name='user_create_db'),
    path('user/sites/<int:site_id>/databases/<int:db_id>/delete/', ud.delete_db,      name='user_delete_db'),

    # ── REST API ──────────────────────────────────────────────────────────
    path('api/v1/websites/',              av.websites,       name='api_websites'),
    path('api/v1/websites/<int:site_id>/',av.website_detail, name='api_website_detail'),
    path('api/v1/users/',                 av.users,          name='api_users'),
    path('api/v1/ftp/',                   av.ftp_accounts,   name='api_ftp'),
    path('api/v1/ssl/',                   av.ssl_certs,      name='api_ssl'),
    path('api/v1/git/',                   av.git_repos,      name='api_git'),
    path('api/v1/databases/',             av.databases,      name='api_databases'),
    path('api/v1/tokens/create/',         av.create_token,   name='api_create_token'),
]
