"""API token authentication."""
import hashlib
from django.utils.timezone import now
from lkypanel.models import APIToken, User


def authenticate_token(request) -> User | None:
    auth = request.META.get('HTTP_AUTHORIZATION', '')
    if not auth.startswith('Bearer '):
        return None
    raw_token = auth[7:].strip()
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    try:
        api_token = APIToken.objects.select_related('user').get(token_hash=token_hash)
        api_token.last_used = now()
        api_token.save(update_fields=['last_used'])
        return api_token.user
    except APIToken.DoesNotExist:
        return None


def api_auth(view_func):
    """Decorator: require valid Bearer token, attach request.api_user."""
    from functools import wraps
    from django.http import JsonResponse

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = authenticate_token(request)
        if user is None:
            return JsonResponse(
                {'error': 'Authentication required', 'code': 'UNAUTHORIZED', 'details': {}},
                status=401,
            )
        request.api_user = user
        return view_func(request, *args, **kwargs)
    return wrapper
