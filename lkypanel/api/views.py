"""REST API viewsets — JSON responses, token auth, ownership enforcement."""
import hashlib
import json
import secrets

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from lkypanel.api.auth import api_auth
from lkypanel.models import Website, User, FTPAccount, Database, GitRepo, SSLCertificate, APIToken


def _err(msg, code, status=400, details=None):
    return JsonResponse({'error': msg, 'code': code, 'details': details or {}}, status=status)


def _owns(user, website):
    return user.role == 'admin' or website.owner_id == user.pk


# ── Websites ──────────────────────────────────────────────────────────────

@csrf_exempt
@api_auth
@require_http_methods(['GET', 'POST'])
def websites(request):
    if request.method == 'GET':
        qs = Website.objects.all() if request.api_user.role == 'admin' \
            else Website.objects.filter(owner=request.api_user)
        return JsonResponse({'websites': list(qs.values('id', 'domain', 'doc_root', 'php_version', 'ssl_enabled'))})

    data = json.loads(request.body)
    if request.api_user.role != 'admin':
        return _err('Admin only', 'FORBIDDEN', 403)
    from lkypanel.admin_views.websites import create_website as _cw
    # reuse service logic inline
    domain = data.get('domain', '').strip().lower()
    owner_id = data.get('owner_id', request.api_user.pk)
    php_version = data.get('php_version', '8.1')
    if Website.objects.filter(domain=domain).exists():
        return _err('Domain already exists', 'DUPLICATE_DOMAIN')
    try:
        owner = User.objects.get(pk=owner_id)
        site = Website(owner=owner, domain=domain, php_version=php_version)
        site.full_clean()
        site.save()
        from lkypanel.services.ols import create_docroot, write_vhost_config, reload_ols
        create_docroot(domain)
        write_vhost_config(domain, php_version)
        reload_ols()
    except Exception as e:
        return _err(str(e), 'CREATE_FAILED', 400)
    return JsonResponse({'id': site.pk, 'domain': site.domain}, status=201)


@csrf_exempt
@api_auth
@require_http_methods(['GET', 'PUT', 'DELETE'])
def website_detail(request, site_id):
    try:
        site = Website.objects.get(pk=site_id)
    except Website.DoesNotExist:
        return _err('Not found', 'NOT_FOUND', 404)
    if not _owns(request.api_user, site):
        return _err('Forbidden', 'FORBIDDEN', 403)

    if request.method == 'GET':
        return JsonResponse({'id': site.pk, 'domain': site.domain, 'doc_root': site.doc_root,
                             'php_version': site.php_version, 'ssl_enabled': site.ssl_enabled})
    if request.method == 'DELETE':
        if request.api_user.role != 'admin':
            return _err('Admin only', 'FORBIDDEN', 403)
        from lkypanel.services.ols import delete_vhost_config, reload_ols
        delete_vhost_config(site.domain)
        site.delete()
        reload_ols()
        return JsonResponse({'deleted': site.domain})
    if request.method == 'PUT':
        data = json.loads(request.body)
        site.php_version = data.get('php_version', site.php_version)
        site.save(update_fields=['php_version'])
        from lkypanel.services.ols import write_vhost_config, reload_ols
        write_vhost_config(site.domain, site.php_version, ssl=site.ssl_enabled)
        reload_ols()
        return JsonResponse({'id': site.pk, 'php_version': site.php_version})


# ── Users (admin only) ────────────────────────────────────────────────────

@csrf_exempt
@api_auth
@require_http_methods(['GET', 'POST'])
def users(request):
    if request.api_user.role != 'admin':
        return _err('Admin only', 'FORBIDDEN', 403)
    if request.method == 'GET':
        return JsonResponse({'users': list(User.objects.values('id', 'username', 'email', 'role', 'is_active'))})
    data = json.loads(request.body)
    try:
        u = User.objects.create_user(
            username=data['username'], email=data['email'],
            password=data['password'], role=data.get('role', 'user'))
    except Exception as e:
        return _err(str(e), 'CREATE_FAILED')
    return JsonResponse({'id': u.pk, 'username': u.username}, status=201)


# ── FTP ───────────────────────────────────────────────────────────────────

@csrf_exempt
@api_auth
@require_http_methods(['GET', 'POST'])
def ftp_accounts(request):
    if request.method == 'GET':
        qs = FTPAccount.objects.filter(website__owner=request.api_user) \
            if request.api_user.role != 'admin' else FTPAccount.objects.all()
        return JsonResponse({'ftp_accounts': list(qs.values('id', 'username', 'quota_mb', 'home_dir', 'status'))})
    data = json.loads(request.body)
    try:
        site = Website.objects.get(pk=data['site_id'])
    except Website.DoesNotExist:
        return _err('Website not found', 'NOT_FOUND', 404)
    if not _owns(request.api_user, site):
        return _err('Forbidden', 'FORBIDDEN', 403)
    from lkypanel.services.ftp import create_ftp_account
    try:
        acc = create_ftp_account(site, data['username'], data['password'], int(data.get('quota_mb', 1024)))
    except Exception as e:
        return _err(str(e), 'FTP_CREATE_FAILED')
    return JsonResponse({'id': acc.pk, 'username': acc.username}, status=201)


# ── SSL ───────────────────────────────────────────────────────────────────

@csrf_exempt
@api_auth
@require_http_methods(['GET', 'POST'])
def ssl_certs(request):
    if request.method == 'GET':
        qs = SSLCertificate.objects.filter(website__owner=request.api_user) \
            if request.api_user.role != 'admin' else SSLCertificate.objects.all()
        return JsonResponse({'ssl_certs': list(qs.values('id', 'cert_path', 'issued_at', 'expires_at', 'auto_renew'))})
    data = json.loads(request.body)
    try:
        site = Website.objects.get(pk=data['site_id'])
    except Website.DoesNotExist:
        return _err('Website not found', 'NOT_FOUND', 404)
    if not _owns(request.api_user, site):
        return _err('Forbidden', 'FORBIDDEN', 403)
    from lkypanel.services.ssl import request_certificate
    try:
        cert = request_certificate(site)
    except ValueError as e:
        return _err(str(e), 'DNS_CHECK_FAILED')
    except RuntimeError as e:
        return _err(str(e), 'CERTBOT_FAILED', 500)
    return JsonResponse({'cert_path': cert.cert_path, 'expires_at': cert.expires_at.isoformat()}, status=201)


# ── Git ───────────────────────────────────────────────────────────────────

@csrf_exempt
@api_auth
@require_http_methods(['GET', 'POST'])
def git_repos(request):
    if request.method == 'GET':
        qs = GitRepo.objects.filter(website__owner=request.api_user) \
            if request.api_user.role != 'admin' else GitRepo.objects.all()
        return JsonResponse({'repos': list(qs.values('id', 'repo_url', 'branch', 'auth_type', 'git_user'))})
    data = json.loads(request.body)
    try:
        site = Website.objects.get(pk=data['site_id'])
    except Website.DoesNotExist:
        return _err('Website not found', 'NOT_FOUND', 404)
    if not _owns(request.api_user, site):
        return _err('Forbidden', 'FORBIDDEN', 403)
    from lkypanel.services.git import clone_repo
    try:
        clone_repo(site, data['repo_url'], data.get('branch', 'main'),
                   data.get('auth_type', 'none'), data.get('credentials'))
    except RuntimeError as e:
        return _err(str(e), 'GIT_CLONE_FAILED', 500)
    return JsonResponse({'linked': data['repo_url']}, status=201)


# ── Databases ─────────────────────────────────────────────────────────────

@csrf_exempt
@api_auth
@require_http_methods(['GET', 'POST'])
def databases(request):
    if request.method == 'GET':
        qs = Database.objects.filter(website__owner=request.api_user) \
            if request.api_user.role != 'admin' else Database.objects.all()
        return JsonResponse({'databases': list(qs.values('id', 'db_name', 'db_user', 'created_at'))})
    data = json.loads(request.body)
    try:
        site = Website.objects.get(pk=data['site_id'])
    except Website.DoesNotExist:
        return _err('Website not found', 'NOT_FOUND', 404)
    if not _owns(request.api_user, site):
        return _err('Forbidden', 'FORBIDDEN', 403)
    from lkypanel.services.db_manager import create_database
    try:
        db = create_database(site, data['db_name'])
    except Exception as e:
        return _err(str(e), 'DB_CREATE_FAILED')
    return JsonResponse({'id': db.pk, 'db_name': db.db_name}, status=201)


# ── API Token management ──────────────────────────────────────────────────

@csrf_exempt
@api_auth
@require_http_methods(['POST'])
def create_token(request):
    data = json.loads(request.body)
    name = data.get('name', 'default')
    raw = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    APIToken.objects.create(user=request.api_user, token_hash=token_hash, name=name)
    # Raw token shown once — never stored
    return JsonResponse({'token': raw, 'name': name}, status=201)
