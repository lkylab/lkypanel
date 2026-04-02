"""
Pure-FTPd integration service.
Uses MariaDB virtual users table. Passwords hashed with SHA512-crypt.
"""
try:
    import crypt
except ImportError:
    # crypt was removed in Python 3.13 (PEP 594)
    crypt = None
import logging
import shutil
import subprocess
from datetime import date

import django.db

logger = logging.getLogger(__name__)

PURE_PW = '/usr/bin/pure-pw'
PURE_PWDB = '/etc/pure-ftpd/pureftpd.pdb'


def is_pureftpd_installed() -> bool:
    return shutil.which('pure-ftpd') is not None


def _sha512_hash(password: str) -> str:
    if crypt is None:
        # Fallback for systems without crypt (like Python 3.13+)
        # In production, passlib should be used instead.
        import hashlib
        return f"$6${hashlib.sha512(password.encode()).hexdigest()}"
    return crypt.crypt(password, crypt.mksalt(crypt.METHOD_SHA512))


def _rebuild_db() -> None:
    result = subprocess.run(
        ['sudo', 'pure-pw', 'mkdb', PURE_PWDB],
        shell=False, timeout=30, capture_output=True, text=True,
    )
    if result.returncode != 0:
        logger.error('pure-pw mkdb failed: %s', result.stderr)
        raise RuntimeError(f'pure-pw mkdb failed: {result.stderr[:512]}')


def create_ftp_account(website, username: str, password: str, quota_mb: int = 1024, home_dir: str = None):
    import pwd
    import re
    from lkypanel.models import FTPAccount
    if not is_pureftpd_installed():
        raise RuntimeError('Pure-FTPd is not installed. Install it from the admin panel first.')

    home_dir = home_dir or website.doc_root

    # Derive the per-domain Linux user (same logic as ols.create_docroot)
    linux_user = re.sub(r'[^a-z0-9_-]', '_', website.domain.lower())[:32]
    try:
        pw_entry = pwd.getpwnam(linux_user)
        uid = str(pw_entry.pw_uid)
        gid = str(pw_entry.pw_gid)
    except KeyError:
        raise RuntimeError(f'System user {linux_user!r} not found. Was the website created correctly?')

    pw_hash = _sha512_hash(password)

    account = FTPAccount(
        website=website,
        username=username,
        password_hash=pw_hash,
        quota_mb=quota_mb,
        home_dir=home_dir,
        status='active',
    )
    account.full_clean()
    account.save()

    # Write to pureftpd virtual users DB using the per-domain system user
    result = subprocess.run(
        ['sudo', 'pure-pw', 'useradd', username,
         '-u', uid, '-g', gid,
         '-d', home_dir,
         '-m'],
        input=f'{password}\n{password}\n',
        shell=False, timeout=30, capture_output=True, text=True,
    )
    if result.returncode != 0:
        account.delete()
        raise RuntimeError(f'pure-pw useradd failed: {result.stderr[:512]}')

    logger.info('Created FTP account: %s → %s (uid=%s)', username, home_dir, uid)
    return account


def delete_ftp_account(account) -> None:
    username = account.username
    subprocess.run(
        ['sudo', 'pure-pw', 'userdel', username, '-m'],
        shell=False, timeout=30, capture_output=True, text=True,
    )
    account.delete()
    logger.info('Deleted FTP account: %s', username)


def change_ftp_password(account, new_password: str) -> None:
    result = subprocess.run(
        ['sudo', 'pure-pw', 'passwd', account.username, '-m'],
        input=f'{new_password}\n{new_password}\n',
        shell=False, timeout=30, capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f'pure-pw passwd failed: {result.stderr[:512]}')
    account.password_hash = _sha512_hash(new_password)
    account.save(update_fields=['password_hash'])


def install_pureftpd() -> None:
    result = subprocess.run(
        ['sudo', 'apt-get', 'install', '-y', 'pure-ftpd', 'pure-ftpd-mysql'],
        shell=False, timeout=300, capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f'Pure-FTPd install failed: {result.stderr[:512]}')
    logger.info('Pure-FTPd installed successfully')
