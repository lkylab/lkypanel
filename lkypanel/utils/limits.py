"""Package limit enforcement utilities."""
from lkypanel.models import User, Website, Database, FTPAccount, MailAccount


def check_limit(user: User, resource: str) -> tuple[bool, str]:
    """
    Check if a user is within their package limits for a given resource.
    Returns (allowed: bool, message: str).
    Admins and users without a package are always allowed.
    """
    if user.role == 'admin' or user.package is None:
        return True, ''

    pkg = user.package

    if resource == 'website':
        count = Website.objects.filter(owner=user).count()
        if count >= pkg.websites_limit:
            return False, f'Website limit reached ({pkg.websites_limit}). Upgrade your package.'

    elif resource == 'database':
        count = Database.objects.filter(website__owner=user).count()
        if count >= pkg.databases_limit:
            return False, f'Database limit reached ({pkg.databases_limit}). Upgrade your package.'

    elif resource == 'ftp':
        count = FTPAccount.objects.filter(website__owner=user).count()
        if count >= pkg.ftp_limit:
            return False, f'FTP account limit reached ({pkg.ftp_limit}). Upgrade your package.'

    elif resource == 'email':
        count = MailAccount.objects.filter(domain__website__owner=user).count()
        if count >= pkg.email_limit:
            return False, f'Email account limit reached ({pkg.email_limit}). Upgrade your package.'

    return True, ''
