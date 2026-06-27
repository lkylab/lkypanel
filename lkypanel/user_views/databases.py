"""Database management — user views."""
import json
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect

from lkypanel.models import Database
from lkypanel.user_views.decorators import login_required, owns_website
from lkypanel.services.db_manager import create_database, delete_database
from lkypanel.services.packages import is_plugin_installed


@login_required
@owns_website
@require_http_methods(['GET'])
def list_databases(request, site_id):
    site = request.panel_website
    databases = site.databases.all().order_by('-created_at')
    return render(request, 'user/site_databases.html', {
        'site': site,
        'databases': databases,
        'mariadb_installed': is_plugin_installed('mariadb'),
        'active_page': 'websites',
        'panel_user': request.panel_user,
    })


@login_required
@owns_website
@csrf_protect
@require_http_methods(['POST'])
def create_db(request, site_id):
    data = json.loads(request.body)
    db_name = data.get('db_name', '').strip()

    from lkypanel.utils.limits import check_limit
    allowed, msg = check_limit(request.panel_user, 'database')
    if not allowed:
        return JsonResponse({'error': msg, 'code': 'LIMIT_EXCEEDED', 'details': {}}, status=400)

    try:
        db = create_database(request.panel_website, db_name)
    except Exception as e:
        return JsonResponse({'error': str(e), 'code': 'DB_CREATE_FAILED', 'details': {}}, status=400)
    return JsonResponse({'id': db.pk, 'db_name': db.db_name, 'db_user': db.db_user}, status=201)


@login_required
@owns_website
@csrf_protect
@require_http_methods(['POST'])
def delete_db(request, site_id, db_id):
    try:
        db = Database.objects.get(pk=db_id, website=request.panel_website)
    except Database.DoesNotExist:
        return JsonResponse({'error': 'Not found', 'code': 'NOT_FOUND', 'details': {}}, status=404)
    try:
        delete_database(db)
    except Exception as e:
        return JsonResponse({'error': str(e), 'code': 'DB_DELETE_FAILED', 'details': {}}, status=500)
    return JsonResponse({'deleted': db.db_name})
