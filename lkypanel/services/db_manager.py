"""
MariaDB/MySQL database management service.
Uses subprocess + mysql CLI (root via unix socket) — same pattern as CyberPanel.
Never uses Django's default SQLite connection for MariaDB operations.
"""
import logging
import re
import secrets
import subprocess

logger = logging.getLogger(__name__)

_NAME_RE = re.compile(r'^[a-zA-Z0-9_]{1,64}$')


def _safe_name(name: str) -> str:
    if not _NAME_RE.match(name):
        raise ValueError(f'Invalid database/user name: {name}')
    return name


def _mysql(sql: str) -> None:
    """Execute a SQL statement via mysql CLI as root (unix socket auth)."""
    result = subprocess.run(
        ['sudo', 'mysql', '-u', 'root', '-e', sql],
        shell=False, timeout=30, capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f'MySQL error: {result.stderr[:512]}')


def create_database(website, db_name: str) -> 'Database':
    from lkypanel.models import Database
    db_name = _safe_name(db_name)
    db_user = _safe_name(db_name + '_u')[:64]
    db_pass = secrets.token_urlsafe(24)

    _mysql(f"CREATE DATABASE `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
    _mysql(f"CREATE USER '{db_user}'@'localhost' IDENTIFIED BY '{db_pass}';")
    _mysql(f"GRANT ALL PRIVILEGES ON `{db_name}`.* TO '{db_user}'@'localhost';")
    _mysql("FLUSH PRIVILEGES;")

    db = Database.objects.create(website=website, db_name=db_name, db_user=db_user)
    logger.info('Created database %s for %s', db_name, website.domain)
    return db


def delete_database(database) -> None:
    db_name = _safe_name(database.db_name)
    db_user = _safe_name(database.db_user)

    _mysql(f"DROP DATABASE IF EXISTS `{db_name}`;")
    _mysql(f"DROP USER IF EXISTS '{db_user}'@'localhost';")
    _mysql("FLUSH PRIVILEGES;")

    database.delete()
    logger.info('Deleted database %s', db_name)
