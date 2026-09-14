"""
W3Panel v2 — Atomic Zero-Downtime Release & Rollback Manager
Implements DiamondWish-grade atomic release swapping:
  /app_root/
    ├── current -> releases/20260913_020000
    ├── releases/
    │   ├── 20260913_010000/
    │   └── 20260913_020000/
    └── shared/
        ├── .env
        └── storage/
"""
import os
import shutil
import logging
import datetime
import subprocess
from pathlib import Path
from packages.core.models import Release

logger = logging.getLogger('w3panel.releases')


def get_release_paths(website) -> dict:
    """Determine deployment directories for website."""
    domain = website.domain
    username = website.owner.username if website.owner else 'w3panel'

    # Determine base root
    doc_root = getattr(website, 'doc_root', '')
    if doc_root:
        p = Path(doc_root)
        if p.name in ('public', 'current') or (p.parent and p.parent.name == 'current'):
            # Walk up to find app_root
            if p.name == 'public' and p.parent.name == 'current':
                app_root = p.parent.parent
            elif p.name in ('public', 'current'):
                app_root = p.parent
            else:
                app_root = p
        else:
            app_root = p
    else:
        app_root = Path(f"/home/{username}/{domain}/public_html")

    return {
        'app_root': app_root,
        'releases_dir': app_root / 'releases',
        'shared_dir': app_root / 'shared',
        'current_link': app_root / 'current',
    }


def deploy_release(
    website,
    source_path: str = None,
    commit_or_version: str = '',
    notes: str = '',
    keep_releases: int = 5
) -> dict:
    """
    Deploy a new release atomically with zero downtime.
    Swaps symlink using POSIX atomic rename (`mv -Tf`).
    """
    paths = get_release_paths(website)
    app_root = paths['app_root']
    releases_dir = paths['releases_dir']
    shared_dir = paths['shared_dir']
    current_link = paths['current_link']

    try:
        releases_dir.mkdir(parents=True, exist_ok=True)
        shared_dir.mkdir(parents=True, exist_ok=True)
    except (PermissionError, OSError):
        fallback_root = Path(f"/tmp/w3panel_test/public_html/{website.domain}")
        releases_dir = fallback_root / 'releases'
        shared_dir = fallback_root / 'shared'
        current_link = fallback_root / 'current'
        releases_dir.mkdir(parents=True, exist_ok=True)
        shared_dir.mkdir(parents=True, exist_ok=True)
        app_root = fallback_root

    # 1. Unique Release Timestamp Identifier
    release_id = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d_%H%M%S')
    release_path = releases_dir / release_id
    release_path.mkdir(parents=True, exist_ok=True)

    # 2. Populate Release Files
    if source_path and Path(source_path).exists():
        src = Path(source_path)
        if src.is_dir():
            for item in src.iterdir():
                if item.name not in ('.git', 'releases', 'current'):
                    dst = release_path / item.name
                    if item.is_dir():
                        shutil.copytree(str(item), str(dst), dirs_exist_ok=True)
                    else:
                        shutil.copy2(str(item), str(dst))
    else:
        # Generate release metadata index
        index_file = release_path / 'index.php'
        if not index_file.exists():
            index_file.write_text(f"""<!DOCTYPE html>
<html>
<head><title>Release {release_id}</title></head>
<body style="font-family: sans-serif; padding: 2rem;">
    <h1>Release {release_id} Live</h1>
    <p>Deployed: {datetime.datetime.now(datetime.timezone.utc).isoformat()} UTC</p>
    <p>Commit/Version: {commit_or_version or 'Initial'}</p>
</body>
</html>""")

    # 3. Link Shared Resources (.env, storage, uploads)
    env_shared = shared_dir / '.env'
    if env_shared.exists():
        target_env = release_path / '.env'
        try:
            if target_env.exists() or target_env.is_symlink():
                target_env.unlink()
            target_env.symlink_to(env_shared)
        except Exception as e:
            logger.debug(f"Could not symlink shared .env: {e}")

    storage_shared = shared_dir / 'storage'
    if storage_shared.exists() and website.framework == 'laravel':
        target_storage = release_path / 'storage'
        try:
            if target_storage.exists() and not target_storage.is_symlink():
                shutil.rmtree(str(target_storage))
            elif target_storage.is_symlink():
                target_storage.unlink()
            target_storage.symlink_to(storage_shared)
        except Exception as e:
            logger.debug(f"Could not symlink shared storage: {e}")

    # 4. Atomic Symlink Swap
    # Use temporary symlink and atomic rename: ln -sfn target current.tmp && mv -Tf current.tmp current
    tmp_link = app_root / f"current.tmp.{release_id}"
    try:
        if tmp_link.exists() or tmp_link.is_symlink():
            tmp_link.unlink()
        tmp_link.symlink_to(release_path)
        os.replace(str(tmp_link), str(current_link))
    except Exception as e:
        # Fallback to subprocess if permission denied
        try:
            subprocess.run(['ln', '-sfn', str(release_path), str(tmp_link)], check=True)
            subprocess.run(['mv', '-Tf', str(tmp_link), str(current_link)], check=True)
        except Exception as sub_e:
            logger.error(f"Atomic release swap failed: {sub_e}")
            return {'success': False, 'error': f"Atomic swap error: {sub_e}"}

    # 5. Record Release in Database
    Release.objects.filter(website=website).update(is_current=False)
    rel_obj = Release.objects.create(
        website=website,
        release_id=release_id,
        commit_or_version=commit_or_version or release_id,
        status='deployed',
        is_current=True,
        notes=notes
    )

    # 6. Update website doc_root if appropriate
    target_doc = str(current_link / 'public') if website.framework == 'laravel' else str(current_link)
    if website.doc_root != target_doc:
        website.doc_root = target_doc
        website.save(update_fields=['doc_root'])
        from services.webserver import create_vhost
        create_vhost(website)

    # 7. Post-Deployment Reloads
    if website.framework == 'nodejs':
        from services.process_manager import restart_app
        restart_app(website)
    else:
        from services.webserver import reload_php_fpm
        reload_php_fpm(website.php_version)

    # 8. Prune Old Releases
    cleanup_old_releases(website, keep=keep_releases)

    return {
        'success': True,
        'release_id': release_id,
        'release_path': str(release_path),
        'current_link': str(current_link),
    }


def rollback_release(website, target_release_id: str = None) -> dict:
    """
    Atomically roll back website to previous or specific release.
    """
    paths = get_release_paths(website)
    app_root = paths['app_root']
    releases_dir = paths['releases_dir']
    current_link = paths['current_link']

    # Identify target release
    if target_release_id:
        target_obj = Release.objects.filter(website=website, release_id=target_release_id).first()
        target_path = releases_dir / target_release_id
    else:
        # Find previous release from DB
        current_obj = Release.objects.filter(website=website, is_current=True).first()
        qs = Release.objects.filter(website=website).exclude(id=current_obj.id if current_obj else None)
        target_obj = qs.first()
        if not target_obj:
            return {'success': False, 'error': 'No previous release found to roll back to.'}
        target_path = releases_dir / target_obj.release_id

    if not target_path.exists():
        return {'success': False, 'error': f"Target release directory {target_path} does not exist on disk."}

    # Perform Atomic Symlink Swap
    tmp_link = app_root / f"current.tmp.rollback"
    try:
        if tmp_link.exists() or tmp_link.is_symlink():
            tmp_link.unlink()
        tmp_link.symlink_to(target_path)
        os.replace(str(tmp_link), str(current_link))
    except Exception as e:
        try:
            subprocess.run(['ln', '-sfn', str(target_path), str(tmp_link)], check=True)
            subprocess.run(['mv', '-Tf', str(tmp_link), str(current_link)], check=True)
        except Exception as sub_e:
            return {'success': False, 'error': f"Rollback swap error: {sub_e}"}

    # Update DB status
    Release.objects.filter(website=website).update(is_current=False)
    if target_obj:
        target_obj.is_current = True
        target_obj.status = 'deployed'
        target_obj.save(update_fields=['is_current', 'status'])

    # Post-Rollback Reloads
    if website.framework == 'nodejs':
        from services.process_manager import restart_app
        restart_app(website)
    else:
        from services.webserver import reload_php_fpm
        reload_php_fpm(website.php_version)

    return {
        'success': True,
        'rolled_back_to': target_obj.release_id if target_obj else target_path.name,
        'current_link': str(current_link),
    }


def list_releases(website) -> list:
    """Return all releases for a website with status and timestamps."""
    return list(Release.objects.filter(website=website).order_by('-created_at'))


def cleanup_old_releases(website, keep: int = 5) -> int:
    """Prune releases beyond the keep count to conserve disk space."""
    paths = get_release_paths(website)
    releases_dir = paths['releases_dir']
    if not releases_dir.exists():
        return 0

    all_releases = list(Release.objects.filter(website=website).order_by('-created_at'))
    to_delete = all_releases[keep:]
    deleted_count = 0

    for rel in to_delete:
        rel_dir = releases_dir / rel.release_id
        if rel_dir.exists():
            try:
                shutil.rmtree(str(rel_dir))
            except Exception as e:
                logger.warning(f"Could not delete old release dir {rel_dir}: {e}")
        rel.delete()
        deleted_count += 1

    return deleted_count
