"""Database management — user views."""
import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect

from lkypanel.models import Database
from lkypanel.user_views.decorators import login_required, owns_website
from lkypanel.services.db_manager import create_database, delete_database


@login_required
@owns_website
@require_http_methods(['GET'])
def list_databases(request, site_id):
    dbs = list(request.panel_website.databases.values('id', 'db_name', 'db_user', 'created_at'))
    return JsonResponse({'databases': dbs})


@login_required
@owns_website
@csrf_protect
@require_http_methods(['POST'])
def create_db(request, site_id):
    data = json.loads(request.body)
    db_name = data.get('db_name', '').strip()
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
