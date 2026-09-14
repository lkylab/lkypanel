"""
W3Panel v2 — File Manager Core Operations
All privileged operations run via sudo (shell=False), matching the W3Panel pattern.
"""
import os
import json
import stat
import subprocess
import zipfile
import tarfile
import shutil
import tempfile
import re
from pathlib import Path
from django.utils import timezone
from django.http import JsonResponse, FileResponse, Http404


def _run(cmd, input=None, timeout=30, cwd=None):
    """Run command with subprocess, no shell."""
    return subprocess.run(cmd, shell=False, capture_output=True, text=True,
                          input=input, timeout=timeout, cwd=cwd)


def _safe_path(base: str, requested: str) -> str | None:
    """Resolve requested path and verify it stays inside base."""
    try:
        full = os.path.normpath(os.path.join(base, requested.lstrip('/')))
        base_real = os.path.realpath(base)
        full_real = os.path.realpath(full)
        if full_real == base_real or full_real.startswith(base_real + os.sep):
            return full_real
    except Exception:
        pass
    return None


def ok(data=None):
    """Success response."""
    payload = {'status': 1}
    if data:
        payload.update(data)
    return JsonResponse(payload)


def err(msg, status=200):
    """Error response."""
    return JsonResponse({'status': 0, 'error': msg}, status=status)


def list_dir(base, rel_path, page=1, per_page=100, sort='name', reverse=False, search=''):
    """List directory contents via sudo ls."""
    target = _safe_path(base, rel_path) if rel_path else os.path.realpath(base)
    if not target:
        return err('Invalid path.')

    r = _run(['sudo', 'ls', '-la', '--group-directories-first', target])
    if r.returncode != 0:
        return err('Permission denied or path not found.')

    entries = []
    for line in r.stdout.splitlines():
        parts = line.split()
        if not parts or parts[0] == 'total' or len(parts) < 9:
            continue
        name = ' '.join(parts[8:])
        if name in ('.', '..', '.trash_info.json'):
            continue
        if search and search.lower() not in name.lower():
            continue
        is_dir = parts[0][0] == 'd'
        is_link = parts[0][0] == 'l'
        try:
            size = int(parts[4])
        except ValueError:
            size = 0
        entries.append({
            'name': name,
            'is_dir': is_dir,
            'is_link': is_link,
            'size': size,
            'mtime': parts[5] + ' ' + parts[6] + ' ' + parts[7],
            'perms': parts[0],
        })

    key_map = {
        'name': lambda e: (not e['is_dir'], e['name'].lower()),
        'size': lambda e: (not e['is_dir'], e['size']),
        'mtime': lambda e: (not e['is_dir'], e['mtime']),
    }
    entries.sort(key=key_map.get(sort, key_map['name']), reverse=reverse)

    total = len(entries)
    start = (page - 1) * per_page
    page_entries = entries[start:start + per_page]

    base_real = os.path.realpath(base)
    rel = os.path.relpath(target, base_real)
    crumbs = []
    if rel != '.':
        parts = rel.split(os.sep)
        for i, part in enumerate(parts):
            crumbs.append({'name': part, 'path': os.sep.join(parts[:i + 1])})

    return ok({
        'path': '' if rel == '.' else rel,
        'entries': page_entries,
        'total': total,
        'page': page,
        'per_page': per_page,
        'breadcrumbs': crumbs,
    })


def create_file(base, rel_path):
    target = _safe_path(base, rel_path)
    if not target:
        return err('Invalid path.')
    r = _run(['sudo', 'touch', target])
    return ok() if r.returncode == 0 else err(r.stderr.strip())


def create_folder(base, rel_path):
    target = _safe_path(base, rel_path)
    if not target:
        return err('Invalid path.')
    r = _run(['sudo', 'mkdir', target])
    return ok() if r.returncode == 0 else err(r.stderr.strip())


def rename(base, rel_dir, old_name, new_name):
    if '/' in new_name or '\\' in new_name or new_name in ('.', '..'):
        return err('Invalid name.')
    src = _safe_path(base, os.path.join(rel_dir, old_name))
    dst = _safe_path(base, os.path.join(rel_dir, new_name))
    if not src or not dst:
        return err('Invalid path.')
    r = _run(['sudo', 'mv', src, dst])
    return ok() if r.returncode == 0 else err(r.stderr.strip())


def copy_items(base, src_dir, items, dst_dir):
    dst = _safe_path(base, dst_dir)
    if not dst:
        return err('Invalid destination.')
    _run(['sudo', 'mkdir', '-p', dst])
    for name in items:
        src = _safe_path(base, os.path.join(src_dir, name))
        if not src:
            return err(f'Invalid path: {name}')
        r = _run(['sudo', 'cp', '-r', src, dst])
        if r.returncode != 0:
            return err(r.stderr.strip())
    return ok()


def move_items(base, src_dir, items, dst_dir):
    dst = _safe_path(base, dst_dir)
    if not dst:
        return err('Invalid destination.')
    _run(['sudo', 'mkdir', '-p', dst])
    for name in items:
        src = _safe_path(base, os.path.join(src_dir, name))
        if not src:
            return err(f'Invalid path: {name}')
        r = _run(['sudo', 'mv', src, dst])
        if r.returncode != 0:
            return err(r.stderr.strip())
    return ok()


def _get_trash_info_path(base):
    return os.path.join(os.path.realpath(base), '.trash', '.trash_info.json')


def _load_trash_info(base):
    info_path = _get_trash_info_path(base)
    try:
        if os.path.isfile(info_path):
            with open(info_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        r = _run(['sudo', 'cat', info_path])
        if r.returncode == 0 and r.stdout.strip():
            return json.loads(r.stdout)
    except Exception:
        pass
    return {}


def _save_trash_info(base, info_data):
    trash_dir = os.path.join(os.path.realpath(base), '.trash')
    _run(['sudo', 'mkdir', '-p', trash_dir])
    info_path = _get_trash_info_path(base)
    try:
        data_str = json.dumps(info_data, indent=2)
        _run(['sudo', 'tee', info_path], input=data_str)
    except Exception:
        pass


def trash_items(base, rel_dir, items):
    trash_path = os.path.join(os.path.realpath(base), '.trash')
    _run(['sudo', 'mkdir', '-p', trash_path])
    info_data = _load_trash_info(base)
    moved = []
    for item in items:
        orig_rel = os.path.normpath(os.path.join(rel_dir, item)).lstrip(os.sep)
        src = _safe_path(base, orig_rel)
        if not src:
            return err(f'Invalid path: {item}')
        if _run(['sudo', 'test', '-e', src]).returncode != 0:
            continue

        base_name = os.path.basename(orig_rel)
        dst_name = base_name
        dst = os.path.join(trash_path, dst_name)
        counter = 1
        while _run(['sudo', 'test', '-e', dst]).returncode == 0:
            dst_name = f'{base_name}.{counter}'
            dst = os.path.join(trash_path, dst_name)
            counter += 1

        r = _run(['sudo', 'mv', src, dst])
        if r.returncode != 0:
            return err(r.stderr.strip() or f'Failed to trash {item}')

        info_data[dst_name] = {
            'original_path': orig_rel,
            'deleted_at': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        moved.append({'original': orig_rel, 'trash_name': dst_name})

    _save_trash_info(base, info_data)
    return ok({'moved': moved, 'trashed_count': len(moved)})


def delete_permanent(base, rel_dir, items):
    info_data = _load_trash_info(base)
    changed_info = False
    for name in items:
        target = _safe_path(base, os.path.join(rel_dir, name))
        if not target:
            return err(f'Invalid path: {name}')
        r = _run(['sudo', 'rm', '-rf', target])
        if r.returncode != 0:
            return err(r.stderr.strip())
        base_name = os.path.basename(name.strip('/'))
        if base_name in info_data:
            del info_data[base_name]
            changed_info = True

    if changed_info:
        _save_trash_info(base, info_data)
    return ok()


def list_trash(base):
    trash_path = os.path.join(os.path.realpath(base), '.trash')
    info_data = _load_trash_info(base)
    r = _run(['sudo', 'ls', '-la', trash_path])
    if r.returncode != 0:
        return ok({'entries': []})
    entries = []
    for line in r.stdout.splitlines():
        parts = line.split()
        if not parts or parts[0] == 'total' or len(parts) < 9:
            continue
        name = ' '.join(parts[8:])
        if name in ('.', '..', '.trash_info.json'):
            continue
        orig_info = info_data.get(name, {})
        orig_path = orig_info.get('original_path', name) if isinstance(orig_info, dict) else str(orig_info or name)
        deleted_at = orig_info.get('deleted_at', '') if isinstance(orig_info, dict) else ''
        entries.append({
            'name': name,
            'is_dir': parts[0][0] == 'd',
            'size': int(parts[4]) if parts[4].isdigit() else 0,
            'mtime': parts[5] + ' ' + parts[6] + ' ' + parts[7],
            'original_path': orig_path,
            'deleted_at': deleted_at,
        })
    return ok({'entries': entries})


def restore_trash(base, trash_names, original_paths=None):
    trash_path = os.path.join(os.path.realpath(base), '.trash')
    info_data = _load_trash_info(base)
    restored = []

    orig_map = {}
    if original_paths and isinstance(original_paths, (list, tuple)):
        for t_name, o_path in zip(trash_names, original_paths):
            if o_path:
                orig_map[os.path.basename(t_name.strip('/'))] = o_path
    elif isinstance(original_paths, dict):
        orig_map = original_paths

    for t_name in trash_names:
        clean_name = os.path.basename(t_name.strip('/'))
        if not clean_name or clean_name == '.trash_info.json':
            continue
        src = os.path.join(trash_path, clean_name)
        if _run(['sudo', 'test', '-e', src]).returncode != 0:
            continue

        orig_rel = orig_map.get(clean_name)
        if not orig_rel:
            entry = info_data.get(clean_name)
            if isinstance(entry, dict) and entry.get('original_path'):
                orig_rel = entry['original_path']
            elif isinstance(entry, str):
                orig_rel = entry
            else:
                orig_rel = clean_name

        dst = _safe_path(base, orig_rel)
        if not dst:
            return err(f'Invalid restore path: {orig_rel}')

        parent_dst = os.path.dirname(dst)
        _run(['sudo', 'mkdir', '-p', parent_dst])
        r = _run(['sudo', 'mv', '-f', src, dst])
        if r.returncode != 0:
            return err(r.stderr.strip() or f'Failed to restore {clean_name}')

        if clean_name in info_data:
            del info_data[clean_name]
        restored.append({'trash_name': clean_name, 'restored_to': orig_rel})

    _save_trash_info(base, info_data)
    return ok({'restored': restored, 'restored_count': len(restored)})


def empty_trash(base):
    trash_path = os.path.join(os.path.realpath(base), '.trash')
    r = _run(['sudo', 'rm', '-rf', trash_path])
    if r.returncode != 0:
        return err(r.stderr.strip() or 'Failed to empty trash')
    _run(['sudo', 'mkdir', '-p', trash_path])
    _save_trash_info(base, {})
    return ok({'emptied': True})


def read_file(base, rel_path):
    target = _safe_path(base, rel_path)
    if not target:
        return err('Invalid path.')
    r_size = _run(['sudo', 'stat', '-c', '%s', target])
    try:
        size = int(r_size.stdout.strip())
        if size > 2 * 1024 * 1024:
            return err('File too large to edit (max 2 MB).')
    except ValueError:
        pass
    r = _run(['sudo', 'cat', target])
    if r.returncode != 0:
        return err(r.stderr.strip())
    return JsonResponse({'status': 1, 'content': r.stdout, 'path': rel_path})


def write_file(base, rel_path, content):
    target = _safe_path(base, rel_path)
    if not target:
        return err('Invalid path.')
    r = _run(['sudo', 'tee', target], input=content)
    return ok() if r.returncode == 0 else err(r.stderr.strip())


def upload_file(base, rel_dir, uploaded_file):
    dst_dir = _safe_path(base, rel_dir) if rel_dir else os.path.realpath(base)
    if not dst_dir:
        return err('Invalid path.')
    filename = os.path.basename(uploaded_file.name)
    if not filename or filename in ('.', '..'):
        return err('Invalid filename.')
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        for chunk in uploaded_file.chunks():
            tmp.write(chunk)
        tmp_path = tmp.name
    dst = os.path.join(dst_dir, filename)
    r = _run(['sudo', 'mv', tmp_path, dst])
    if r.returncode != 0:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        return err(r.stderr.strip())
    _run(['sudo', 'chmod', '0644', dst])
    return ok({'filename': filename})


def download_file(base, rel_path):
    target = _safe_path(base, rel_path)
    if not target or not os.path.exists(target) or os.path.isdir(target):
        raise Http404
    try:
        f = open(target, 'rb')
        return FileResponse(f, as_attachment=True, filename=os.path.basename(target))
    except Exception:
        r = _run(['sudo', 'cat', target])
        if r.returncode != 0:
            raise Http404
        from django.http import HttpResponse
        response = HttpResponse(r.stdout.encode('utf-8', errors='replace'),
                                content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{os.path.basename(target)}"'
        return response


def extract_archive(base, rel_archive, rel_dest):
    src = _safe_path(base, rel_archive)
    dst = _safe_path(base, rel_dest) if rel_dest else (os.path.dirname(src) if src else None)
    if not src or not dst:
        return err('Invalid path.')
    _run(['sudo', 'mkdir', '-p', dst])
    try:
        if src.endswith('.zip'):
            if shutil.which('unzip'):
                r = _run(['sudo', 'unzip', '-o', src, '-d', dst])
                if r.returncode != 0:
                    with zipfile.ZipFile(src, 'r') as z:
                        z.extractall(dst)
            else:
                with zipfile.ZipFile(src, 'r') as z:
                    z.extractall(dst)
        elif src.endswith(('.tar.gz', '.tgz', '.tar.bz2', '.tar.xz', '.tar')):
            if shutil.which('tar'):
                r = _run(['sudo', 'tar', '-xf', src, '-C', dst])
                if r.returncode != 0:
                    with tarfile.open(src, 'r:*') as t:
                        t.extractall(dst)
            else:
                with tarfile.open(src, 'r:*') as t:
                    t.extractall(dst)
        else:
            return err('Unsupported archive format.')
    except Exception as e:
        return err(f'Extraction error: {e}')

    # Normalize extracted file permissions
    _run(['sudo', 'find', dst, '-type', 'd', '-exec', 'chmod', '0755', '{}', '+'])
    _run(['sudo', 'find', dst, '-type', 'f', '-exec', 'chmod', '0644', '{}', '+'])
    return ok()


def _zip_with_python(src_dir: str, items: list, out_path: str):
    with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for item in items:
            item_full = os.path.join(src_dir, item)
            if os.path.isdir(item_full):
                for root, _, files in os.walk(item_full):
                    for f in files:
                        file_path = os.path.join(root, f)
                        arcname = os.path.relpath(file_path, src_dir)
                        zipf.write(file_path, arcname)
            elif os.path.exists(item_full):
                zipf.write(item_full, item)


def _tar_with_python(src_dir: str, items: list, out_path: str):
    with tarfile.open(out_path, 'w:gz') as tarf:
        for item in items:
            item_full = os.path.join(src_dir, item)
            if os.path.exists(item_full):
                tarf.add(item_full, arcname=item)


def compress_items(base, rel_dir, items, archive_name, fmt, dest_dir=None):
    src_dir = _safe_path(base, rel_dir) if rel_dir else os.path.realpath(base)
    target_dest = dest_dir.strip('/') if dest_dir is not None else (rel_dir.strip('/') if rel_dir else '')
    dst_dir = _safe_path(base, target_dest) if target_dest else os.path.realpath(base)
    if not src_dir or not dst_dir:
        return err('Invalid path.')
    if not re.match(r'^[a-zA-Z0-9_.-]+$', archive_name):
        return err('Invalid archive name.')

    clean_name = archive_name
    if fmt == 'zip':
        if not clean_name.endswith('.zip'):
            clean_name += '.zip'
        out = os.path.join(dst_dir, clean_name)
        if not _safe_path(base, os.path.join(target_dest, clean_name)):
            return err('Invalid output path.')
        try:
            if shutil.which('zip'):
                r = _run(['sudo', 'zip', '-r', out] + items, cwd=src_dir)
                if r.returncode != 0:
                    _zip_with_python(src_dir, items, out)
            else:
                _zip_with_python(src_dir, items, out)
        except Exception as e:
            return err(f'Zip error: {e}')
    else:
        if not clean_name.endswith('.tar.gz') and not clean_name.endswith('.tgz'):
            clean_name += '.tar.gz'
        out = os.path.join(dst_dir, clean_name)
        if not _safe_path(base, os.path.join(target_dest, clean_name)):
            return err('Invalid output path.')
        try:
            if shutil.which('tar'):
                r = _run(['sudo', 'tar', '-czf', out] + items, cwd=src_dir)
                if r.returncode != 0:
                    _tar_with_python(src_dir, items, out)
            else:
                _tar_with_python(src_dir, items, out)
        except Exception as e:
            return err(f'Tar error: {e}')

    _run(['sudo', 'chmod', '0644', out])
    return ok({'archive': clean_name, 'dest_path': target_dest})


def change_permissions(base, rel_path, mode_octal, recursive):
    target = _safe_path(base, rel_path)
    if not target:
        return err('Invalid path.')
    clean_mode = str(mode_octal).strip()
    if not re.match(r'^[0-7]{3,4}$', clean_mode):
        return err('Invalid octal mode.')
    cmd = ['sudo', 'chmod']
    if recursive:
        cmd.append('-R')
    cmd += [clean_mode, target]
    r = _run(cmd)
    return ok() if r.returncode == 0 else err(r.stderr.strip())


def fix_permissions(base: str, rel_path: str = '', username: str = None) -> dict:
    """
    Recursively normalize permissions for web applications (WordPress, Laravel, PHP):
    - Directories: 0755
    - Files: 0644
    - Ownership: {username}:{username}
    - Base directory traversal: 0755
    """
    target = _safe_path(base, rel_path) if rel_path else os.path.realpath(base)
    if not target:
        return err('Invalid path.')

    # 1. Directories to 0755
    _run(['sudo', 'find', target, '-type', 'd', '-exec', 'chmod', '0755', '{}', '+'])

    # 2. Files to 0644
    _run(['sudo', 'find', target, '-type', 'f', '-exec', 'chmod', '0644', '{}', '+'])

    # 3. Ownership
    if username:
        check = _run(['id', '-u', username])
        if check.returncode == 0:
            _run(['sudo', 'chown', '-R', f'{username}:{username}', target])
        _run(['sudo', 'chmod', '0755', os.path.realpath(base)])

    return ok({'message': 'Permissions normalized successfully (Directories: 0755, Files: 0644).'})


def disk_usage(base):
    base_real = os.path.realpath(base)
    r = _run(['sudo', 'du', '-sb', base_real])
    used = 0
    try:
        used = int(r.stdout.split()[0])
    except Exception:
        pass
    try:
        st = os.statvfs(base_real)
        free = st.f_bavail * st.f_frsize
        total = st.f_blocks * st.f_frsize
    except Exception:
        free = total = 0
    return ok({'used': used, 'free': free, 'total': total})


def search_files(base: str, rel_path: str = '', query: str = '',
                 time_filter: str = '', mtime_from: int = 0, mtime_to: int = 0,
                 type_filter: str = 'all', size_filter: str = 'all',
                 size_min: int = 0, size_max: int = 0, max_results: int = 500):
    """
    Search recursively for files and directories matching query & filter criteria under base / rel_path.
    Filters:
    - query: name substring (case-insensitive)
    - time_filter: '1h', '24h', '7d', '30d', '90d', '365d', 'custom'
    - mtime_from / mtime_to: unix timestamps for custom date range
    - type_filter: 'all', 'files', 'dirs', 'code', 'images', 'archives'
    - size_filter: 'all', 'empty', 'small' (<100KB), 'medium' (>1MB), 'large' (>10MB), 'huge' (>100MB), 'custom'
    - size_min / size_max: byte limits
    """
    import time
    target = _safe_path(base, rel_path) if rel_path else os.path.realpath(base)
    if not target or not os.path.exists(target):
        return ok({'results': []})
    if os.path.isfile(target):
        target = os.path.dirname(target)

    base_real = os.path.realpath(base)
    q_low = (query or '').strip().lower()
    time_filter = (time_filter or '').strip().lower()
    type_filter = (type_filter or 'all').strip().lower()
    size_filter = (size_filter or 'all').strip().lower()

    # Calculate time bounds
    now_ts = int(time.time())
    min_mtime = 0
    max_mtime = 0
    if time_filter == '1h':
        min_mtime = now_ts - 3600
    elif time_filter == '24h':
        min_mtime = now_ts - 86400
    elif time_filter == '7d':
        min_mtime = now_ts - 7 * 86400
    elif time_filter == '30d':
        min_mtime = now_ts - 30 * 86400
    elif time_filter == '90d':
        min_mtime = now_ts - 90 * 86400
    elif time_filter == '365d':
        min_mtime = now_ts - 365 * 86400
    elif time_filter == 'custom':
        if mtime_from > 0:
            min_mtime = mtime_from
        if mtime_to > 0:
            max_mtime = mtime_to

    # Calculate size bounds
    calc_min_size = -1
    calc_max_size = -1
    if size_filter == 'empty':
        calc_min_size = 0
        calc_max_size = 0
    elif size_filter == 'small':
        calc_max_size = 100 * 1024
    elif size_filter == 'medium':
        calc_min_size = 1024 * 1024
    elif size_filter == 'large':
        calc_min_size = 10 * 1024 * 1024
    elif size_filter == 'huge':
        calc_min_size = 100 * 1024 * 1024
    elif size_filter == 'custom':
        if size_min > 0:
            calc_min_size = size_min
        if size_max > 0:
            calc_max_size = size_max

    CODE_EXTS = {'.php', '.phtml', '.html', '.htm', '.css', '.scss', '.js', '.ts', '.jsx', '.tsx', '.json', '.sql', '.py', '.sh', '.env', '.htaccess', '.conf', '.ini', '.xml', '.txt', '.md', '.yaml', '.yml', '.c', '.cpp', '.h', '.java', '.go', '.rs'}
    IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico', '.bmp', '.tiff', '.avif'}
    ARCHIVE_EXTS = {'.zip', '.tar', '.gz', '.tgz', '.bz2', '.xz', '.rar', '.7z', '.iso'}

    # If no criteria is specified at all, return empty results
    has_criteria = bool(q_low) or (time_filter and time_filter != 'all') or (type_filter and type_filter != 'all') or (size_filter and size_filter != 'all')
    if not has_criteria:
        return ok({'results': []})

    results = []
    try:
        for root, dirs, files in os.walk(target):
            # Exclude hidden directories except .trash
            dirs[:] = [d for d in dirs if not d.startswith('.') or d in ('.trash',)]

            # Check directories
            include_dirs = type_filter in ('all', 'dirs') and size_filter in ('all', '')
            if include_dirs:
                for d in list(dirs):
                    if q_low and q_low not in d.lower():
                        continue
                    full_p = os.path.join(root, d)
                    try:
                        st = os.stat(full_p)
                        perms = oct(st.st_mode)[-4:] if len(oct(st.st_mode)) >= 4 else oct(st.st_mode)[-3:].zfill(4)
                        mtime_ts = int(st.st_mtime)
                    except Exception:
                        perms = "0755"
                        mtime_ts = 0

                    if min_mtime > 0 and mtime_ts < min_mtime:
                        continue
                    if max_mtime > 0 and mtime_ts > max_mtime:
                        continue

                    rel_p = os.path.relpath(full_p, base_real)
                    results.append({
                        'name': d,
                        'rel_path': rel_p,
                        'is_dir': True,
                        'size': 4096,
                        'perms': perms,
                        'mtime_ts': mtime_ts,
                    })
                    if len(results) >= max_results:
                        break

            if len(results) >= max_results:
                break

            # Check files
            if type_filter != 'dirs':
                for f in files:
                    if f == '.trash_info.json':
                        continue
                    if f.startswith('.') and f not in ('.htaccess', '.env', '.trash'):
                        continue
                    if q_low and q_low not in f.lower():
                        continue

                    ext = os.path.splitext(f)[1].lower()
                    if type_filter == 'code' and ext not in CODE_EXTS:
                        continue
                    if type_filter == 'images' and ext not in IMAGE_EXTS:
                        continue
                    if type_filter == 'archives' and ext not in ARCHIVE_EXTS:
                        continue

                    full_p = os.path.join(root, f)
                    try:
                        st = os.stat(full_p)
                        size = st.st_size
                        perms = oct(st.st_mode)[-4:] if len(oct(st.st_mode)) >= 4 else oct(st.st_mode)[-3:].zfill(4)
                        mtime_ts = int(st.st_mtime)
                    except Exception:
                        size = 0
                        perms = "0644"
                        mtime_ts = 0

                    if min_mtime > 0 and mtime_ts < min_mtime:
                        continue
                    if max_mtime > 0 and mtime_ts > max_mtime:
                        continue
                    if calc_min_size >= 0 and size < calc_min_size:
                        continue
                    if calc_max_size >= 0 and size > calc_max_size:
                        continue

                    rel_p = os.path.relpath(full_p, base_real)
                    results.append({
                        'name': f,
                        'rel_path': rel_p,
                        'is_dir': False,
                        'size': size,
                        'perms': perms,
                        'mtime_ts': mtime_ts,
                    })
                    if len(results) >= max_results:
                        break

            if len(results) >= max_results:
                break
    except Exception as e:
        return err(f"Search error: {str(e)}")

    return ok({'results': results})