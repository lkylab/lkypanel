"""
Core file manager operations for LkyPanel.
All privileged operations run via sudo (shell=False), matching the rest of LkyPanel.
"""
import os
import json
import stat
import subprocess
import zipfile
import tarfile
import shutil
from django.http import JsonResponse, FileResponse, Http404


def _run(cmd, input=None, timeout=30, cwd=None):
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
    payload = {'status': 1}
    if data:
        payload.update(data)
    return JsonResponse(payload)


def err(msg, status=200):
    return JsonResponse({'status': 0, 'error': msg}, status=status)


# ── List directory via sudo ls ─────────────────────────────────────────────

def list_dir(base, rel_path, page=1, per_page=100, sort='name', reverse=False, search=''):
    target = _safe_path(base, rel_path) if rel_path else os.path.realpath(base)
    if not target:
        return err('Invalid path.')

    # Use sudo ls to list — works regardless of lkypanel user permissions
    r = _run(['sudo', 'ls', '-la', '--group-directories-first', target])
    if r.returncode != 0:
        return err('Permission denied or path not found.')

    entries = []
    for line in r.stdout.splitlines():
        parts = line.split()
        if not parts or parts[0] == 'total' or len(parts) < 9:
            continue
        name = ' '.join(parts[8:])
        if name in ('.', '..'):
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

    # Sort
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


def trash_items(base, rel_dir, items):
    trash_path = os.path.join(os.path.realpath(base), '.trash')
    _run(['sudo', 'mkdir', '-p', trash_path])
    moved = []
    for name in items:
        src = _safe_path(base, os.path.join(rel_dir, name))
        if not src:
            return err(f'Invalid path: {name}')
        dst_name = name
        dst = os.path.join(trash_path, dst_name)
        counter = 1
        # check existence via sudo
        while _run(['sudo', 'test', '-e', dst]).returncode == 0:
            dst_name = f'{name}.{counter}'
            dst = os.path.join(trash_path, dst_name)
            counter += 1
        r = _run(['sudo', 'mv', src, dst])
        if r.returncode != 0:
            return err(r.stderr.strip())
        moved.append({'original': os.path.join(rel_dir, name), 'trash_name': dst_name})
    return ok({'moved': moved})


def delete_permanent(base, rel_dir, items):
    for name in items:
        target = _safe_path(base, os.path.join(rel_dir, name))
        if not target:
            return err(f'Invalid path: {name}')
        r = _run(['sudo', 'rm', '-rf', target])
        if r.returncode != 0:
            return err(r.stderr.strip())
    return ok()


def list_trash(base):
    trash_path = os.path.join(os.path.realpath(base), '.trash')
    r = _run(['sudo', 'ls', '-la', trash_path])
    if r.returncode != 0:
        return ok({'entries': []})
    entries = []
    for line in r.stdout.splitlines():
        parts = line.split()
        if not parts or parts[0] == 'total' or len(parts) < 9:
            continue
        name = ' '.join(parts[8:])
        if name in ('.', '..'):
            continue
        entries.append({
            'name': name,
            'is_dir': parts[0][0] == 'd',
            'size': int(parts[4]) if parts[4].isdigit() else 0,
            'mtime': parts[5] + ' ' + parts[6] + ' ' + parts[7],
        })
    return ok({'entries': entries})


def restore_trash(base, trash_names, original_paths):
    trash_path = os.path.join(os.path.realpath(base), '.trash')
    for trash_name, orig_rel in zip(trash_names, original_paths):
        src = os.path.join(trash_path, trash_name)
        dst = _safe_path(base, orig_rel)
        if not dst:
            return err(f'Invalid restore path: {orig_rel}')
        _run(['sudo', 'mkdir', '-p', os.path.dirname(dst)])
        r = _run(['sudo', 'mv', src, dst])
        if r.returncode != 0:
            return err(r.stderr.strip())
    return ok()


def empty_trash(base):
    trash_path = os.path.join(os.path.realpath(base), '.trash')
    r = _run(['sudo', 'rm', '-rf', trash_path])
    return ok() if r.returncode == 0 else err(r.stderr.strip())


def read_file(base, rel_path):
    target = _safe_path(base, rel_path)
    if not target:
        return err('Invalid path.')
    # Check size first
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
    # Write to tmp then sudo mv
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        for chunk in uploaded_file.chunks():
            tmp.write(chunk)
        tmp_path = tmp.name
    dst = os.path.join(dst_dir, filename)
    r = _run(['sudo', 'mv', tmp_path, dst])
    if r.returncode != 0:
        os.unlink(tmp_path)
        return err(r.stderr.strip())
    return ok({'filename': filename})


def download_file(base, rel_path):
    target = _safe_path(base, rel_path)
    if not target:
        raise Http404
    # Copy to tmp via sudo cat, stream it
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
    dst = _safe_path(base, rel_dest) if rel_dest else os.path.dirname(src)
    if not src or not dst:
        return err('Invalid path.')
    _run(['sudo', 'mkdir', '-p', dst])
    if src.endswith('.zip'):
        r = _run(['sudo', 'unzip', '-o', src, '-d', dst])
    elif src.endswith(('.tar.gz', '.tgz', '.tar.bz2', '.tar.xz', '.tar')):
        r = _run(['sudo', 'tar', '-xf', src, '-C', dst])
    else:
        return err('Unsupported archive format.')
    return ok() if r.returncode == 0 else err(r.stderr.strip())


def compress_items(base, rel_dir, items, archive_name, fmt):
    src_dir = _safe_path(base, rel_dir) if rel_dir else os.path.realpath(base)
    if not src_dir:
        return err('Invalid path.')
    
    if fmt == 'zip':
        filename = archive_name + '.zip'
        out = _safe_path(base, os.path.join(rel_dir, filename))
        if not out:
            return err('Invalid output path.')
        r = _run(['sudo', 'zip', '-r', filename] + items, cwd=src_dir)
    else:
        filename = archive_name + '.tar.gz'
        out = _safe_path(base, os.path.join(rel_dir, filename))
        if not out:
            return err('Invalid output path.')
        r = _run(['sudo', 'tar', '-czf', filename] + items, cwd=src_dir)

    return ok({'archive': filename}) if r.returncode == 0 else err(r.stderr.strip())


def change_permissions(base, rel_path, mode_octal, recursive):
    target = _safe_path(base, rel_path)
    if not target:
        return err('Invalid path.')
    cmd = ['sudo', 'chmod']
    if recursive:
        cmd.append('-R')
    cmd += [mode_octal, target]
    r = _run(cmd)
    return ok() if r.returncode == 0 else err(r.stderr.strip())


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
