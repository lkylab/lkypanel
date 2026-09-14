"""
W3Panel v2 — Account Backups Manager
Archives public web files and dumps databases into compressed .tar.gz archives.
"""
import os
import subprocess
import tarfile
import logging
from pathlib import Path
from django.utils import timezone

logger = logging.getLogger('w3panel.backup')
BACKUP_BASE_DIR = Path('/var/lib/w3panel/backups')


def create_user_backup(user) -> dict:
    """
    Generate snapshot archive of user document roots and databases.
    """
    username = user.username
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    filename = f"backup_{username}_{timestamp}.tar.gz"
    
    user_backup_dir = BACKUP_BASE_DIR / username
    user_backup_dir.mkdir(parents=True, exist_ok=True)
    archive_path = user_backup_dir / filename

    user_home_dir = Path(f"/home/{username}")
    
    try:
        with tarfile.open(archive_path, "w:gz") as tar:
            if user_home_dir.exists():
                tar.add(user_home_dir, arcname="home")
            
            # Dump user databases
            from packages.core.models import Database
            user_dbs = Database.objects.filter(owner=user)
            for db in user_dbs:
                sql_temp = user_backup_dir / f"{db.name}.sql"
                try:
                    cmd = ['sudo', 'mysqldump', db.name]
                    with open(sql_temp, 'w') as f:
                        subprocess.run(cmd, stdout=f, timeout=30)
                    if sql_temp.exists() and sql_temp.stat().st_size > 0:
                        tar.add(sql_temp, arcname=f"databases/{db.name}.sql")
                        sql_temp.unlink()
                except Exception:
                    pass

        size_mb = round(archive_path.stat().st_size / (1024 * 1024), 2)
        return {'success': True, 'name': filename, 'path': str(archive_path), 'size_mb': max(size_mb, 0.1)}
    except Exception as e:
        logger.error(f"Backup creation error for {username}: {e}")
        return {'success': False, 'error': str(e)}


def delete_user_backup(username: str, filename: str) -> dict:
    """Delete archive file from disk."""
    archive_path = BACKUP_BASE_DIR / username / filename
    if archive_path.exists():
        try:
            archive_path.unlink()
        except Exception:
            pass
    return {'success': True}
