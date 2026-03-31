from django.core.exceptions import ValidationError
from lkypanel.models import Website, Database, FTPAccount, MailAccount

def check_resource_limit(user, resource_type):
    """
    Check if a user has exceeded their package limits for a given resource.
    Raises ValidationError if limit is reached.
    """
    if user.role == 'admin':
        return True  # Admins have no limits

    package = user.package
    if not package:
        return True  # No package Assigned = No limits (or default to something?)
        # return False # Or strict: No package = No resources. 
        # Let's assume for now if no package is assigned, they are not limited 
        # (usually only admins don't have packages).

    if resource_type == 'websites':
        count = Website.objects.filter(owner=user).count()
        if count >= package.websites_limit:
            raise ValidationError(f"Website limit reached ({package.websites_limit}). Please upgrade your package.")

    elif resource_type == 'databases':
        # Databases are linked to websites, which are linked to owners
        count = Database.objects.filter(website__owner=user).count()
        if count >= package.databases_limit:
            raise ValidationError(f"Database limit reached ({package.databases_limit}). Please upgrade your package.")

    elif resource_type == 'ftp_accounts':
        count = FTPAccount.objects.filter(website__owner=user).count()
        if count >= package.ftp_limit:
            raise ValidationError(f"FTP account limit reached ({package.ftp_limit}). Please upgrade your package.")

    elif resource_type == 'email_accounts':
        count = MailAccount.objects.filter(domain__website__owner=user).count()
        if count >= package.email_limit:
            raise ValidationError(f"Email account limit reached ({package.email_limit}). Please upgrade your package.")

    return True

def get_user_usage(user):
    """Return a dict of current usage vs limits."""
    package = user.package
    usage = {
        'websites': {'current': Website.objects.filter(owner=user).count(), 'limit': package.websites_limit if package else '∞'},
        'databases': {'current': Database.objects.filter(website__owner=user).count(), 'limit': package.databases_limit if package else '∞'},
        'ftp_accounts': {'current': FTPAccount.objects.filter(website__owner=user).count(), 'limit': package.ftp_limit if package else '∞'},
        'email_accounts': {'current': MailAccount.objects.filter(domain__website__owner=user).count(), 'limit': package.email_limit if package else '∞'},
    }
    return usage
