"""Log reading service."""
import subprocess
import logging

logger = logging.getLogger(__name__)

LOG_MAP = {
    'ols_error': '/usr/local/lsws/logs/error.log',
    'ols_access': '/usr/local/lsws/logs/access.log',
    'panel': '/var/log/lkypanel/panel.log',
    'fail2ban': '/var/log/fail2ban.log',
    'auth': '/var/log/auth.log',
    'syslog': '/var/log/syslog',
}

def get_log_content(log_id, lines=100, domain=None):
    """Read log content using sudo tail."""
    path = LOG_MAP.get(log_id)
    
    if log_id == 'site_access' and domain:
        path = f'/home/{domain}/logs/access.log'
    elif log_id == 'site_error' and domain:
        path = f'/home/{domain}/logs/error.log'
    
    if not path:
        return f"Log ID {log_id} not found."

    try:
        # Use sudo tail to read logs lkypanel might not own
        cmd = ['sudo', 'tail', '-n', str(lines), path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return result.stdout
        return f"Error reading log: {result.stderr}"
    except Exception as e:
        logger.error(f"Failed to read log {path}: {e}")
        return f"Exception: {e}"
