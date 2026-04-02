"""Database management — admin views."""
import json
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect

from lkypanel.admin_views.decorators import admin_required
from lkypanel.models import Database, Website
from lkypanel.services.packages import is_plugin_installed


@admin_required
@require_http_methods(['GET'])
def database_dashboard(request):
    """List all databases across all websites."""
    mariadb_installed = is_plugin_installed('mariadb')
    phpmyadmin_installed = is_plugin_installed('phpmyadmin')

    if request.panel_user.role == 'reseller':
        databases = Database.objects.filter(
            website__owner__parent_reseller=request.panel_user
        ).select_related('website', 'website__owner').order_by('-created_at')
        websites = Website.objects.filter(owner__parent_reseller=request.panel_user)
    else:
        databases = Database.objects.select_related('website', 'website__owner').order_by('-created_at')
        websites = Website.objects.all()

    return render(request, 'admin/databases.html', {
        'active_page': 'databases',
        'panel_user': request.panel_user,
        'databases': databases,
        'websites': websites,
        'mariadb_installed': mariadb_installed,
        'phpmyadmin_installed': phpmyadmin_installed,
    })


@admin_required
@csrf_protect
@require_http_methods(['POST'])
def create_database(request):
    """Create a database for a website."""
    if not is_plugin_installed('mariadb'):
        return JsonResponse({'error': 'MariaDB not installed'}, status=400)
    data = json.loads(request.body)
    site_id = data.get('site_id')
    db_name = data.get('db_name', '').strip()
    try:
        site = Website.objects.get(pk=site_id)
    except Website.DoesNotExist:
        return JsonResponse({'error': 'Website not found'}, status=404)
    from lkypanel.services.db_manager import create_database as svc_create
    try:
        db = svc_create(site, db_name)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'id': db.pk, 'db_name': db.db_name, 'db_user': db.db_user}, status=201)


@admin_required
@csrf_protect
@require_http_methods(['POST'])
def delete_database(request, db_id):
    """Delete a database."""
    try:
        db = Database.objects.get(pk=db_id)
    except Database.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    from lkypanel.services.db_manager import delete_database as svc_delete
    try:
        svc_delete(db)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'deleted': db.db_name})
