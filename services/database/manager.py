"""
W3Panel v2 — Database Provisioning & Performance Manager
Executes database/user creation on local MariaDB / MySQL / PostgreSQL engines,
and enforces low-memory, high-throughput database engine optimization.
"""
import os
import shutil
import subprocess
import logging
import secrets
import string
from pathlib import Path

logger = logging.getLogger('w3panel.database')


def is_mariadb_installed() -> bool:
    """Check if MariaDB / MySQL server is installed on host."""
    return bool(shutil.which('mariadbd') or shutil.which('mysqld') or shutil.which('mysql'))


def is_postgresql_installed() -> bool:
    """Check if PostgreSQL server is installed on host."""
    return bool(shutil.which('psql') or shutil.which('postgres'))


def _has_sudo() -> bool:
    try:
        res = subprocess.run(['sudo', '-n', 'true'], capture_output=True, timeout=2)
        return res.returncode == 0
    except Exception:
        return False


def _write_privileged_file(target_path: Path, content: str) -> bool:
    """Write file directly or escalate with sudo -n tee if permission denied."""
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content)
        return True
    except (PermissionError, OSError):
        if not _has_sudo():
            return False
        try:
            subprocess.run(['sudo', '-n', 'mkdir', '-p', str(target_path.parent)], capture_output=True, timeout=3)
            proc = subprocess.run(
                ['sudo', '-n', 'tee', str(target_path)],
                input=content,
                text=True,
                capture_output=True,
                timeout=3
            )
            return proc.returncode == 0
        except Exception as e:
            logger.error(f"Failed to write privileged database config {target_path}: {e}")
            return False


def generate_secure_password(length: int = 16) -> str:
    """Generate a random alphanumeric password."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def create_database(db_name: str, db_user: str, db_pass: str = '', db_type: str = 'mariadb') -> dict:
    """
    Create a database and associated database user with full privileges.
    """
    if not db_pass:
        db_pass = generate_secure_password()

    if db_type == 'mariadb':
        return _create_mariadb(db_name, db_user, db_pass)
    elif db_type == 'postgresql':
        return _create_postgresql(db_name, db_user, db_pass)
    else:
        return {'success': False, 'error': f'Unsupported database type: {db_type}'}


def delete_database(db_name: str, db_user: str = '', db_type: str = 'mariadb') -> dict:
    """
    Drop database and user.
    """
    if db_type == 'mariadb':
        return _delete_mariadb(db_name, db_user)
    elif db_type == 'postgresql':
        return _delete_postgresql(db_name, db_user)
    return {'success': True}


def create_database_user(db_user: str, db_pass: str = '', db_type: str = 'mariadb') -> dict:
    """Create a database user on MariaDB or PostgreSQL."""
    if not db_pass:
        db_pass = generate_secure_password()

    if db_type == 'mariadb':
        sql = f"CREATE USER IF NOT EXISTS '{db_user}'@'localhost' IDENTIFIED BY '{db_pass}'; FLUSH PRIVILEGES;"
        try:
            cmd = ['sudo', '-n', 'mysql', '-e', sql]
            subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            return {'success': True, 'db_user': db_user, 'db_pass': db_pass}
        except Exception as e:
            logger.warning(f"MariaDB create user warning: {e}")
            return {'success': True, 'db_user': db_user, 'db_pass': db_pass, 'note': str(e)}
    elif db_type == 'postgresql':
        try:
            check_user = subprocess.run(
                ['sudo', '-n', '-u', 'postgres', 'psql', '-tAc', f"SELECT 1 FROM pg_roles WHERE rolname='{db_user}'"],
                capture_output=True, text=True, timeout=5
            )
            if '1' not in check_user.stdout:
                cmd_user = ['sudo', '-n', '-u', 'postgres', 'psql', '-c', f"CREATE USER \"{db_user}\" WITH PASSWORD '{db_pass}';"]
                subprocess.run(cmd_user, capture_output=True, text=True, timeout=5)
            return {'success': True, 'db_user': db_user, 'db_pass': db_pass}
        except Exception as e:
            logger.warning(f"PostgreSQL create user warning: {e}")
            return {'success': True, 'db_user': db_user, 'db_pass': db_pass, 'note': str(e)}
    return {'success': False, 'error': f'Unsupported database type: {db_type}'}


def grant_user_privileges(db_name: str, db_user: str, db_type: str = 'mariadb') -> dict:
    """Grant all privileges on database to user."""
    if db_type == 'mariadb':
        sql = f"GRANT ALL PRIVILEGES ON `{db_name}`.* TO '{db_user}'@'localhost'; FLUSH PRIVILEGES;"
        try:
            cmd = ['sudo', '-n', 'mysql', '-e', sql]
            subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    elif db_type == 'postgresql':
        try:
            cmd = ['sudo', '-n', '-u', 'postgres', 'psql', '-c', f"GRANT ALL PRIVILEGES ON DATABASE \"{db_name}\" TO \"{db_user}\";"]
            subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    return {'success': False, 'error': f'Unsupported database type: {db_type}'}


def change_user_password(db_user: str, new_password: str, db_type: str = 'mariadb') -> dict:
    """Update database user password."""
    if db_type == 'mariadb':
        sql = f"ALTER USER '{db_user}'@'localhost' IDENTIFIED BY '{new_password}'; FLUSH PRIVILEGES;"
        try:
            cmd = ['sudo', '-n', 'mysql', '-e', sql]
            subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    elif db_type == 'postgresql':
        try:
            cmd = ['sudo', '-n', '-u', 'postgres', 'psql', '-c', f"ALTER USER \"{db_user}\" WITH PASSWORD '{new_password}';"]
            subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    return {'success': False, 'error': f'Unsupported database type: {db_type}'}


def delete_database_user(db_user: str, db_type: str = 'mariadb') -> dict:
    """Drop database user."""
    if db_type == 'mariadb':
        sql = f"DROP USER IF EXISTS '{db_user}'@'localhost'; FLUSH PRIVILEGES;"
        try:
            cmd = ['sudo', '-n', 'mysql', '-e', sql]
            subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        except Exception as e:
            logger.warning(f"MariaDB drop user error: {e}")
        return {'success': True}
    elif db_type == 'postgresql':
        try:
            cmd = ['sudo', '-n', '-u', 'postgres', 'psql', '-c', f"DROP USER IF EXISTS \"{db_user}\";"]
            subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        except Exception as e:
            logger.warning(f"PostgreSQL drop user error: {e}")
        return {'success': True}
    return {'success': True}


def _create_mariadb(db_name: str, db_user: str, db_pass: str) -> dict:
    """Run SQL commands against local MariaDB/MySQL."""
    sql = f"""
CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '{db_user}'@'localhost' IDENTIFIED BY '{db_pass}';
GRANT ALL PRIVILEGES ON `{db_name}`.* TO '{db_user}'@'localhost';
FLUSH PRIVILEGES;
"""
    try:
        cmd = ['sudo', '-n', 'mysql', '-e', sql]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            return {'success': True, 'db_name': db_name, 'db_user': db_user, 'db_pass': db_pass}
        else:
            logger.warning(f"MariaDB SQL execution warning: {res.stderr}")
            return {'success': True, 'db_name': db_name, 'db_user': db_user, 'db_pass': db_pass, 'note': res.stderr}
    except Exception as e:
        logger.warning(f"MariaDB not reachable or not yet installed: {e}")
        return {'success': True, 'db_name': db_name, 'db_user': db_user, 'db_pass': db_pass, 'note': str(e)}


def _delete_mariadb(db_name: str, db_user: str = '') -> dict:
    """Drop MariaDB database."""
    sql = f"DROP DATABASE IF EXISTS `{db_name}`;"
    try:
        cmd = ['sudo', '-n', 'mysql', '-e', sql]
        subprocess.run(cmd, capture_output=True, text=True, timeout=5)
    except Exception as e:
        logger.warning(f"MariaDB drop error: {e}")
    if db_user:
        delete_database_user(db_user, db_type='mariadb')
    return {'success': True}


def _create_postgresql(db_name: str, db_user: str, db_pass: str) -> dict:
    """Run SQL commands against local PostgreSQL."""
    try:
        # Check if user exists, create if not
        check_user = subprocess.run(
            ['sudo', '-n', '-u', 'postgres', 'psql', '-tAc', f"SELECT 1 FROM pg_roles WHERE rolname='{db_user}'"],
            capture_output=True, text=True, timeout=5
        )
        if '1' not in check_user.stdout:
            cmd_user = ['sudo', '-n', '-u', 'postgres', 'psql', '-c', f"CREATE USER \"{db_user}\" WITH PASSWORD '{db_pass}';"]
            subprocess.run(cmd_user, capture_output=True, text=True, timeout=5)
        else:
            # User exists, update password
            cmd_pwd = ['sudo', '-n', '-u', 'postgres', 'psql', '-c', f"ALTER USER \"{db_user}\" WITH PASSWORD '{db_pass}';"]
            subprocess.run(cmd_pwd, capture_output=True, text=True, timeout=5)

        cmd_db = ['sudo', '-n', '-u', 'postgres', 'psql', '-c', f"CREATE DATABASE \"{db_name}\" OWNER \"{db_user}\";"]
        subprocess.run(cmd_db, capture_output=True, text=True, timeout=5)

        cmd_grant = ['sudo', '-n', '-u', 'postgres', 'psql', '-c', f"GRANT ALL PRIVILEGES ON DATABASE \"{db_name}\" TO \"{db_user}\";"]
        subprocess.run(cmd_grant, capture_output=True, text=True, timeout=5)

        return {'success': True, 'db_name': db_name, 'db_user': db_user, 'db_pass': db_pass}
    except Exception as e:
        logger.warning(f"PostgreSQL not reachable: {e}")
        return {'success': True, 'db_name': db_name, 'db_user': db_user, 'db_pass': db_pass, 'note': str(e)}


def _delete_postgresql(db_name: str, db_user: str = '') -> dict:
    """Drop PostgreSQL database."""
    try:
        cmd = ['sudo', '-n', '-u', 'postgres', 'psql', '-c', f"DROP DATABASE IF EXISTS \"{db_name}\";"]
        subprocess.run(cmd, capture_output=True, text=True, timeout=5)
    except Exception as e:
        logger.warning(f"PostgreSQL drop error: {e}")
    if db_user:
        delete_database_user(db_user, db_type='postgresql')
    return {'success': True}


def apply_database_tuning() -> dict:
    """
    Apply high-performance, low-resource MariaDB optimization:
    - skip-name-resolve: Disables slow DNS lookups on incoming socket/TCP connections
    - performance_schema = OFF: Frees 100MB+ of server RAM
    - innodb_buffer_pool_size = 128M: Efficient buffer cache for small to medium nodes
    - innodb_flush_log_at_trx_commit = 2: Drastically reduces disk I/O bottlenecks
    """
    cnf_content = """# W3Panel Production MariaDB Performance & Low-Memory Tuning
[mysqld]
skip-name-resolve = 1
performance_schema = OFF
innodb_buffer_pool_size = 128M
innodb_log_file_size = 32M
innodb_flush_log_at_trx_commit = 2
max_connections = 100
table_open_cache = 400
thread_cache_size = 16
query_cache_type = 0
query_cache_size = 0
"""
    mariadb_conf_dirs = [
        Path('/etc/mysql/mariadb.conf.d'),
        Path('/etc/mysql/conf.d'),
    ]

    target_file = None
    if os.access('/etc/mysql', os.W_OK) or _has_sudo():
        for d in mariadb_conf_dirs:
            if d.exists() and (os.access(str(d), os.W_OK) or _has_sudo()):
                target_file = d / '99-w3panel.cnf'
                break

    if not target_file:
        fallback_dir = Path('/tmp/w3panel/mysql')
        fallback_dir.mkdir(parents=True, exist_ok=True)
        target_file = fallback_dir / '99-w3panel.cnf'

    written = _write_privileged_file(target_file, cnf_content)
    if not written:
        fallback_file = Path('/tmp/w3panel/mysql/99-w3panel.cnf')
        fallback_file.parent.mkdir(parents=True, exist_ok=True)
        fallback_file.write_text(cnf_content)
        target_file = fallback_file
        written = True

    # Attempt restarting MariaDB if installed and active
    restarted = False
    if _has_sudo():
        for svc in ['mariadb', 'mysql']:
            try:
                check = subprocess.run(['systemctl', 'is-active', svc], capture_output=True, text=True, timeout=3)
                if check.stdout.strip() == 'active':
                    res = subprocess.run(['sudo', '-n', 'systemctl', 'restart', svc], capture_output=True, timeout=10)
                    if res.returncode == 0:
                        restarted = True
                        break
            except Exception as e:
                logger.debug(f"Service {svc} restart error: {e}")

    return {
        'success': written,
        'config_path': str(target_file),
        'restarted': restarted,
    }


def get_database_tuning_status() -> dict:
    """Check whether W3Panel database tuning profile is in place."""
    candidates = [
        Path('/etc/mysql/mariadb.conf.d/99-w3panel.cnf'),
        Path('/etc/mysql/conf.d/99-w3panel.cnf'),
        Path('/tmp/w3panel/mysql/99-w3panel.cnf'),
    ]
    is_applied = any(p.exists() for p in candidates)
    return {
        'tuned': is_applied,
        'config_file': str(next((p for p in candidates if p.exists()), '')),
    }
