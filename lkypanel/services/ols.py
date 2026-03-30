"""
OpenLiteSpeed integration service.
All subprocess calls use explicit arg lists, shell=False, timeout=60.
"""
import logging
import re
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

LSWS_CTRL = '/usr/local/lsws/bin/lswsctrl'
VHOST_DIR  = '/usr/local/lsws/conf/vhosts'
HTTPD_CONF = '/usr/local/lsws/conf/httpd_config.conf'
PHP_MYADMIN_DIR = '/usr/local/lkypanel/phpmyadmin'
SSL_DIR = '/usr/local/lkypanel/ssl'

_DOMAIN_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9\-\.]{1,251}[a-zA-Z0-9]$')


def get_linux_user(domain: str) -> str:
    """Derive a valid Linux username (must be <= 32 chars) from the domain."""
    return re.sub(r'[^a-z0-9_-]', '_', domain.lower())[:32]


VHOST_TEMPLATE = """\
virtualHost {domain} {{
  vhRoot                  /home/{domain}/
  docRoot                 /home/{domain}/public_html/
  allowSymbolLink         1
  enableScript            1
  restrained              1

  index  {{
    useServer             0
    indexFiles            index.php, index.html, index.htm
  }}

  errorlog $VH_ROOT/logs/error.log {{
    useServer             0
    logLevel              DEBUG
    rollingSize           10M
  }}

  accesslog $VH_ROOT/logs/access.log {{
    useServer             0
    logFormat             "%h %l %u %t \\"%r\\" %>s %b \\"%{{Referer}}i\\" \\"%{{User-Agent}}i\\""
    logHeaders            Referer, User-Agent
    rollingSize           10M
    keepDays              30
    compressArchive       1
  }}

  extprocessor lsphp{php_ver_flat} {{
    type                  lsapi
    address               uds://tmp/lshttpd/lsphp{php_ver_flat}.sock
    maxConns              50
    env                   PHP_LSAPI_CHILDREN=50
    initTimeout           60
    retryTimeout          0
    persistConn           1
    pcKeepAliveTimeout    1
    respBuffer            0
    autoStart             1
    path                  /usr/local/lsws/lsphp{php_version}/bin/lsphp
    extUser               {linux_user}
    extGroup              {linux_user}
    memSoftLimit          2047M
    memHardLimit          2047M
    procSoftLimit         400
    procHardLimit         500
  }}

  scripthandler {{
    add lsphp{php_ver_flat} php
  }}

  rewrite  {{
    enable                1
    autoLoadHtaccess      1
    logLevel              0
    rules                 <<<END_REWRITE
RewriteRule ^/\\.git/ - [F]
RewriteRule ^/\\.env$ - [F]
RewriteRule ^/\\.htaccess$ - [F]
RewriteRule ^/\\.htpasswd$ - [F]
RewriteRule ^/composer\\.json$ - [F]
RewriteRule ^/composer\\.lock$ - [F]
RewriteRule ^/package\\.json$ - [F]
RewriteRule ^/package-lock\\.json$ - [F]
END_REWRITE
  }}
{ssl_block}}}
"""

SSL_BLOCK = """\
  vhssl  {{
    keyFile               /etc/letsencrypt/live/{domain}/privkey.pem
    certFile              /etc/letsencrypt/live/{domain}/fullchain.pem
    certChain             1
  }}
"""

# Snippet added to httpd_config.conf to register the vhost
HTTPD_VHOST_ENTRY = """
virtualHost {domain} {{
  vhRoot                  /home/{domain}/
  configFile              {vhost_dir}/{domain}/vhconf.conf
  allowSymbolLink         1
}}

listener HTTP {{
  map                     {domain} {domain}
}}
"""

HTTPD_LISTENER_ENTRY = """
listener HTTP {{
  address                 *:80
  secure                  0
  map                     {domain} {domain}
}}
"""


def _safe_domain(domain: str) -> str:
    if not _DOMAIN_RE.match(domain):
        raise ValueError(f'Invalid domain: {domain}')
    return domain


def _sudo_read(path: str) -> str:
    r = subprocess.run(['sudo', 'cat', path], capture_output=True, text=True, timeout=10)
    return r.stdout if r.returncode == 0 else ''


def _sudo_write(path: str, content: str) -> None:
    r = subprocess.run(['sudo', 'tee', path], input=content, text=True,
                       capture_output=True, timeout=10)
    if r.returncode != 0:
        raise RuntimeError(f'Failed to write {path}: {r.stderr}')


def write_vhost_config(domain: str, php_version: str = '8.1', ssl: bool = False) -> Path:
    domain = _safe_domain(domain)
    php_flat = php_version.replace('.', '')
    linux_user = get_linux_user(domain)
    ssl_block = SSL_BLOCK.format(domain=domain) if ssl else ''
    config = VHOST_TEMPLATE.format(
        domain=domain,
        php_ver_flat=php_flat,
        php_version=php_version,
        linux_user=linux_user,
        ssl_block=ssl_block
    )

    vhost_dir = Path(VHOST_DIR) / domain
    conf_file = vhost_dir / 'vhconf.conf'

    subprocess.run(['sudo', 'mkdir', '-p', str(vhost_dir)], check=True, timeout=10)
    _sudo_write(str(conf_file), config)

    # Register vhost in httpd_config.conf if not already there
    _register_vhost_in_httpd(domain)

    logger.info('Wrote OLS vhost config: %s', conf_file)
    return conf_file


def _register_vhost_in_httpd(domain: str) -> None:
    """Add virtualHost + listener map entry to httpd_config.conf if missing."""
    try:
        current = _sudo_read(HTTPD_CONF)
        if f'vhRoot                  /home/{domain}/' in current:
            return  # already registered

        entry = HTTPD_VHOST_ENTRY.format(domain=domain, vhost_dir=VHOST_DIR)
        _sudo_write(HTTPD_CONF, current + entry)
        logger.info('Registered vhost %s in httpd_config.conf', domain)
    except Exception as e:
        logger.warning('Could not register vhost in httpd_config.conf: %s', e)


def _unregister_vhost_from_httpd(domain: str) -> None:
    """Remove the vhost block for domain from httpd_config.conf."""
    try:
        current = _sudo_read(HTTPD_CONF)
        # Remove the block we added
        marker = f'\nvirtualHost {domain} {{'
        if marker not in current:
            return
        start = current.index(marker)
        # Find matching closing brace
        depth, pos = 0, start
        for i, ch in enumerate(current[start:], start):
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    pos = i + 1
                    break
        new_content = current[:start] + current[pos:]
        _sudo_write(HTTPD_CONF, new_content)
        logger.info('Unregistered vhost %s from httpd_config.conf', domain)
    except Exception as e:
        logger.warning('Could not unregister vhost from httpd_config.conf: %s', e)


def delete_vhost_config(domain: str) -> None:
    domain = _safe_domain(domain)
    vhost_dir = Path(VHOST_DIR) / domain
    subprocess.run(['sudo', 'rm', '-rf', str(vhost_dir)], timeout=10)
    _unregister_vhost_from_httpd(domain)
    logger.info('Deleted OLS vhost config for %s', domain)


def reload_ols() -> None:
    """Graceful reload — non-fatal if OLS is not installed."""
    if not Path(LSWS_CTRL).exists():
        logger.warning('lswsctrl not found — skipping OLS reload')
        return
    result = subprocess.run(
        ['sudo', LSWS_CTRL, 'graceful'],
        shell=False, timeout=60, capture_output=True, text=True,
    )
    if result.returncode != 0:
        logger.error('OLS reload failed: %s', result.stderr)
        # Non-fatal — site is created, OLS just needs manual reload
    else:
        logger.info('OLS graceful reload OK')


def setup_panel_ols() -> None:
    """Ensure OLS is ready for website hosting and panel tools.
    
    The panel (2087/2083) is served directly by Gunicorn. OLS only serves
    the tools (like phpMyAdmin) on an internal port (8088) for proxying.
    """
    try:
        conf = _sudo_read(HTTPD_CONF)
        if 'listener HTTP {' not in conf:
            http_listener = """
listener HTTP {
  address                 *:80
  secure                  0
}
"""
            conf += http_listener
            _sudo_write(HTTPD_CONF, conf)
            logger.info('Added HTTP listener (port 80) to OLS for websites')
        
        # 1. Inject phpMyAdmin context into Example vhost (internal tools host on 8088)
        example_vhost_conf = '/usr/local/lsws/conf/vhosts/Example/vhconf.conf'
        conf_example = _sudo_read(example_vhost_conf)
        
        if 'context /phpmyadmin/' not in conf_example:
            pma_context = """
context /phpmyadmin/ {
  location                /usr/local/lkypanel/phpmyadmin/
  allowBrowse             1
  indexFiles              index.php
  
  rewrite  {
    enable                1
    inherit               1
    RewriteFile           .htaccess
  }
  
  addDefaultCharset       off

  php {
    useServer             0
    initTimeout           60
    retryTimeout          0
    respBuffer            0
  }
}
"""
            conf_example += pma_context
            _sudo_write(example_vhost_conf, conf_example)
            logger.info('Injected phpMyAdmin context into OLS Example vhost')

        reload_ols()
        logger.info('OLS ready (panel is independent on 2087/2083)')
    except Exception as e:
        logger.error('Failed to setup OLS: %s', e)
        raise


def create_docroot(domain: str) -> Path:
    domain = _safe_domain(domain)

    # Derive a valid Linux username
    linux_user = get_linux_user(domain)

    home_dir  = Path(f'/home/{domain}')
    docroot   = home_dir / 'public_html'
    logs_dir  = home_dir / 'logs'

    # Detect distro for group name
    try:
        with open('/etc/lsb-release') as f:
            is_ubuntu = True
    except FileNotFoundError:
        is_ubuntu = False

    group_name = 'nogroup' if is_ubuntu else 'nobody'

    # Create system user (no login, home at /home/domain) — ignore error if exists
    if is_ubuntu:
        subprocess.run(
            ['sudo', '/usr/sbin/adduser', '--no-create-home',
             '--home', str(home_dir), '--disabled-login', '--gecos', '', linux_user],
            capture_output=True, timeout=15
        )
    else:
        subprocess.run(
            ['sudo', '/usr/sbin/adduser', linux_user, '-M', '-d', str(home_dir)],
            capture_output=True, timeout=15
        )

    # Create group and add user to it
    subprocess.run(['sudo', '/usr/sbin/groupadd', linux_user], capture_output=True, timeout=10)
    subprocess.run(['sudo', '/usr/sbin/usermod', '-a', '-G', linux_user, linux_user],
                   capture_output=True, timeout=10)

    # /home/domain — owned user:user, chmod 711
    subprocess.run(['sudo', 'mkdir', '-p', str(home_dir)], check=True, timeout=10)
    subprocess.run(['sudo', 'chown', f'{linux_user}:{linux_user}', str(home_dir)], check=True, timeout=10)
    subprocess.run(['sudo', 'chmod', '711', str(home_dir)], check=True, timeout=10)

    # /home/domain/public_html — owned user:nogroup, chmod 750
    subprocess.run(['sudo', 'mkdir', '-p', str(docroot)], check=True, timeout=10)
    subprocess.run(['sudo', 'chown', f'{linux_user}:{group_name}', str(docroot)], check=True, timeout=10)
    subprocess.run(['sudo', 'chmod', '750', str(docroot)], check=True, timeout=10)

    # /home/domain/logs — owned root:nogroup, chmod 750
    subprocess.run(['sudo', 'mkdir', '-p', str(logs_dir)], check=True, timeout=10)
    subprocess.run(['sudo', 'chown', f'root:{group_name}', str(logs_dir)], check=True, timeout=10)
    subprocess.run(['sudo', 'chmod', '750', str(logs_dir)], check=True, timeout=10)

    logger.info('Created site structure for %s (linux_user: %s)', domain, linux_user)
    return docroot
