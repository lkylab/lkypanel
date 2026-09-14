"""
W3Panel v2 — SSL Certificate Manager
Automates Let's Encrypt issuance via Certbot with fallback to self-signed certificates.
"""
import os
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger('w3panel.ssl')

def _get_ssl_dir() -> Path:
    target = Path(os.environ.get('W3PANEL_SSL_DIR', '/etc/w3panel/ssl'))
    try:
        target.mkdir(parents=True, exist_ok=True)
        return target
    except Exception:
        fallback = Path('/tmp/w3panel/ssl')
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def issue_certificate(website, email: str = '') -> dict:
    """
    Issue SSL certificate for a website domain.
    Attempts Let's Encrypt first; falls back to self-signed for dev/local testing.
    """
    domain = website.domain
    username = website.owner.username if website.owner else 'w3panel'
    webroot = Path(website.doc_root) if website.doc_root else Path(f"/home/{username}/{domain}/public_html")

    # Check for Let's Encrypt live path
    le_cert = Path(f"/etc/letsencrypt/live/{domain}/fullchain.pem")
    le_key = Path(f"/etc/letsencrypt/live/{domain}/privkey.pem")

    # Try Certbot if domain is not localhost/local IP
    if not domain.endswith('.local') and not domain.replace('.', '').isdigit() and 'localhost' not in domain:
        try:
            cmd = [
                'sudo', 'certbot', 'certonly', '--webroot',
                '-w', str(webroot),
                '-d', domain,
                '-d', f"www.{domain}",
                '--non-interactive',
                '--agree-tos',
                '--register-unsafely-without-email' if not email else f'--email={email}',
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if res.returncode == 0 and le_cert.exists():
                website.ssl_enabled = True
                website.save()
                from services.webserver import create_vhost
                create_vhost(website, ssl_cert=str(le_cert), ssl_key=str(le_key))
                return {'success': True, 'type': 'letsencrypt', 'cert': str(le_cert), 'key': str(le_key)}
        except Exception as e:
            logger.warning(f"Certbot attempt bypassed/failed: {e}")

    # Fallback to self-signed certificate for local testing
    self_cert, self_key = _generate_self_signed(domain)
    website.ssl_enabled = True
    website.save()

    from services.webserver import create_vhost
    create_vhost(website, ssl_cert=str(self_cert), ssl_key=str(self_key))
    return {'success': True, 'type': 'self-signed', 'cert': str(self_cert), 'key': str(self_key)}


def _generate_self_signed(domain: str) -> tuple:
    """Generate self-signed certificate in /etc/w3panel/ssl (or fallback)."""
    ssl_dir = _get_ssl_dir()
    cert_path = ssl_dir / f"{domain}.crt"
    key_path = ssl_dir / f"{domain}.key"

    if not cert_path.exists() or not key_path.exists():
        cmd = [
            'openssl', 'req', '-x509', '-nodes', '-days', '3650',
            '-newkey', 'rsa:2048',
            '-keyout', str(key_path),
            '-out', str(cert_path),
            '-subj', f"/C=US/ST=State/L=City/O=W3Panel/CN={domain}",
            '-addext', f"subjectAltName=DNS:{domain},DNS:www.{domain}",
        ]
        try:
            subprocess.run(cmd, capture_output=True, timeout=10)
            try:
                os.chmod(str(key_path), 0o600)
                os.chmod(str(cert_path), 0o644)
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Failed to generate self-signed cert: {e}")

    return cert_path, key_path
