"""
Audit logging helper for Lite Hosting Panel.
Atomic write to AuditLog for every security-relevant action.
"""
from lkypanel.models import AuditLog, User


def log_action(user, action: str, target: str, ip_address: str) -> AuditLog:
    """
    Create an AuditLog record atomically.

    Args:
        user: User instance or None (anonymous)
        action: short action code e.g. 'login_fail', 'website_delete'
        target: resource identifier e.g. domain name, username
        ip_address: source IP string
    """
    return AuditLog.objects.create(
        user=user if isinstance(user, User) else None,
        action=action,
        target=str(target)[:512],
        ip_address=(ip_address or '0.0.0.0')[:45],
    )
