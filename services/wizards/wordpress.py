"""
W3Panel v2 — WordPress Installer Wizard
Installs and configures WordPress with automatic database, vhost, and wp-config.php.
"""
import urllib.request
import zipfile
import io
import secrets
import logging
from pathlib import Path

logger = logging.getLogger('w3panel.wizards.wordpress')


def install_wordpress(website, db_name: str = '', db_user: str = '', db_pass: str = '') -> dict:
    """
    Automate full WordPress installation for a Website instance.
    """
    domain = website.domain
    username = website.owner.username if website.owner else 'w3panel'
    doc_root = Path(website.doc_root) if website.doc_root else Path(f"/home/{username}/{domain}/public_html")
    doc_root.mkdir(parents=True, exist_ok=True)

    # 1. Setup Database
    if not db_name:
        db_name = f"{username}_wp_{secrets.token_hex(3)}"
    if not db_user:
        db_user = db_name[:16]
    if not db_pass:
        from services.database import generate_secure_password
        db_pass = generate_secure_password()

    from services.database import create_database
    db_res = create_database(db_name, db_user, db_pass, db_type='mariadb')

    # Save to Database Model
    from packages.core.models import Database
    Database.objects.get_or_create(
        owner=website.owner,
        name=db_name,
        defaults={'db_type': 'mariadb', 'db_user': db_user}
    )

    # 2. Download WordPress archive
    try:
        url = "https://wordpress.org/latest.zip"
        req = urllib.request.Request(url, headers={'User-Agent': 'W3Panel-Installer/2.0'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            zip_bytes = io.BytesIO(resp.read())
            with zipfile.ZipFile(zip_bytes) as z:
                # Extract contents inside 'wordpress/' directly into doc_root
                for member in z.infolist():
                    if member.filename.startswith('wordpress/'):
                        rel_path = member.filename[len('wordpress/'):]
                        if not rel_path:
                            continue
                        target = doc_root / rel_path
                        if member.is_dir():
                            target.mkdir(parents=True, exist_ok=True)
                        else:
                            target.parent.mkdir(parents=True, exist_ok=True)
                            with z.open(member) as src, open(target, 'wb') as dst:
                                dst.write(src.read())

        # 3. Generate wp-config.php
        _generate_wp_config(doc_root, db_name, db_user, db_pass)

        # 4. Update website framework to wordpress and regenerate vhost
        website.framework = 'wordpress'
        website.save()
        from services.webserver import create_vhost
        create_vhost(website)

        return {
            'success': True,
            'domain': domain,
            'install_url': f"http://{domain}/wp-admin/install.php",
            'db_name': db_name,
            'db_user': db_user,
            'db_pass': db_pass
        }

    except Exception as e:
        logger.error(f"Failed to install WordPress for {domain}: {e}")
        return {'success': False, 'error': str(e)}


def _generate_wp_config(doc_root: Path, db_name: str, db_user: str, db_pass: str):
    """Write wp-config.php with secure salts."""
    salts = "\n".join([
        f"define('{key}', '{secrets.token_urlsafe(48)}');"
        for key in [
            'AUTH_KEY', 'SECURE_AUTH_KEY', 'LOGGED_IN_KEY', 'NONCE_KEY',
            'AUTH_SALT', 'SECURE_AUTH_SALT', 'LOGGED_IN_SALT', 'NONCE_SALT'
        ]
    ])

    wp_config = f"""<?php
define('DB_NAME', '{db_name}');
define('DB_USER', '{db_user}');
define('DB_PASSWORD', '{db_pass}');
define('DB_HOST', 'localhost');
define('DB_CHARSET', 'utf8mb4');
define('DB_COLLATE', '');

{salts}

$table_prefix = 'wp_';
define('WP_DEBUG', false);

if ( ! defined( 'ABSPATH' ) ) {{
    define( 'ABSPATH', __DIR__ . '/' );
}}
require_once ABSPATH . 'wp-settings.php';
"""
    (doc_root / 'wp-config.php').write_text(wp_config)
