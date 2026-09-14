"""
W3Panel v2 — Web Server & VirtualHost Manager
Generates VirtualHost configurations (Nginx / OpenLiteSpeed) and provisions document roots.
Phase 1: Dedicated per-user PHP-FPM pools, OS kernel tuning, and Nginx Real-IP restoration.
"""
import os
import shutil
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger('w3panel.webserver')

NGINX_AVAILABLE = Path('/etc/nginx/sites-available')
NGINX_ENABLED = Path('/etc/nginx/sites-enabled')


def _has_sudo() -> bool:
    """Check if passwordless sudo is available."""
    try:
        res = subprocess.run(['sudo', '-n', 'true'], capture_output=True, timeout=2)
        return res.returncode == 0
    except Exception:
        return False


def _get_users_base_dir() -> Path:
    """Return base directory for user home directories: /home by default."""
    env_dir = os.environ.get('W3PANEL_USERS_DIR')
    if env_dir:
        p = Path(env_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p
    target = Path('/home')
    if target.exists():
        return target
    fallback = Path('/tmp/w3panel/users')
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def _get_vhost_dir() -> Path:
    """Return directory for generated virtual hosts."""
    target = Path(os.environ.get('W3PANEL_VHOST_DIR', '/etc/w3panel/vhosts'))
    try:
        target.mkdir(parents=True, exist_ok=True)
        return target
    except Exception:
        fallback = Path('/tmp/w3panel/vhosts')
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def _get_php_pool_dir(php_version: str = '8.3') -> Path:
    """Return directory for PHP-FPM pool configurations."""
    env_dir = os.environ.get('W3PANEL_PHP_POOL_DIR')
    if env_dir:
        p = Path(env_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p
    target = Path(f"/etc/php/{php_version}/fpm/pool.d")
    if target.exists() and (os.access(str(target), os.W_OK) or _has_sudo()):
        return target
    fallback = Path(f"/tmp/w3panel/php/{php_version}/pools")
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


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
            logger.error(f"Failed to write privileged file {target_path}: {e}")
            return False


def _remove_privileged_file(target_path: Path) -> bool:
    """Remove file directly or escalate with sudo -n rm if permission denied."""
    if not target_path.exists():
        return True
    try:
        target_path.unlink()
        return True
    except (PermissionError, OSError):
        if not _has_sudo():
            return False
        try:
            proc = subprocess.run(['sudo', '-n', 'rm', '-f', str(target_path)], capture_output=True, timeout=3)
            return proc.returncode == 0
        except Exception as e:
            logger.error(f"Failed to remove privileged file {target_path}: {e}")
            return False


def _ensure_system_user(username: str, home_dir: Path) -> str:
    """
    Ensure a Linux user exists for the tenant.
    Returns username if exists/created, or fallback user ('w3panel', 'www-data', or current process user).
    """
    import pwd
    try:
        pwd.getpwnam(username)
        return username
    except KeyError:
        pass

    if _has_sudo():
        try:
            cmd = ['sudo', '-n', 'useradd', '-m', '-s', '/bin/false', '-d', str(home_dir), username]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
            if res.returncode == 0:
                logger.info(f"Created system user {username}")
                return username
        except Exception as e:
            logger.debug(f"Could not create system user {username}: {e}")

    for fallback in ['w3panel', 'www-data']:
        try:
            pwd.getpwnam(fallback)
            return fallback
        except KeyError:
            pass

    try:
        import getpass
        return getpass.getuser()
    except Exception:
        return 'nobody'


def _get_user_group(user: str) -> str:
    """Get group for user or fallback."""
    import grp
    try:
        grp.getgrnam(user)
        return user
    except KeyError:
        pass
    for fallback in ['w3panel', 'www-data']:
        try:
            grp.getgrnam(fallback)
            return fallback
        except KeyError:
            pass
    return user


def sync_system_user_shell(username: str, shell_enabled: bool) -> bool:
    """Update POSIX shell for tenant user (/bin/bash if enabled, /bin/false if disabled)."""
    shell = '/bin/bash' if shell_enabled else '/bin/false'
    if _has_sudo():
        try:
            res = subprocess.run(['sudo', '-n', 'usermod', '-s', shell, username], capture_output=True, timeout=3)
            return res.returncode == 0
        except Exception as e:
            logger.debug(f"Could not update shell for {username}: {e}")
    return False


def sync_system_user_password(username: str, password: str) -> bool:
    """Sync POSIX system password for user (for SSH/SFTP/Terminal access)."""
    if _has_sudo() and password:
        try:
            proc = subprocess.run(
                ['sudo', '-n', 'chpasswd'],
                input=f"{username}:{password}\n",
                text=True,
                capture_output=True,
                timeout=5
            )
            return proc.returncode == 0
        except Exception as e:
            logger.debug(f"Could not sync system password for {username}: {e}")
    return False


def sync_system_user_status(username: str, is_active: bool) -> bool:
    """Lock or unlock system account (usermod -L / -U)."""
    flag = '-U' if is_active else '-L'
    if _has_sudo():
        try:
            res = subprocess.run(['sudo', '-n', 'usermod', flag, username], capture_output=True, timeout=3)
            return res.returncode == 0
        except Exception as e:
            logger.debug(f"Could not toggle system user lock for {username}: {e}")
    return False



def get_user_php_socket(username: str, php_version: str = '8.3') -> str:
    """Return UNIX socket path for user's PHP-FPM pool."""
    if not username or username == 'w3panel':
        return f"unix:/run/php/php{php_version}-fpm.sock"
    return f"unix:/run/php/php{php_version}-fpm-{username}.sock"


def get_doc_root(username: str, domain: str, framework: str = 'none') -> Path:
    """
    Determine document root directory for a website:
    /home/<username>/<domain>/public_html
    If multidomain for same user:
    /home/<username>/<domain2>/public_html
    """
    base = _get_users_base_dir() / username / domain / 'public_html'
    if framework == 'laravel':
        return base / 'public'
    return base


def create_user_php_pool(
    username: str,
    php_version: str = '8.3',
    max_children: int = 20,
    start_servers: int = 4,
    min_spare_servers: int = 2,
    max_spare_servers: int = 8,
    memory_limit: str = '256M',
    upload_max_filesize: str = '64M'
) -> dict:
    """
    Generate and provision dedicated per-tenant PHP-FPM pool configuration.
    Enforces open_basedir jailing, dedicated session/tmp paths, and user isolation.
    """
    if not username:
        return {'success': False, 'error': 'Username is required'}

    user_base = _get_users_base_dir() / username
    user_tmp = user_base / 'tmp'
    user_sessions = user_base / 'sessions'

    # 1. Create isolation directories
    try:
        user_base.mkdir(parents=True, exist_ok=True)
        user_tmp.mkdir(parents=True, exist_ok=True)
        user_sessions.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.warning(f"Could not create user pool directories: {e}")

    # 2. Determine pool execution user and group
    pool_user = _ensure_system_user(username, user_base)
    pool_group = _get_user_group(pool_user)

    # Listen ownership: www-data if available
    listen_owner = 'www-data'
    try:
        import grp
        grp.getgrnam('www-data')
    except KeyError:
        listen_owner = pool_user

    sock_path = f"/run/php/php{php_version}-fpm-{username}.sock"

    # Fix ownership and permissions of tenant directories
    if _has_sudo():
        try:
            subprocess.run(['sudo', '-n', 'mkdir', '-p', str(user_base), str(user_tmp), str(user_sessions)], capture_output=True, timeout=3)
            subprocess.run(['sudo', '-n', 'chown', f"{pool_user}:{pool_group}", str(user_base)], capture_output=True, timeout=3)
            subprocess.run(['sudo', '-n', 'chmod', '755', str(user_base)], capture_output=True, timeout=3)
            subprocess.run(['sudo', '-n', 'chown', '-R', f"{pool_user}:{pool_group}", str(user_sessions), str(user_tmp)], capture_output=True, timeout=3)
            subprocess.run(['sudo', '-n', 'chmod', '700', str(user_sessions)], capture_output=True, timeout=3)
            subprocess.run(['sudo', '-n', 'chmod', '700', str(user_tmp)], capture_output=True, timeout=3)
            if listen_owner == 'www-data':
                subprocess.run(['sudo', '-n', 'usermod', '-aG', pool_group, 'www-data'], capture_output=True, timeout=3)
        except Exception:
            pass

    # 3. Generate pool config
    pool_config = f"""; ==============================================================================
; W3Panel Dedicated PHP-FPM Pool: {username}
; ==============================================================================
[{username}]
user = {pool_user}
group = {pool_group}

listen = {sock_path}
listen.owner = {listen_owner}
listen.group = {listen_owner}
listen.mode = 0660
listen.backlog = 65535

pm = dynamic
pm.max_children = {max_children}
pm.start_servers = {start_servers}
pm.min_spare_servers = {min_spare_servers}
pm.max_spare_servers = {max_spare_servers}
pm.max_requests = 1000

; Per-tenant isolation & security
php_admin_value[open_basedir] = {user_base}:/tmp
php_admin_value[upload_tmp_dir] = {user_tmp}
php_admin_value[session.save_path] = {user_sessions}
php_admin_value[memory_limit] = {memory_limit}
php_admin_value[max_execution_time] = 120
php_admin_value[upload_max_filesize] = {upload_max_filesize}
php_admin_value[post_max_size] = {upload_max_filesize}
"""

    # 4. Write pool file
    pool_dir = _get_php_pool_dir(php_version)
    pool_file = pool_dir / f"{username}.conf"
    if not _write_privileged_file(pool_file, pool_config):
        return {'success': False, 'error': f"Failed to write pool file {pool_file}"}

    # Also mirror into system /etc/php/{ver}/fpm/pool.d if it exists and differs
    if _has_sudo():
        etc_dir = Path(f"/etc/php/{php_version}/fpm/pool.d")
        if etc_dir.exists() and pool_dir.resolve() != etc_dir.resolve():
            _write_privileged_file(etc_dir / f"{username}.conf", pool_config)

    # 5. Reload PHP-FPM
    reloaded = reload_php_fpm(php_version)
    return {
        'success': True,
        'pool_path': str(pool_file),
        'socket': sock_path,
        'reloaded': reloaded
    }


def remove_user_php_pool(username: str, php_version: str = '8.3') -> dict:
    """Remove user's PHP-FPM pool and reload service."""
    pool_dir = _get_php_pool_dir(php_version)
    pool_file = pool_dir / f"{username}.conf"
    _remove_privileged_file(pool_file)

    if _has_sudo():
        etc_file = Path(f"/etc/php/{php_version}/fpm/pool.d/{username}.conf")
        if etc_file.exists():
            _remove_privileged_file(etc_file)

    reloaded = reload_php_fpm(php_version)
    return {'success': True, 'reloaded': reloaded}


def reload_php_fpm(php_version: str = '8.3') -> bool:
    """Reload PHP-FPM service if active and sudo is available."""
    service_name = f"php{php_version}-fpm"
    try:
        res = subprocess.run(['systemctl', 'is-active', service_name], capture_output=True, text=True, timeout=3)
        if res.stdout.strip() == 'active' and _has_sudo():
            reload_res = subprocess.run(['sudo', '-n', 'systemctl', 'reload', service_name], capture_output=True, timeout=5)
            if reload_res.returncode == 0:
                logger.info(f"Reloaded {service_name}")
                return True
            else:
                subprocess.run(['sudo', '-n', 'systemctl', 'restart', service_name], timeout=5)
                return True
    except Exception as e:
        logger.debug(f"PHP-FPM reload bypassed: {e}")
    return False


def apply_system_tuning(php_version: str = '8.3') -> dict:
    """
    Apply DiamondWish-grade kernel and OS tuning:
    1. /etc/sysctl.d/99-w3panel.conf (somaxconn, file-max, tcp tuning)
    2. /etc/security/limits.d/99-w3panel.conf (1M nofile)
    3. Production OPcache tuning with JIT tracing
    4. Nginx Real-IP restoration configuration
    """
    results = {'applied': [], 'errors': []}

    # Ensure log directory permissions for Nginx logging
    if _has_sudo():
        log_dir = Path('/var/log/w3panel')
        if log_dir.exists():
            try:
                subprocess.run(['sudo', '-n', 'chgrp', 'www-data', str(log_dir)], capture_output=True, timeout=3)
                subprocess.run(['sudo', '-n', 'chmod', '775', str(log_dir)], capture_output=True, timeout=3)
            except Exception:
                pass

    # 1. Sysctl Kernel Tuning
    sysctl_content = """# W3Panel Production High-Performance Kernel Tuning
fs.file-max = 2097152
fs.nr_open = 2097152
net.core.somaxconn = 65535
net.core.netdev_max_backlog = 65535
net.ipv4.ip_local_port_range = 1024 65535
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fin_timeout = 15
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216
"""
    sysctl_path = Path('/etc/sysctl.d/99-w3panel.conf')
    if _write_privileged_file(sysctl_path, sysctl_content):
        results['applied'].append('sysctl')
        if _has_sudo():
            try:
                subprocess.run(['sudo', '-n', 'sysctl', '-p', str(sysctl_path)], capture_output=True, timeout=5)
            except Exception:
                pass
    else:
        results['errors'].append('sysctl')

    # 2. Security Limits
    limits_content = """# W3Panel Production File Descriptor Limits
* soft nofile 1048576
* hard nofile 1048576
root soft nofile 1048576
root hard nofile 1048576
w3panel soft nofile 1048576
w3panel hard nofile 1048576
www-data soft nofile 1048576
www-data hard nofile 1048576
"""
    limits_path = Path('/etc/security/limits.d/99-w3panel.conf')
    if _write_privileged_file(limits_path, limits_content):
        results['applied'].append('limits')
    else:
        results['errors'].append('limits')

    # 3. Production OPcache with JIT tracing
    opcache_content = """; W3Panel Production OPcache Configuration
[opcache]
opcache.enable=1
opcache.enable_cli=0
opcache.memory_consumption=256
opcache.interned_strings_buffer=32
opcache.max_accelerated_files=50000
opcache.validate_timestamps=1
opcache.revalidate_freq=2
opcache.fast_shutdown=1
opcache.save_comments=1
opcache.jit=tracing
opcache.jit_buffer_size=64M
"""
    opcache_dir = Path(f"/etc/php/{php_version}/fpm/conf.d")
    if opcache_dir.exists():
        opcache_file = opcache_dir / '10-w3panel-opcache.ini'
        if _write_privileged_file(opcache_file, opcache_content):
            results['applied'].append('opcache')
            reload_php_fpm(php_version)

    # 4. Remove any global real-ip configuration (Real-IP is scoped per site)
    global_real_ip = Path('/etc/nginx/conf.d/w3panel-real-ip.conf')
    if global_real_ip.exists():
        _remove_privileged_file(global_real_ip)
        reload_webserver()

    results['success'] = len(results['applied']) > 0
    return results


def get_system_tuning_status(php_version: str = '8.3') -> dict:
    """Check current status of OS kernel tuning, limits, OPcache, and user pools."""
    sysctl_ok = Path('/etc/sysctl.d/99-w3panel.conf').exists()
    limits_ok = Path('/etc/security/limits.d/99-w3panel.conf').exists()
    opcache_ok = Path(f"/etc/php/{php_version}/fpm/conf.d/10-w3panel-opcache.ini").exists()

    pool_dir = Path(f"/etc/php/{php_version}/fpm/pool.d")
    pool_count = 0
    if pool_dir.exists():
        pool_count = len(list(pool_dir.glob('*.conf')))

    return {
        'sysctl': sysctl_ok,
        'limits': limits_ok,
        'opcache': opcache_ok,
        'pool_count': pool_count,
        'fully_tuned': all([sysctl_ok, limits_ok, opcache_ok]),
    }


def create_vhost(website, ssl_cert: str = '', ssl_key: str = '') -> dict:
    """
    Create or update VirtualHost configuration and document root for a domain.
    Provisions dedicated per-tenant PHP-FPM pool for isolated execution.
    """
    domain = website.domain
    username = website.owner.username if website.owner else 'w3panel'
    framework = website.framework
    php_version = website.php_version or '8.3'
    doc_root = Path(website.doc_root) if website.doc_root else get_doc_root(username, domain, framework)

    # 1. Create document root directory
    try:
        user_base = _get_users_base_dir() / username
        domain_dir = user_base / domain
        if _has_sudo():
            subprocess.run(['sudo', '-n', 'mkdir', '-p', str(doc_root)], capture_output=True, timeout=3)
            subprocess.run(['sudo', '-n', 'chmod', '755', str(user_base)], capture_output=True, timeout=3)
            subprocess.run(['sudo', '-n', 'chown', '-R', f"{username}:{username}", str(domain_dir)], capture_output=True, timeout=3)
            subprocess.run(['sudo', '-n', 'chmod', '-R', '755', str(domain_dir)], capture_output=True, timeout=3)
        else:
            doc_root.mkdir(parents=True, exist_ok=True)

        # Create default index.php if directory is empty
        index_file = doc_root / 'index.php'
        if not index_file.exists() and not (doc_root / 'index.html').exists():
            index_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Welcome to {domain}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@latest/tabler-icons.min.css">
</head>
<body class="min-h-screen bg-slate-50 flex items-center justify-center p-6 text-slate-800">
    <div class="max-w-lg w-full bg-white rounded-2xl shadow-sm border border-slate-200 p-8 text-center">
        <div class="size-16 rounded-2xl bg-blue-600 text-white flex items-center justify-center text-3xl mx-auto mb-4 shadow-md shadow-blue-500/20">
            <i class="ti ti-world"></i>
        </div>
        <h1 class="text-2xl font-bold text-slate-900">{domain}</h1>
        <p class="text-sm text-slate-500 mt-2">Your new website is successfully created and live on W3Panel v2!</p>
        
        <div class="mt-6 p-4 rounded-xl bg-slate-50 border border-slate-200 text-left text-xs font-mono text-slate-600 space-y-1.5">
            <div><span class="text-slate-400 font-sans font-semibold">Document Root:</span> {doc_root}</div>
            <div><span class="text-slate-400 font-sans font-semibold">PHP Version:</span> <?php echo phpversion(); ?></div>
            <div><span class="text-slate-400 font-sans font-semibold">Tenant Pool:</span> {username}</div>
            <div><span class="text-slate-400 font-sans font-semibold">Framework:</span> {framework.capitalize()}</div>
        </div>

        <div class="mt-6 pt-4 border-t border-slate-100 flex items-center justify-center gap-4 text-xs text-slate-400">
            <span>Powered by W3Panel v2</span>
        </div>
    </div>
</body>
</html>
"""
            if not _write_privileged_file(index_file, index_content):
                try:
                    index_file.write_text(index_content)
                except Exception:
                    pass
            if _has_sudo():
                subprocess.run(['sudo', '-n', 'chown', f"{username}:{username}", str(index_file)], capture_output=True, timeout=3)
    except Exception as e:
        logger.warning(f"Could not create doc_root or default index: {e}")

    # 2. Provision dedicated per-user PHP pool (if PHP framework)
    pool_res = {}
    if framework != 'nodejs' and username:
        try:
            pool_res = create_user_php_pool(username=username, php_version=php_version)
        except Exception as e:
            logger.warning(f"Failed to provision PHP pool for {username}: {e}")

    proxy_real_ip = getattr(website, 'proxy_real_ip', False)
    port = getattr(website, 'port', 3000) or 3000

    # 3. Build Nginx VirtualHost Config
    vhost_config = _generate_nginx_config(
        domain=domain,
        doc_root=str(doc_root),
        php_version=php_version,
        framework=framework,
        username=username,
        port=port,
        ssl_enabled=website.ssl_enabled,
        ssl_cert=ssl_cert,
        ssl_key=ssl_key,
        proxy_real_ip=proxy_real_ip,
    )

    # 4. Save Vhost File
    vhost_dir = _get_vhost_dir()
    vhost_path = vhost_dir / f"{domain}.conf"
    if not _write_privileged_file(vhost_path, vhost_config):
        logger.error(f"Failed to write vhost config for {domain}")
        return {'success': False, 'error': f"Failed to write vhost config for {domain}"}

    # 5. Link into Nginx if available
    if NGINX_AVAILABLE.exists():
        try:
            target_avail = NGINX_AVAILABLE / f"{domain}.conf"
            target_enabled = NGINX_ENABLED / f"{domain}.conf"
            _write_privileged_file(target_avail, vhost_config)
            if not target_enabled.exists():
                try:
                    os.symlink(str(target_avail), str(target_enabled))
                except (PermissionError, OSError):
                    if _has_sudo():
                        subprocess.run(['sudo', '-n', 'ln', '-sf', str(target_avail), str(target_enabled)], capture_output=True)
        except Exception as e:
            logger.warning(f"Could not link to /etc/nginx/: {e}")

    # 6. Reload Nginx
    reload_res = reload_webserver()
    return {
        'success': True,
        'vhost_path': str(vhost_path),
        'reload': reload_res,
        'pool': pool_res
    }


def remove_vhost(domain: str) -> dict:
    """Remove VirtualHost configuration when website is deleted."""
    vhost_dir = _get_vhost_dir()
    vhost_path = vhost_dir / f"{domain}.conf"
    _remove_privileged_file(vhost_path)

    if NGINX_ENABLED.exists():
        enabled_link = NGINX_ENABLED / f"{domain}.conf"
        _remove_privileged_file(enabled_link)

    if NGINX_AVAILABLE.exists():
        avail_file = NGINX_AVAILABLE / f"{domain}.conf"
        _remove_privileged_file(avail_file)

    reload_webserver()
    return {'success': True}


def reload_webserver() -> bool:
    """Test and reload Nginx / web server if running."""
    try:
        res = subprocess.run(['systemctl', 'is-active', 'nginx'], capture_output=True, text=True, timeout=3)
        if res.stdout.strip() == 'active' and _has_sudo():
            test_res = subprocess.run(['sudo', '-n', 'nginx', '-t'], capture_output=True, text=True, timeout=5)
            if test_res.returncode == 0:
                subprocess.run(['sudo', '-n', 'systemctl', 'reload', 'nginx'], timeout=5)
                return True
            else:
                logger.error(f"Nginx config test failed: {test_res.stderr}")
                return False
    except Exception as e:
        logger.debug(f"Webserver reload bypassed: {e}")
    return False


def get_vhost_path(domain: str) -> Path:
    """Return primary vhost path on disk."""
    if NGINX_AVAILABLE.exists():
        avail = NGINX_AVAILABLE / f"{domain}.conf"
        if avail.exists():
            return avail
    return _get_vhost_dir() / f"{domain}.conf"


def get_vhost_content(website) -> str:
    """Read the current VirtualHost configuration or generate default."""
    vhost_file = get_vhost_path(website.domain)
    if vhost_file.exists():
        try:
            return vhost_file.read_text()
        except Exception:
            pass

    domain = website.domain
    username = website.owner.username if website.owner else 'w3panel'
    framework = website.framework
    php_version = website.php_version or '8.3'
    doc_root = Path(website.doc_root) if website.doc_root else get_doc_root(username, domain, framework)
    port = getattr(website, 'port', 3000) or 3000
    proxy_real_ip = getattr(website, 'proxy_real_ip', False)
    return _generate_nginx_config(
        domain=domain,
        doc_root=str(doc_root),
        php_version=php_version,
        framework=framework,
        username=username,
        port=port,
        ssl_enabled=website.ssl_enabled,
        proxy_real_ip=proxy_real_ip,
    )


def save_custom_vhost(website, content: str) -> dict:
    """
    Save custom Nginx vhost config, test syntax, and reload Nginx safely.
    If syntax is invalid, automatically rolls back to previous config.
    """
    domain = website.domain
    prev_content = get_vhost_content(website)

    vhost_dir = _get_vhost_dir()
    vhost_path = vhost_dir / f"{domain}.conf"
    avail_file = NGINX_AVAILABLE / f"{domain}.conf" if NGINX_AVAILABLE.exists() else None
    enabled_link = NGINX_ENABLED / f"{domain}.conf" if NGINX_ENABLED.exists() else None

    # 1. Write to target locations
    if not _write_privileged_file(vhost_path, content):
        return {'success': False, 'error': f"Failed to write configuration to {vhost_path}"}

    if avail_file:
        _write_privileged_file(avail_file, content)
        if enabled_link and not enabled_link.exists():
            try:
                os.symlink(str(avail_file), str(enabled_link))
            except Exception:
                if _has_sudo():
                    subprocess.run(['sudo', '-n', 'ln', '-sf', str(avail_file), str(enabled_link)], capture_output=True)

    # 2. Syntax validation test
    if shutil.which('nginx') and _has_sudo():
        try:
            test_res = subprocess.run(['sudo', '-n', 'nginx', '-t'], capture_output=True, text=True, timeout=5)
            if test_res.returncode != 0:
                # Syntax error! Rollback immediately
                logger.warning(f"Syntax error in custom vhost for {domain}: {test_res.stderr}. Rolling back.")
                _write_privileged_file(vhost_path, prev_content)
                if avail_file:
                    _write_privileged_file(avail_file, prev_content)
                return {
                    'success': False,
                    'error': f"Nginx syntax check failed:\n{test_res.stderr or test_res.stdout}\nChanges rolled back safely."
                }
        except Exception as e:
            logger.debug(f"Syntax test skipped: {e}")

    # 3. Reload webserver
    reloaded = reload_webserver()
    return {
        'success': True,
        'message': f"VirtualHost for {domain} saved and validated successfully.",
        'reloaded': reloaded
    }


def reset_vhost_to_default(website) -> dict:
    """Regenerate default virtual host configuration for website."""
    return create_vhost(website)


def get_website_logs(website, log_type: str = 'error', lines: int = 100) -> str:
    """Read recent domain access or error logs."""
    domain = website.domain
    log_file = Path(f"/var/log/w3panel/{domain}_{log_type}.log")
    if not log_file.exists():
        alt = Path(f"/var/log/nginx/{log_type}.log")
        if alt.exists():
            log_file = alt
        else:
            return f"No {log_type} log entries recorded yet for {domain}."

    try:
        cmd = ['tail', '-n', str(lines), str(log_file)]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
        return res.stdout if res.returncode == 0 and res.stdout.strip() else f"No recent {log_type} log entries."
    except Exception as e:
        return f"Could not read log file: {e}"


def _generate_nginx_config(
    domain: str,
    doc_root: str,
    php_version: str,
    framework: str,
    username: str = '',
    port: int = 3000,
    ssl_enabled: bool = False,
    ssl_cert: str = '',
    ssl_key: str = '',
    proxy_real_ip: bool = False,
) -> str:
    """Build Nginx vhost block with per-user socket, security headers, static caching, and reverse proxy support."""
    php_sock = get_user_php_socket(username, php_version)
    
    # Real-IP restoration (only injected if this specific website is behind a reverse proxy)
    real_ip_block = ""
    if proxy_real_ip:
        real_ip_block = """
    # Real-IP restoration behind reverse proxies & Cloudflare (Per-site enabled)
    set_real_ip_from 10.0.0.0/8;
    set_real_ip_from 172.16.0.0/12;
    set_real_ip_from 192.168.0.0/16;
    set_real_ip_from 127.0.0.1;
    set_real_ip_from 173.245.48.0/20;
    set_real_ip_from 103.21.244.0/22;
    set_real_ip_from 103.22.200.0/22;
    set_real_ip_from 103.31.4.0/22;
    set_real_ip_from 141.101.64.0/18;
    set_real_ip_from 108.162.192.0/18;
    set_real_ip_from 190.93.240.0/20;
    set_real_ip_from 188.114.96.0/20;
    set_real_ip_from 197.234.240.0/22;
    set_real_ip_from 198.41.128.0/17;
    set_real_ip_from 162.158.0.0/15;
    set_real_ip_from 104.16.0.0/13;
    set_real_ip_from 104.24.0.0/14;
    set_real_ip_from 172.64.0.0/13;
    set_real_ip_from 131.0.72.0/22;
    real_ip_header X-Forwarded-For;
    real_ip_recursive on;
"""

    if framework == 'nodejs':
        routes_and_backend = f"""
    # High-Performance Static Asset Caching with Node Proxy Fallback
    location ~* \\.(jpg|jpeg|gif|png|webp|svg|ico|css|js|woff|woff2|ttf|eot)$ {{
        expires 30d;
        add_header Cache-Control "public, no-transform";
        access_log off;
        try_files $uri @node_backend;
    }}

    location / {{
        try_files $uri @node_backend;
    }}

    location @node_backend {{
        proxy_pass http://127.0.0.1:{port};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }}
"""
    else:
        if framework in ('wordpress', 'laravel'):
            route_location = """    location / {
        try_files $uri $uri/ /index.php?$query_string;
    }"""
        else:
            route_location = """    location / {
        try_files $uri $uri/ =404;
    }"""

        routes_and_backend = f"""
    # High-Performance Static Asset Caching
    location ~* \\.(jpg|jpeg|gif|png|webp|svg|ico|css|js|woff|woff2|ttf|eot)$ {{
        expires 30d;
        add_header Cache-Control "public, no-transform";
        access_log off;
        try_files $uri =404;
    }}

{route_location}

    location ~ \\.php$ {{
        include snippets/fastcgi-php.conf;
        fastcgi_pass {php_sock};
        fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
        fastcgi_param HTTP_X_FORWARDED_PROTO $http_x_forwarded_proto if_not_empty;
        fastcgi_param HTTP_X_FORWARDED_FOR $proxy_add_x_forwarded_for;
        include fastcgi_params;
    }}
"""

    ssl_block = ""
    if ssl_enabled and ssl_cert and ssl_key:
        ssl_block = f"""
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    ssl_certificate {ssl_cert};
    ssl_certificate_key {ssl_key};
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
"""

    config = f"""# W3Panel VirtualHost Configuration for {domain}
# Tenant: {username or 'system'} | Mode: {framework} | Reverse Proxy Real-IP: {'Enabled' if proxy_real_ip else 'Disabled (Direct)'}
server {{
    listen 80;
    listen [::]:80;
    server_name {domain} www.{domain};
    root {doc_root};
    index index.php index.html index.htm;
{ssl_block}
    access_log /var/log/w3panel/{domain}_access.log;
    error_log /var/log/w3panel/{domain}_error.log;

    # Defense-in-depth Security Headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
{real_ip_block}
    # Sensitive file protection - return 404 to avoid information disclosure
    location ~* /(\\.(git|env|user\\.ini|htaccess|htpasswd)|composer\\.(json|lock)|auth\\.json|package(-lock)?\\.json) {{
        deny all;
        return 404;
    }}
{routes_and_backend}
}}
"""
    return config
