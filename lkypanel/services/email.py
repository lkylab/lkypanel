"""Email service for managing Postfix and Dovecot."""
import os
import subprocess
from django.conf import settings
from lkypanel.models import MailDomain, MailAccount

CONFIG_DIR = os.path.join(settings.BASE_DIR, 'lkypanel', 'plugins', 'postfix', 'configs')
POSTFIX_DIR = '/etc/postfix'
DOVECOT_DIR = '/etc/dovecot'

def _run_sudo(cmd_list):
    """Run a command with sudo."""
    try:
        subprocess.run(['sudo'] + cmd_list, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {e.stderr.decode()}")
        return False

def sync_email_configs():
    """Deploy SQLite query files to Postfix/Dovecot and restart services."""
    # SQLite Query Files
    cf_files = [
        'sqlite-virtual-mailbox-domains.cf',
        'sqlite-virtual-mailbox-maps.cf',
    ]
    
    for cf in cf_files:
        src = os.path.join(CONFIG_DIR, f"{cf}.tmpl")
        dest = os.path.join(POSTFIX_DIR, cf)
        if os.path.exists(src):
            _run_sudo(['cp', src, dest])
            _run_sudo(['chmod', '644', dest])
            _run_sudo(['chown', 'root:root', dest])

    # Dovecot SQLite config
    src_dovecot = os.path.join(CONFIG_DIR, 'dovecot-sqlite.conf.tmpl')
    dest_dovecot = os.path.join(DOVECOT_DIR, 'dovecot-sqlite.conf.ext')
    if os.path.exists(src_dovecot):
        _run_sudo(['cp', src_dovecot, dest_dovecot])
        _run_sudo(['chmod', '600', dest_dovecot])
        _run_sudo(['chown', 'root:root', dest_dovecot])

    # Main Configs (Optional: only deploy if not already customized by user)
    # For now, we expect the installer to have set these up
    
    # Reload services
    _run_sudo(['systemctl', 'restart', 'postfix'])
    _run_sudo(['systemctl', 'restart', 'dovecot'])
    return True

def add_mail_account(domain_id, email_user, password):
    """Create a mail account and sync."""
    from django.contrib.auth.hashers import make_password
    # Dovecot often expects specific hashes, but we'll use a standard one for now
    # or SHA512-crypt if preferred. Django defaults to PBKDF2/Argon2.
    # Dovecot needs to support the algorithm.
    hashed = make_password(password)
    
    domain = MailDomain.objects.get(id=domain_id)
    account = MailAccount.objects.create(
        domain=domain,
        email_user=email_user,
        password_hash=hashed
    )
    sync_email_configs()
    return account
