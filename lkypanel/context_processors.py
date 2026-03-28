"""Template context processors for LKYPanel."""
from lkypanel.services.packages import is_plugin_installed


def plugin_states(request):
    """Inject plugin installed states into every template context."""
    return {
        'postfix_installed': is_plugin_installed('postfix'),
        'fail2ban_installed': is_plugin_installed('fail2ban'),
        'mariadb_installed': is_plugin_installed('mariadb'),
        'pureftpd_installed': is_plugin_installed('pureftpd'),
        'restic_installed': is_plugin_installed('restic'),
    }
