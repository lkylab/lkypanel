"""
W3Panel v2 — Core Auth
Session-based authentication with brute-force protection.
"""
import secrets
import hashlib
from datetime import timedelta

from django.utils import timezone
from django.http import HttpRequest

from .models import User, AuditLog


MAX_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


def authenticate_user(username: str, password: str, ip_address: str = '') -> tuple:
    """
    Authenticate user with brute-force protection.
    Returns (user, is_2fa_required) or raises ValueError.
    """
    try:
        user = User.objects.get(username=username, is_active=True)
    except User.DoesNotExist:
        raise ValueError('Invalid credentials')

    # Check lockout
    if user.locked_until and user.locked_until > timezone.now():
        remaining = int((user.locked_until - timezone.now()).total_seconds() / 60)
        raise ValueError(f'Account locked. Try again in {remaining} minutes.')

    # Check password
    if not user.check_password(password):
        user.failed_logins += 1
        if user.failed_logins >= MAX_ATTEMPTS:
            user.locked_until = timezone.now() + timedelta(minutes=LOCKOUT_MINUTES)
            user.failed_logins = 0
            _log_action(user, 'login_lockout', username, ip_address)
        user.save(update_fields=['failed_logins', 'locked_until'])
        raise ValueError('Invalid credentials')

    # Successful auth — reset counters
    user.failed_logins = 0
    user.locked_until = None
    user.save(update_fields=['failed_logins', 'locked_until'])

    _log_action(user, 'login_success', username, ip_address)

    # Check if 2FA is required
    is_2fa_required = user.is_2fa_enabled and bool(user.otp_secret)
    return user, is_2fa_required


def create_session(request: HttpRequest, user: User) -> None:
    """Create session for authenticated user."""
    request.session['user_id'] = user.pk
    request.session['role'] = user.role
    request.session.set_expiry(1800)  # 30 minutes


def destroy_session(request: HttpRequest) -> None:
    """Destroy user session."""
    user_id = request.session.get('user_id')
    if user_id:
        try:
            user = User.objects.get(pk=user_id)
            _log_action(user, 'logout', '', request.META.get('REMOTE_ADDR', ''))
        except User.DoesNotExist:
            pass
    request.session.flush()


def verify_2fa(user: User, code: str) -> bool:
    """Verify TOTP 2FA code."""
    if not user.otp_secret:
        return False

    import pyotp
    totp = pyotp.TOTP(user.otp_secret)
    return totp.verify(code, valid_window=1)


def _log_action(user, action, target='', ip_address=''):
    try:
        AuditLog.objects.create(
            user=user,
            action=action,
            target=target,
            ip_address=ip_address or None,
        )
    except Exception:
        pass
