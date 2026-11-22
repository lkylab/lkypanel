"""
W3Panel v2 — Core Middleware
License enforcement, port isolation, role enforcement, rate limiting.
"""
import time
import json
import hashlib
import logging
from pathlib import Path
from collections import deque
from functools import wraps

from django.http import HttpResponseForbidden, JsonResponse
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger('w3panel.middleware')

ADMIN_PORT = 2087
USER_PORT = 2083
API_PORT = 2080
ADMIN_PREFIX = '/admin/'
USER_PREFIX = '/user/'
API_PREFIX = '/api/v1/'


# ---------------------------------------------------------------------------
# License Enforcement Middleware
# ---------------------------------------------------------------------------

class LicenseEnforcementMiddleware:
    """
    Checks license status on every request.
    Reads cached status from /run/w3panel/license_status.
    Whitelists: login pages, static files, license activation.
    """

    WHITELIST_PATHS = [
        '/',
        '/login/',
        '/admin/login/',
        '/user/login/',
        '/user/sso/',
        '/sso/',
        '/api/v1/license/activate/',
        '/static/',
        '/favicon.ico',
    ]

    def __init__(self, get_response):
        self.get_response = get_response
        self._status_cache = None
        self._cache_time = 0
        self._cache_ttl = 30  # seconds

    def __call__(self, request):
        # Skip whitelist paths
        if any(request.path.startswith(p) for p in self.WHITELIST_PATHS):
            return self.get_response(request)

        # Check license status
        status = self._get_license_status()
        if status and not status.get('valid', False):
            error = status.get('error', 'License invalid')
            code = status.get('code', 'LICENSE_INVALID')

            # Grace period: 7 days read-only
            if status.get('grace_days_remaining', 0) > 0:
                if request.method != 'GET':
                    return JsonResponse({
                        'error': f'License expired. Read-only mode for {status["grace_days_remaining"]} days.',
                        'code': 'LICENSE_GRACE_PERIOD',
                    }, status=403)
            else:
                return JsonResponse({
                    'error': error,
                    'code': code,
                }, status=403)

        return self.get_response(request)

    def _get_license_status(self):
        """Read cached license status from file."""
        now = time.time()
        if self._status_cache and (now - self._cache_time) < self._cache_ttl:
            return self._status_cache

        status_file = Path('/run/w3panel/license_status')
        if status_file.exists():
            try:
                self._status_cache = json.loads(status_file.read_text())
                self._cache_time = now
            except (json.JSONDecodeError, IOError):
                self._status_cache = None
        else:
            self._status_cache = None

        return self._status_cache


def get_request_port(request):
    """Accurately determine the server port from environment, META, or Host header."""
    import os
    env_port = os.environ.get('SERVER_PORT')
    if env_port:
        try:
            return int(env_port)
        except ValueError:
            pass

    meta_port = request.META.get('SERVER_PORT')
    if meta_port:
        try:
            return int(meta_port)
        except (ValueError, TypeError):
            pass

    host = request.get_host()
    if ':' in host:
        try:
            return int(host.split(':')[-1])
        except ValueError:
            pass

    return 0


def get_session_cookie_name(request):
    """Return dedicated session cookie name per port to prevent tab/session collisions."""
    from django.conf import settings
    port = get_request_port(request)
    if port in (USER_PORT, 12083):
        return 'w3p_client_session'
    elif port in (ADMIN_PORT, 12087):
        return 'w3p_host_session'
    return getattr(settings, 'SESSION_COOKIE_NAME', 'w3p_session')


# ---------------------------------------------------------------------------
# Port Session Middleware (Dedicated Session Cookies per Port)
# ---------------------------------------------------------------------------

class PortSessionMiddleware:
    """
    Port-isolated Session Middleware.
    Ensures Port 2083 (W3Client) and Port 2087 (W3Host) use completely independent session cookies
    (w3p_client_session vs w3p_host_session) so they never collide or overwrite each other in the browser.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        from importlib import import_module
        from django.conf import settings
        engine = import_module(settings.SESSION_ENGINE)
        self.SessionStore = engine.SessionStore

    def __call__(self, request):
        from django.conf import settings
        from django.utils.cache import patch_vary_headers

        cookie_name = get_session_cookie_name(request)
        request._session_cookie_name = cookie_name
        session_key = request.COOKIES.get(cookie_name)
        request.session = self.SessionStore(session_key)

        response = self.get_response(request)

        try:
            accessed = request.session.accessed
            modified = request.session.modified
            empty = request.session.is_empty()
        except AttributeError:
            return response

        if accessed:
            patch_vary_headers(response, ('Cookie',))

        if modified or getattr(settings, 'SESSION_SAVE_EVERY_REQUEST', False):
            if empty:
                if session_key:
                    response.delete_cookie(
                        cookie_name,
                        path=getattr(settings, 'SESSION_COOKIE_PATH', '/'),
                        domain=getattr(settings, 'SESSION_COOKIE_DOMAIN', None),
                        samesite=getattr(settings, 'SESSION_COOKIE_SAMESITE', 'Lax'),
                    )
            else:
                from django.utils.http import http_date
                if request.session.get_expire_at_browser_close():
                    max_age = None
                    expires = None
                else:
                    max_age = request.session.get_expiry_age()
                    expires_time = time.time() + max_age
                    expires = http_date(expires_time)

                if response.status_code < 500:
                    request.session.save()
                    response.set_cookie(
                        cookie_name,
                        request.session.session_key,
                        max_age=max_age,
                        expires=expires,
                        domain=getattr(settings, 'SESSION_COOKIE_DOMAIN', None),
                        path=getattr(settings, 'SESSION_COOKIE_PATH', '/'),
                        secure=getattr(settings, 'SESSION_COOKIE_SECURE', False) or None,
                        httponly=getattr(settings, 'SESSION_COOKIE_HTTPONLY', True) or None,
                        samesite=getattr(settings, 'SESSION_COOKIE_SAMESITE', 'Lax'),
                    )

        return response


# ---------------------------------------------------------------------------
# Port Isolation Middleware
# ---------------------------------------------------------------------------

class PortIsolationMiddleware:
    """Dynamically routes URLConf and isolates namespaces per port."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        port = get_request_port(request)

        # Dynamically route URL configuration per port
        from django.urls import set_urlconf
        if port in (USER_PORT, 12083):
            request.urlconf = 'panel.urls_user'
            set_urlconf('panel.urls_user')
        elif port in (ADMIN_PORT, 12087):
            request.urlconf = 'panel.urls_admin'
            set_urlconf('panel.urls_admin')

        path = request.path_info

        if port in (USER_PORT, 12083) and path.startswith(ADMIN_PREFIX):
            return HttpResponseForbidden('Admin routes not available on this port.')

        return self.get_response(request)


# ---------------------------------------------------------------------------
# Role Enforcement Middleware
# ---------------------------------------------------------------------------

class RoleEnforcementMiddleware:
    """Blocks wrong-role sessions per port without destructive session flushing."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info

        # Whitelist public auth and SSO endpoints so login and 1-click autologin work seamlessly
        if (path.startswith('/user/sso/') or path.startswith('/sso/') or
            path.startswith('/static/') or path.startswith('/favicon.ico') or
            path in ('/login/', '/user/login/', '/admin/login/', '/logout/', '/user/logout/', '/admin/logout/')):
            return self.get_response(request)

        port = get_request_port(request)
        uid = request.session.get('user_id')
        request.panel_user = None

        if not uid:
            from django.shortcuts import redirect
            if (port in (ADMIN_PORT, 12087)) and not path.startswith(API_PREFIX):
                return redirect('admin_login')
            elif (port in (USER_PORT, 12083)) and not path.startswith(API_PREFIX):
                return redirect('user_login')
            return self.get_response(request)

        from .models import User
        try:
            user = User.objects.get(pk=uid, is_active=True)
        except User.DoesNotExist:
            user = None

        if user:
            request.panel_user = user
            role = user.role

            if port in (ADMIN_PORT, 12087):
                # Non-admin can only access /user/ routes on port 2087
                if role not in ('admin', 'reseller') and not path.startswith(USER_PREFIX):
                    _log_unauthorized(user, request)
                    from django.shortcuts import redirect
                    return redirect('admin_login')

            elif port in (USER_PORT, 12083):
                # Only regular users on port 2083, unless impersonated by admin
                if role in ('admin', 'reseller') and not request.session.get('impersonated_by'):
                    _log_unauthorized(user, request)
                    from django.shortcuts import redirect
                    return redirect('user_login')

        return self.get_response(request)


# ---------------------------------------------------------------------------
# API Rate Limit Middleware
# ---------------------------------------------------------------------------

class APIRateLimitMiddleware:
    """Rate limit /api/v1/* endpoints. Configurable per-user limits."""

    def __init__(self, get_response):
        self.get_response = get_response
        self._requests = {}  # token_hash -> deque of timestamps
        self._default_limit = 50  # requests per minute

    def __call__(self, request):
        if not request.path.startswith(API_PREFIX):
            return self.get_response(request)

        # Get token from Authorization header
        auth = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth.startswith('Bearer '):
            return self.get_response(request)

        token_hash = hashlib.sha256(auth[7:].encode()).hexdigest()
        now = time.time()
        window = 60  # 1 minute

        # Get or create request history
        if token_hash not in self._requests:
            self._requests[token_hash] = deque()

        timestamps = self._requests[token_hash]

        # Remove old entries
        while timestamps and timestamps[0] < now - window:
            timestamps.popleft()

        # Check limit
        limit = self._get_limit(token_hash)
        if len(timestamps) >= limit:
            return JsonResponse({
                'error': 'Rate limit exceeded',
                'code': 'RATE_LIMIT_EXCEEDED',
                'retry_after': int(timestamps[0] + window - now),
            }, status=429, headers={
                'Retry-After': str(int(timestamps[0] + window - now)),
                'X-RateLimit-Limit': str(limit),
                'X-RateLimit-Remaining': '0',
            })

        # Record request
        timestamps.append(now)

        response = self.get_response(request)
        response['X-RateLimit-Limit'] = str(limit)
        response['X-RateLimit-Remaining'] = str(max(0, limit - len(timestamps)))
        return response

    def _get_limit(self, token_hash):
        """Get rate limit for token. Configurable in admin settings."""
        try:
            from .models import SystemSetting
            return int(SystemSetting.get('api_rate_limit', self._default_limit))
        except (ValueError, ImportError):
            return self._default_limit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _log_unauthorized(user, request):
    try:
        from .models import AuditLog
        from .utils import get_client_ip
        AuditLog.objects.create(
            user=user,
            action='unauthorized_port_access',
            target=request.path_info,
            ip_address=get_client_ip(request),
        )
    except Exception:
        logger.exception('Failed to log unauthorized access')


# ---------------------------------------------------------------------------
# License Feature Gate Decorator
# ---------------------------------------------------------------------------

def require_license(feature):
    """
    Decorator: require a specific license feature.
    
    Usage:
        @require_license('api')
        def my_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            from .models import SystemSetting
            import json

            # Check license features
            features_json = SystemSetting.get('license_features', '[]')
            try:
                features = json.loads(features_json)
            except (json.JSONDecodeError, TypeError):
                features = []

            if feature not in features:
                return JsonResponse({
                    'error': f'This feature requires a license ({feature})',
                    'code': 'FEATURE_NOT_LICENSED',
                }, status=403)

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
