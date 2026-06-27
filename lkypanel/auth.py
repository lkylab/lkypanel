"""
Authentication helpers for Lite Hosting Panel.

Provides authenticate_user() with brute-force lockout and audit logging.
"""
from datetime import timedelta

from django.utils.timezone import now

from lkypanel.models import AuditLog, User


MAX_ATTEMPTS = 3
LOCKOUT_MINUTES = 15


class AccountLocked(Exception):
    """Raised when a user account is locked due to too many failed login attempts."""

    def __init__(self, remaining_minutes: int):
        self.remaining_minutes = remaining_minutes
        super().__init__(
            f'Account is locked. Try again in {remaining_minutes} minute(s).'
        )


class InvalidCredentials(Exception):
    """Raised when the supplied password does not match the stored hash."""


def authenticate_user(username: str, password: str, ip_address: str) -> tuple[User, bool]:
    """
    Authenticate a user by username and password.

    - Returns (User, is_2fa_required) on success.
    - If is_2fa_required is True, the caller MUST verify the OTP code before 
      fully logging the user in.
    """
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        return None, False

    # Check lockout before verifying password
    if user.locked_until and user.locked_until > now():
        delta = user.locked_until - now()
        remaining = max(1, int(delta.total_seconds() // 60) + (1 if delta.total_seconds() % 60 else 0))
        raise AccountLocked(remaining_minutes=remaining)

    if not user.check_password(password):
        import logging
        logger = logging.getLogger('lkypanel')
        logger.warning(f"Failed login attempt for user '{username}' from IP {ip_address}")
        
        user.failed_logins += 1
        if user.failed_logins >= MAX_ATTEMPTS:
            user.locked_until = now() + timedelta(minutes=LOCKOUT_MINUTES)
        user.save(update_fields=['failed_logins', 'locked_until'])

        from lkypanel.audit import log_action
        log_action(user, 'login_fail', username, ip_address)
        raise InvalidCredentials('Invalid username or password.')

    # Successful primary auth — reset counters
    user.failed_logins = 0
    user.locked_until = None
    user.save(update_fields=['failed_logins', 'locked_until'])

    is_2fa_required = user.is_2fa_enabled and bool(user.otp_secret)

    if not is_2fa_required:
        from lkypanel.audit import log_action
        log_action(user, 'login_success', username, ip_address)

    return user, is_2fa_required
