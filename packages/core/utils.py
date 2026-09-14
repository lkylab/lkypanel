"""
W3Panel v2 — Core Utilities
"""
from django.http import HttpRequest


def get_client_ip(request: HttpRequest) -> str:
    """Get client IP address from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')
