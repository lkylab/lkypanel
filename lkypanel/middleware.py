"""
Middleware for Lite Hosting Panel.

PortIsolationMiddleware  — blocks wrong-namespace routes per port
RoleEnforcementMiddleware — blocks wrong-role sessions per port
APIRateLimitMiddleware   — sliding window rate limit for /api/v1/
"""
import time
import threading
from collections import deque

from django.http import HttpResponseForbidden, JsonResponse
from lkypanel.utils.ip import get_client_ip

ADMIN_PORT = 2087
USER_PORT = 2083
ADMIN_PREFIX = '/admin/'
USER_PREFIX = '/user/'
API_PREFIX = '/api/v1/'

# ---------------------------------------------------------------------------
# Port Isolation
# ---------------------------------------------------------------------------

class PortIsolationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        port = int(request.META.get('SERVER_PORT', 0))
        path = request.path_info

        if port == USER_PORT and path.startswith(ADMIN_PREFIX):
            return HttpResponseForbidden('Admin routes not available on this port.')
        if port == ADMIN_PORT and path.startswith(USER_PREFIX):
            return HttpResponseForbidden('User routes not available on this port.')

        return self.get_response(request)


# ---------------------------------------------------------------------------
# Role Enforcement
# ---------------------------------------------------------------------------

class RoleEnforcementMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        port = int(request.META.get('SERVER_PORT', 0))
        user = getattr(request, 'user', None)

        if user and user.is_authenticated:
            role = getattr(user, 'role', None)
            if port == ADMIN_PORT and role != 'admin':
                request.session.flush()
                _log_unauthorized(user, request)
                return HttpResponseForbidden('Admin access only on this port.')
            if port == USER_PORT and role != 'user':
                request.session.flush()
                _log_unauthorized(user, request)
                return HttpResponseForbidden('User access only on this port.')

        return self.get_response(request)


def _log_unauthorized(user, request):
    try:
        from lkypanel.audit import log_action
        log_action(user, 'unauthorized_port_access', request.path_info,
                   get_client_ip(request))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# API Rate Limiting — in-memory sliding window
# ---------------------------------------------------------------------------

_rate_lock = threading.Lock()
_rate_windows: dict[str, deque] = {}

RATE_LIMIT = 30       # requests
RATE_WINDOW = 60       # seconds


class APIRateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path_info.startswith(API_PREFIX):
            return self.get_response(request)

        token_hash = self._get_token_hash(request)
        if token_hash and self._is_rate_limited(token_hash):
            return JsonResponse(
                {'error': 'Rate limit exceeded', 'code': 'RATE_LIMIT_EXCEEDED', 'details': {}},
                status=429,
            )

        return self.get_response(request)

    def _get_token_hash(self, request):
        auth = request.META.get('HTTP_AUTHORIZATION', '')
        if auth.startswith('Bearer '):
            import hashlib
            return hashlib.sha256(auth[7:].encode()).hexdigest()
        return None

    def _is_rate_limited(self, token_hash: str) -> bool:
        now = time.monotonic()
        with _rate_lock:
            window = _rate_windows.setdefault(token_hash, deque())
            # Remove timestamps outside the window
            while window and window[0] < now - RATE_WINDOW:
                window.popleft()
            if len(window) >= RATE_LIMIT:
                return True
            window.append(now)
            return False
