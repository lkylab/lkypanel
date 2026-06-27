"""PHP management service — ini editing and package management."""
import subprocess
import re
import os

LSPHP_BASE = '/usr/local/lsws'

# Known lsphp versions and their ini paths
PHP_VERSIONS = ['8.3', '8.2', '8.1', '8.0', '7.4']


def _run(cmd, input=None):
    return subprocess.run(cmd, shell=False, capture_output=True, text=True,
                          input=input, timeout=60)


def get_installed_versions() -> list[str]:
    """Return list of installed lsphp versions e.g. ['8.3', '8.1']"""
    installed = []
    for v in PHP_VERSIONS:
        vd = v.replace('.', '')
        if os.path.exists(f'{LSPHP_BASE}/lsphp{vd}/bin/lsphp'):
            installed.append(v)
    return installed


def get_ini_path(version: str) -> str:
    vd = version.replace('.', '')
    return f'{LSPHP_BASE}/lsphp{vd}/etc/php/{version}/litespeed/php.ini'


def read_ini(version: str) -> dict:
    path = get_ini_path(version)
    r = _run(['sudo', 'cat', path])
    if r.returncode != 0:
        return {'error': f'Cannot read {path}: {r.stderr.strip()}'}
    return {'content': r.stdout, 'path': path}


def write_ini(version: str, content: str) -> dict:
    path = get_ini_path(version)
    r = _run(['sudo', 'tee', path], input=content)
    if r.returncode != 0:
        return {'error': r.stderr.strip()}
    return {'ok': True}


def get_ini_values(version: str) -> dict:
    """Parse key ini settings into a dict for the UI."""
    result = read_ini(version)
    if 'error' in result:
        return result
    values = {}
    for line in result['content'].splitlines():
        line = line.strip()
        if line.startswith(';') or '=' not in line:
            continue
        key, _, val = line.partition('=')
        values[key.strip()] = val.strip()
    return {'values': values, 'raw': result['content'], 'path': result['path']}


def set_ini_values(version: str, updates: dict) -> dict:
    """Update specific ini keys, preserving the rest of the file."""
    result = read_ini(version)
    if 'error' in result:
        return result
    content = result['content']
    for key, val in updates.items():
        # Replace existing key or append
        pattern = rf'^(\s*;?\s*{re.escape(key)}\s*=.*)$'
        replacement = f'{key} = {val}'
        new_content, n = re.subn(pattern, replacement, content, flags=re.MULTILINE)
        if n == 0:
            new_content = content + f'\n{key} = {val}'
        content = new_content
    return write_ini(version, content)


# ── Package management ─────────────────────────────────────────────────────

# Common lsphp extensions available via apt
KNOWN_EXTENSIONS = [
    'curl', 'mysql', 'pgsql', 'sqlite3', 'redis', 'memcached',
    'imagick', 'gd', 'intl', 'mbstring', 'xml', 'zip', 'bcmath',
    'soap', 'imap', 'ldap', 'tidy', 'xsl', 'opcache', 'apcu',
    'mongodb', 'igbinary', 'msgpack', 'inotify', 'uuid',
]


def get_packages(version: str) -> dict:
    """Return list of extensions with installed status."""
    vd = version.replace('.', '')
    prefix = f'lsphp{vd}-'
    # Get installed packages
    r = _run(['sudo', 'apt-get', 'list', '--installed'])
    installed_raw = r.stdout if r.returncode == 0 else ''
    installed = set()
    for line in installed_raw.splitlines():
        if line.startswith(prefix):
            pkg = line.split('/')[0].replace(prefix, '')
            installed.add(pkg)

    packages = []
    for ext in KNOWN_EXTENSIONS:
        packages.append({
            'name': ext,
            'pkg': f'{prefix}{ext}',
            'installed': ext in installed,
        })
    return {'packages': packages, 'version': version}


def install_packages(version: str, extensions: list[str]) -> dict:
    vd = version.replace('.', '')
    pkgs = [f'lsphp{vd}-{e}' for e in extensions]
    r = _run(['sudo', 'apt-get', 'install', '-y', '-qq'] + pkgs)
    if r.returncode != 0:
        return {'error': r.stderr.strip() or r.stdout.strip()}
    return {'ok': True, 'installed': extensions}


def remove_packages(version: str, extensions: list[str]) -> dict:
    vd = version.replace('.', '')
    pkgs = [f'lsphp{vd}-{e}' for e in extensions]
    r = _run(['sudo', 'apt-get', 'remove', '-y', '-qq'] + pkgs)
    if r.returncode != 0:
        return {'error': r.stderr.strip() or r.stdout.strip()}
    return {'ok': True, 'removed': extensions}
