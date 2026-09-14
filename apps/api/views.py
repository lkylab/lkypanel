"""
W3Panel v2 — API Views
Full REST API endpoints with Bearer token auth.
"""
import json
import hashlib
import psutil
from functools import wraps

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt

from packages.core.models import APIToken, Website, User, Database, Mailbox
from services.webserver import create_vhost, remove_vhost, create_user_php_pool
from services.database import create_database, delete_database
from services.mail import create_mailbox, delete_mailbox


# ---------------------------------------------------------------------------
# API Auth Decorator
# ---------------------------------------------------------------------------

def api_auth(view_func):
    """Authenticate API request via Bearer token."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        auth = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth.startswith('Bearer '):
            return JsonResponse({'error': 'Missing or invalid Authorization header'}, status=401)

        token_raw = auth[7:].strip()
        token_hash = hashlib.sha256(token_raw.encode()).hexdigest()
        try:
            token = APIToken.objects.get(token_hash=token_hash, is_active=True)
        except APIToken.DoesNotExist:
            return JsonResponse({'error': 'Invalid API token'}, status=401)

        from django.utils import timezone
        token.last_used = timezone.now()
        token.save(update_fields=['last_used'])

        request.api_user = token.user
        return view_func(request, *args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# System Endpoints
# ---------------------------------------------------------------------------

@require_GET
def system_metrics(request):
    """GET /api/v1/system/"""
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    load = psutil.getloadavg()
    return JsonResponse({
        'cpu_percent': round(psutil.cpu_percent(interval=0.1), 1),
        'memory': {
            'used_mb': round(mem.used / (1024 * 1024)),
            'total_mb': round(mem.total / (1024 * 1024)),
            'percent': round(mem.percent, 1)
        },
        'disk': {
            'used_gb': round(disk.used / (1024 ** 3), 1),
            'total_gb': round(disk.total / (1024 ** 3), 1),
            'percent': round(disk.percent, 1)
        },
        'load_average': {
            '1m': round(load[0], 2),
            '5m': round(load[1], 2),
            '15m': round(load[2], 2)
        }
    })


@csrf_exempt
@api_auth
def website_endpoint(request):
    """GET (list) or POST (create) /api/v1/websites/"""
    if request.method == 'GET':
        if request.api_user.role == 'admin':
            websites = Website.objects.all()
        else:
            websites = Website.objects.filter(owner=request.api_user)

        data = [
            {
                'id': w.id,
                'domain': w.domain,
                'owner': w.owner.username,
                'framework': w.framework,
                'php_version': w.php_version,
                'ssl_enabled': w.ssl_enabled,
                'is_active': w.is_active,
                'created_at': w.created_at.isoformat(),
            }
            for w in websites
        ]
        return JsonResponse({'websites': data})

    elif request.method == 'POST':
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON body'}, status=400)

        domain = body.get('domain', '').strip().lower()
        if not domain:
            return JsonResponse({'error': 'Domain is required'}, status=400)

        if Website.objects.filter(domain=domain).exists():
            return JsonResponse({'error': f'Domain {domain} already exists'}, status=409)

        owner = request.api_user
        if request.api_user.role == 'admin' and body.get('owner_username'):
            target_user = User.objects.filter(username=body.get('owner_username')).first()
            if target_user:
                owner = target_user

        doc_root = f"/home/{owner.username}/{domain}/public_html"
        website = Website.objects.create(
            owner=owner,
            domain=domain,
            doc_root=doc_root,
            framework=body.get('framework', 'none'),
            php_version=body.get('php_version', '8.3'),
        )

        create_vhost(website)

        return JsonResponse({
            'id': website.id,
            'domain': website.domain,
            'owner': website.owner.username,
            'doc_root': website.doc_root,
            'framework': website.framework,
            'created_at': website.created_at.isoformat(),
        }, status=201)

    return JsonResponse({'error': 'Method not allowed'}, status=405)

    return JsonResponse({
        'id': website.id,
        'domain': website.domain,
        'owner': website.owner.username,
        'doc_root': website.doc_root,
        'framework': website.framework,
        'created_at': website.created_at.isoformat(),
    }, status=201)


@api_auth
@require_http_methods(['DELETE'])
@csrf_exempt
def website_delete(request, website_id):
    """DELETE /api/v1/websites/<id>/"""
    if request.api_user.role == 'admin':
        website = Website.objects.filter(id=website_id).first()
    else:
        website = Website.objects.filter(id=website_id, owner=request.api_user).first()

    if not website:
        return JsonResponse({'error': 'Website not found'}, status=404)

    domain = website.domain
    remove_vhost(domain)
    website.delete()
    return JsonResponse({'success': True, 'message': f'Website {domain} removed'})


@csrf_exempt
@api_auth
def database_endpoint(request):
    """GET (list) or POST (create) /api/v1/databases/"""
    if request.method == 'GET':
        if request.api_user.role == 'admin':
            databases = Database.objects.all()
        else:
            databases = Database.objects.filter(owner=request.api_user)

        data = [
            {
                'id': d.id,
                'name': d.name,
                'db_type': d.db_type,
                'db_user': d.db_user,
                'owner': d.owner.username,
                'size_mb': d.size_mb,
                'created_at': d.created_at.isoformat(),
            }
            for d in databases
        ]
        return JsonResponse({'databases': data})

    elif request.method == 'POST':
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        name = body.get('name', '').strip().lower()
        if not name:
            return JsonResponse({'error': 'Database name is required'}, status=400)

        owner = request.api_user
        full_name = f"{owner.username}_{name}" if not name.startswith(f"{owner.username}_") else name
        db_type = body.get('db_type', 'mariadb')
        db_user = body.get('db_user', full_name)
        db_pass = body.get('db_pass', '')

        if Database.objects.filter(name=full_name).exists():
            return JsonResponse({'error': f'Database {full_name} already exists'}, status=409)

        res = create_database(full_name, db_user, db_pass, db_type=db_type)
        db_obj = Database.objects.create(
            owner=owner,
            name=full_name,
            db_type=db_type,
            db_user=db_user
        )

        return JsonResponse({
            'id': db_obj.id,
            'name': db_obj.name,
            'db_user': db_obj.db_user,
            'db_type': db_obj.db_type,
            'password': res.get('db_pass', '')
        }, status=201)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


# ---------------------------------------------------------------------------
# Email Endpoints
# ---------------------------------------------------------------------------

@csrf_exempt
@api_auth
def email_endpoint(request):
    """GET (list) or POST (create) /api/v1/emails/"""
    if request.method == 'GET':
        if request.api_user.role == 'admin':
            mailboxes = Mailbox.objects.all()
        else:
            mailboxes = Mailbox.objects.filter(owner=request.api_user)

        data = [
            {
                'id': m.id,
                'email': m.email,
                'domain': m.domain,
                'quota_mb': m.quota_mb,
                'used_mb': m.used_mb,
                'owner': m.owner.username,
                'created_at': m.created_at.isoformat(),
            }
            for m in mailboxes
        ]
        return JsonResponse({'emails': data})

    elif request.method == 'POST':
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        username = body.get('username', '').strip().lower()
        domain = body.get('domain', '').strip().lower()
        quota = int(body.get('quota_mb', 1024))

        if not username or not domain:
            return JsonResponse({'error': 'Username and domain are required'}, status=400)

        full_email = f"{username}@{domain}"
        if Mailbox.objects.filter(email=full_email).exists():
            return JsonResponse({'error': f'Mailbox {full_email} already exists'}, status=409)

        owner = request.api_user
        create_mailbox(full_email, quota_mb=quota)
        mb = Mailbox.objects.create(
            owner=owner,
            email=full_email,
            domain=domain,
            quota_mb=quota
        )

        return JsonResponse({
            'id': mb.id,
            'email': mb.email,
            'domain': mb.domain,
            'quota_mb': mb.quota_mb
        }, status=201)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


# ---------------------------------------------------------------------------
# License Endpoints
# ---------------------------------------------------------------------------

@csrf_exempt
def license_activate(request):
    """POST /api/v1/license/activate/"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    license_key = body.get('license_key')
    if not license_key:
        return JsonResponse({'error': 'License key is required'}, status=400)

    from packages.license.service import activate_license
    result = activate_license(license_key)

    if result['success']:
        return JsonResponse({
            'success': True,
            'tier': result['license'].tier,
            'features': result['license'].features,
            'limits': result['license'].limits,
        })
    else:
        return JsonResponse({'error': result['error']}, status=400)


def license_status(request):
    """GET /api/v1/license/status/"""
    from packages.license.models import License
    license_obj = License.objects.filter(is_active=True).first()

    if not license_obj:
        return JsonResponse({
            'activated': False,
            'tier': 'free',
            'features': [],
            'limits': {'websites': 1, 'databases': 1},
        })

    return JsonResponse({
        'activated': True,
        'tier': license_obj.tier,
        'features': license_obj.features,
        'limits': license_obj.limits,
        'expires_at': license_obj.expires_at.isoformat() if license_obj.expires_at else None,
    })


# ---------------------------------------------------------------------------
# User Endpoints
# ---------------------------------------------------------------------------

@csrf_exempt
@api_auth
@require_http_methods(['GET', 'POST'])
def user_endpoint(request):
    """GET (list) or POST (create) /api/v1/users/"""
    if request.method == 'GET':
        if request.api_user.role != 'admin':
            return JsonResponse({'error': 'Admin privileges required'}, status=403)

        users = User.objects.all()
        data = [
            {
                'id': u.id,
                'username': u.username,
                'email': u.email,
                'role': u.role,
                'is_active': u.is_active,
                'created_at': u.created_at.isoformat(),
            }
            for u in users
        ]
        return JsonResponse({'users': data})

    elif request.method == 'POST':
        if request.api_user.role != 'admin':
            return JsonResponse({'error': 'Admin privileges required'}, status=403)

        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON body'}, status=400)

        username = body.get('username', '').strip()
        password = body.get('password', '').strip()
        email = body.get('email', '').strip()
        role = body.get('role', 'user')
        domain = body.get('domain', '').strip().lower()

        if not username or not password:
            return JsonResponse({'error': 'Username and password are required'}, status=400)

        if User.objects.filter(username=username).exists():
            return JsonResponse({'error': f'Username {username} already exists'}, status=409)

        if domain and Website.objects.filter(domain=domain).exists():
            return JsonResponse({'error': f'Domain {domain} already exists'}, status=409)

        user = User.objects.create_user(username=username, email=email, password=password, role=role)

        site_data = None
        if domain:
            doc_root = f"/home/{user.username}/{domain}/public_html"
            site = Website.objects.create(
                owner=user,
                domain=domain,
                doc_root=doc_root,
                framework=body.get('framework', 'none'),
                php_version=body.get('php_version', '8.3'),
            )
            create_vhost(site)
            site_data = {
                'id': site.id,
                'domain': site.domain,
                'doc_root': site.doc_root,
            }
        else:
            try:
                create_user_php_pool(username=user.username, php_version='8.3')
            except Exception:
                pass

        return JsonResponse({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.role,
            'website': site_data,
        }, status=201)

