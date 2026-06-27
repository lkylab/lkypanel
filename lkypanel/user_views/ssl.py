"""SSL certificate management — user views."""
from datetime import datetime, timezone
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect

from lkypanel.user_views.decorators import login_required, owns_website
from lkypanel.services.ssl import request_certificate


@login_required
@owns_website
@require_http_methods(['GET'])
def ssl_status(request, site_id):
    site = request.panel_website
    ctx = {
        'site': site,
        'ssl_enabled': site.ssl_enabled,
        'active_page': 'websites',
        'panel_user': request.panel_user,
    }
    try:
        cert = site.ssl_certificate
        now = datetime.now(timezone.utc)
        ctx.update({
            'cert_path': cert.cert_path,
            'issued_at': cert.issued_at,
            'expires_at': cert.expires_at,
            'auto_renew': cert.auto_renew,
            'days_left': (cert.expires_at - now).days,
        })
    except Exception:
        pass
    return render(request, 'user/site_ssl.html', ctx)


@login_required
@owns_website
@csrf_protect
@require_http_methods(['POST'])
def request_ssl(request, site_id):
    site = request.panel_website
    try:
        cert = request_certificate(site)
    except ValueError as e:
        return JsonResponse({'error': str(e), 'code': 'DNS_CHECK_FAILED', 'details': {}}, status=400)
    except RuntimeError as e:
        return JsonResponse({'error': str(e), 'code': 'CERTBOT_FAILED', 'details': {}}, status=500)

    return JsonResponse({
        'cert_path': cert.cert_path,
        'expires_at': cert.expires_at.isoformat(),
    }, status=201)
