"""
SSL certificate management via certbot / Let's Encrypt.
Cert path: /etc/letsencrypt/live/{domain}/fullchain.pem
"""
import logging
import re
import socket
import subprocess
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
CERTBOT_TIMEOUT = 120


def _server_ips() -> set:
    try:
        import netifaces
        ips = set()
        for iface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface)
            for addr in addrs.get(netifaces.AF_INET, []):
                ips.add(addr['addr'])
        return ips
    except ImportError:
        # fallback
        return {socket.gethostbyname(socket.gethostname())}


def domain_resolves_to_server(domain: str) -> bool:
    try:
        resolved = socket.gethostbyname(domain)
        return resolved in _server_ips()
    except socket.gaierror:
        return False


def request_certificate(website, webroot: str = None) -> 'SSLCertificate':
    from lkypanel.models import SSLCertificate
    from lkypanel.services.ols import reload_ols, write_vhost_config

    domain = website.domain
    webroot = webroot or website.doc_root

    base_cmd = [
        'sudo', 'certbot', 'certonly', '--webroot',
        '-w', webroot, '-d', domain,
        '--non-interactive', '--agree-tos',
        '--email', f'admin@{domain}',
    ]

    result = subprocess.run(
        base_cmd,
        shell=False, timeout=CERTBOT_TIMEOUT, capture_output=True, text=True,
    )
    if result.returncode != 0:
        logger.error('certbot failed for %s: %s', domain, result.stderr)
        raise RuntimeError(f'certbot failed: {result.stderr[:1024]}')

    expires_at = _read_cert_expiry(domain)

    ssl_cert, _ = SSLCertificate.objects.update_or_create(
        website=website,
        defaults=dict(
            issued_at=datetime.now(timezone.utc),
            expires_at=expires_at,
            auto_renew=True,
        ),
    )
    website.ssl_enabled = True
    website.save(update_fields=['ssl_enabled'])

    write_vhost_config(domain, website.php_version, ssl=True)
    reload_ols()

    return ssl_cert


def renew_certificate(ssl_cert) -> None:
    from lkypanel.services.ols import reload_ols
    from lkypanel.audit import log_action

    domain = ssl_cert.website.domain
    result = subprocess.run(
        ['sudo', 'certbot', 'renew', '--cert-name', domain, '--non-interactive'],
        shell=False, timeout=CERTBOT_TIMEOUT, capture_output=True, text=True,
    )
    if result.returncode != 0:
        logger.error('certbot renew failed for %s: %s', domain, result.stderr)
        log_action(None, 'ssl_renew_fail', domain, '127.0.0.1')
        raise RuntimeError(f'certbot renew failed: {result.stderr[:1024]}')

    ssl_cert.expires_at = _read_cert_expiry(domain)
    ssl_cert.save(update_fields=['expires_at'])
    reload_ols()
    logger.info('SSL renewed for %s', domain)


def _read_cert_expiry(domain: str) -> datetime:
    """Read expiry date from the issued certificate."""
    cert_path = f'/etc/letsencrypt/live/{domain}/fullchain.pem'
    try:
        result = subprocess.run(
            ['sudo', 'openssl', 'x509', '-enddate', '-noout', '-in', cert_path],
            shell=False, timeout=10, capture_output=True, text=True,
        )
        # notAfter=Jan  1 00:00:00 2026 GMT
        match = re.search(r'notAfter=(.+)', result.stdout)
        if match:
            return datetime.strptime(match.group(1).strip(), '%b %d %H:%M:%S %Y %Z').replace(
                tzinfo=timezone.utc)
    except Exception:
        pass
    # fallback: 90 days from now
    from datetime import timedelta
    return datetime.now(timezone.utc) + timedelta(days=90)
