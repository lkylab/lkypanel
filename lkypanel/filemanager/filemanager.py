"""
Core file manager operations for LkyPanel.
All operations use os.* / subprocess with shell=False — no shell string building.
Path traversal is blocked by resolving real paths and checking against the allowed root.
"""
import os
import shutil
import subprocess
import zipfile
import tarfile
import json
import stat
from pathlib import Path
from django.http import HttpResponse, JsonResponse, FileResponse, Http404
from lkypanel.audit import log_action


def _safe_path(base: str, requested: str) -> str | None:
    """
    Resolve `requested` and verify it is inside `base`.
    Returns the resolved absolute path string, or None if unsafe.
    """
    try:
        resolved = os.path.realpath(os.path.join(base, requested.lstrip('/')))
    except Exception:
        return None
    base_real = os.path.realpath(base)
    if resolved == base_real or resolved.startswith(base_real + os.sep):
        return resolved
    return None


def _entry_info(entry: os.DirEntry) -> dict:
    """Build a serialisable dict for a single directory entry."""
    try:
        st = entry.stat(follow_symlinks=False)
    except OSError:
        return None
    is_dir = stat.S_ISDIR(st.st_mode)
    is_link = stat.S_ISLNK(st.st_mode)
    return {
        'name': entry.name,
        'is_dir': is_dir,
        'is_link': is_link,
        'size': 0 if is_dir else st.st_size,
        'mtime': int(st.st_mtime),
        'perms': oct(stat.S_IMODE(st.st_mode)),
    }


def ok(data: dict = None) -> JsonResponse:
    payload = {'status': 1}
    if data:
        payload.update(data)
    return JsonResponse(payload)


def err(msg: str, status: int = 200) -> JsonResponse:
    return JsonResponse({'status': 0, 'error': msg}, status=status)


# ---------------------------------------------------------------------------
# Public API functions — each takes (base_path, ...) and returns JsonResponse
# ---------------------------------------------------------------------------

def list_dir(base: str, rel_path: str, page: int = 1, per_page: int = 100,
             sort: str = 'name', reverse: bool = False, search: str = '') -> JsonResponse:
    target = _safe_path(base, rel_path) if rel_path else os.path.realpath(base)
    if not target or not os.path.isdir(target):
        return err('Path not found or not a directory.')

    entries = []
    try:
        with os.scandir(target) as it:
            for entry in it:
                info = _entry_info(entry)
                if info:
                    entries.append(info)
    except PermissionError:
        return err('Permission denied.')

    if search:
        q = search.lower()
        entries = [e for e in entries if q in e['name'].lower()]

    # Sort: dirs first, then by field
    key_map = {
        'name': lambda e: (not e['is_dir'], e['name'].lower()),
        'size': lambda e: (not e['is_dir'], e['size']),
        'mtime': lambda e: (not e['is_dir'], e['mtime']),
    }
    entries.sort(key=key_map.get(sort, key_map['name']), reverse=reverse)

    total = len(entries)
    start = (page - 1) * per_page
    page_entries = entries[start:start + per_page]

    # Build breadcrumbs relative to base
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


def create_file(base: str, rel_path: str) -> JsonResponse:
    target = _safe_path(base, rel_path)
    if not target:
        return err('Invalid path.')
    if os.path.exists(target):
        return err('File already exists.')
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        Path(target).touch()
    except OSError as e:
        return err(str(e))
    return ok()


def create_folder(base: str, rel_path: str) -> JsonResponse:
    target = _safe_path(base, rel_path)
    if not target:
        return err('Invalid path.')
    try:
        os.makedirs(target, exist_ok=False)
    except FileExistsError:
        return err('Folder already exists.')
    except OSError as e:
        return err(str(e))
    return ok()


def rename(base: str, rel_dir: str, old_name: str, new_name: str) -> JsonResponse:
    if '/' in new_name or '\\' in new_name or new_name in ('.', '..'):
        return err('Invalid name.')
    src = _safe_path(base, os.path.join(rel_dir, old_name))
    dst = _safe_path(base, os.path.join(rel_dir, new_name))
    if not src or not dst:
        return err('Invalid path.')
    if not os.path.exists(src):
        return err('Source not found.')
    if os.path.exists(dst):
        return err('Destination already exists.')
    try:
        os.rename(src, dst)
    except OSError as e:
        return err(str(e))
    return ok()


def copy_items(base: str, src_dir: str, items: list, dst_dir: str) -> JsonResponse:
    dst_base = _safe_path(base, dst_dir)
    if not dst_base:
        return err('Invalid destination.')
    os.makedirs(dst_base, exist_ok=True)
    for name in items:
        src = _safe_path(base, os.path.join(src_dir, name))
        if not src or not os.path.exists(src):
            return err(f'Source not found: {name}')
        dst = os.path.join(dst_base, name)
        try:
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
        except OSError as e:
            return err(str(e))
    return ok()


def move_items(base: str, src_dir: str, items: list, dst_dir: str) -> JsonResponse:
    dst_base = _safe_path(base, dst_dir)
    if not dst_base:
        return err('Invalid destination.')
    os.makedirs(dst_base, exist_ok=True)
    for name in items:
        src = _safe_path(base, os.path.join(src_dir, name))
        if not src or not os.path.exists(src):
            return err(f'Source not found: {name}')
        dst = os.path.join(dst_base, name)
        try:
            shutil.move(src, dst)
        except OSError as e:
            return err(str(e))
    return ok()


def trash_items(base: str, rel_dir: str, items: list, trash_dir: str) -> JsonResponse:
    """Move items to trash folder, recording original paths."""
    trash_path = os.path.join(base, '.trash')
    os.makedirs(trash_path, exist_ok=True)
    moved = []
    for name in items:
        src = _safe_path(base, os.path.join(rel_dir, name))
        if not src or not os.path.exists(src):
            return err(f'Not found: {name}')
        # Avoid collisions in trash
        dst_name = name
        dst = os.path.join(trash_path, dst_name)
        counter = 1
        while os.path.exists(dst):
            dst_name = f'{name}.{counter}'
            dst = os.path.join(trash_path, dst_name)
            counter += 1
        try:
            shutil.move(src, dst)
            moved.append({'original': os.path.join(rel_dir, name), 'trash_name': dst_name})
        except OSError as e:
            return err(str(e))
    return ok({'moved': moved})


def delete_permanent(base: str, rel_dir: str, items: list) -> JsonResponse:
    for name in items:
        target = _safe_path(base, os.path.join(rel_dir, name))
        if not target or not os.path.exists(target):
            continue
        try:
            if os.path.isdir(target) and not os.path.islink(target):
                shutil.rmtree(target)
            else:
                os.remove(target)
        except OSError as e:
            return err(str(e))
    return ok()


def list_trash(base: str) -> JsonResponse:
    trash_path = os.path.join(base, '.trash')
    if not os.path.isdir(trash_path):
        return ok({'entries': []})
    entries = []
    try:
        with os.scandir(trash_path) as it:
            for entry in it:
                info = _entry_info(entry)
                if info:
                    entries.append(info)
    except PermissionError:
        return err('Permission denied.')
    return ok({'entries': entries})


def restore_trash(base: str, trash_names: list, original_paths: list) -> JsonResponse:
    trash_path = os.path.join(base, '.trash')
    for trash_name, orig_rel in zip(trash_names, original_paths):
        src = os.path.join(trash_path, trash_name)
        if not os.path.exists(src):
            return err(f'Trash item not found: {trash_name}')
        dst = _safe_path(base, orig_rel)
        if not dst:
            return err(f'Invalid restore path: {orig_rel}')
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        try:
            shutil.move(src, dst)
        except OSError as e:
            return err(str(e))
    return ok()


def empty_trash(base: str) -> JsonResponse:
    trash_path = os.path.join(base, '.trash')
    if os.path.isdir(trash_path):
        try:
            shutil.rmtree(trash_path)
        except OSError as e:
            return err(str(e))
    return ok()


def read_file(base: str, rel_path: str) -> JsonResponse:
    target = _safe_path(base, rel_path)
    if not target or not os.path.isfile(target):
        return err('File not found.')
    size = os.path.getsize(target)
    if size > 2 * 1024 * 1024:  # 2 MB limit for editor
        return err('File too large to edit (max 2 MB).')
    try:
        with open(target, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
    except OSError as e:
        return err(str(e))
    return ok({'content': content, 'path': rel_path})


def write_file(base: str, rel_path: str, content: str) -> JsonResponse:
    target = _safe_path(base, rel_path)
    if not target:
        return err('Invalid path.')
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, 'w', encoding='utf-8') as f:
            f.write(content)
    except OSError as e:
        return err(str(e))
    return ok()


def upload_file(base: str, rel_dir: str, uploaded_file) -> JsonResponse:
    dst_dir = _safe_path(base, rel_dir) if rel_dir else os.path.realpath(base)
    if not dst_dir:
        return err('Invalid path.')
    os.makedirs(dst_dir, exist_ok=True)
    # Sanitise filename
    filename = os.path.basename(uploaded_file.name)
    if not filename or filename in ('.', '..'):
        return err('Invalid filename.')
    dst = os.path.join(dst_dir, filename)
    # Verify dst is still inside base after joining
    if not (dst == os.path.realpath(base) or dst.startswith(os.path.realpath(base) + os.sep)):
        return err('Invalid path.')
    try:
        with open(dst, 'wb') as f:
            for chunk in uploaded_file.chunks():
                f.write(chunk)
    except OSError as e:
        return err(str(e))
    return ok({'filename': filename})


def download_file(base: str, rel_path: str):
    target = _safe_path(base, rel_path)
    if not target or not os.path.isfile(target):
        raise Http404
    try:
        response = FileResponse(open(target, 'rb'), as_attachment=True,
                                filename=os.path.basename(target))
        return response
    except OSError:
        raise Http404


def extract_archive(base: str, rel_archive: str, rel_dest: str) -> JsonResponse:
    src = _safe_path(base, rel_archive)
    dst = _safe_path(base, rel_dest) if rel_dest else os.path.dirname(src)
    if not src or not os.path.isfile(src):
        return err('Archive not found.')
    if not dst:
        return err('Invalid destination.')
    os.makedirs(dst, exist_ok=True)
    try:
        if src.endswith('.zip'):
            with zipfile.ZipFile(src, 'r') as z:
                z.extractall(dst)
        elif src.endswith(('.tar.gz', '.tgz', '.tar.bz2', '.tar.xz', '.tar')):
            with tarfile.open(src, 'r:*') as t:
                t.extractall(dst)
        else:
            return err('Unsupported archive format.')
    except Exception as e:
        return err(str(e))
    return ok()


def compress_items(base: str, rel_dir: str, items: list, archive_name: str, fmt: str) -> JsonResponse:
    src_dir = _safe_path(base, rel_dir) if rel_dir else os.path.realpath(base)
    if not src_dir:
        return err('Invalid path.')
    if fmt == 'zip':
        out_path = _safe_path(base, os.path.join(rel_dir, archive_name + '.zip'))
    else:
        out_path = _safe_path(base, os.path.join(rel_dir, archive_name + '.tar.gz'))
    if not out_path:
        return err('Invalid output path.')
    try:
        if fmt == 'zip':
            with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED) as z:
                for name in items:
                    src = _safe_path(base, os.path.join(rel_dir, name))
                    if not src:
                        continue
                    if os.path.isdir(src):
                        for root, dirs, files in os.walk(src):
                            for file in files:
                                fp = os.path.join(root, file)
                                z.write(fp, os.path.relpath(fp, src_dir))
                    else:
                        z.write(src, os.path.relpath(src, src_dir))
        else:
            with tarfile.open(out_path, 'w:gz') as t:
                for name in items:
                    src = _safe_path(base, os.path.join(rel_dir, name))
                    if src:
                        t.add(src, arcname=name)
    except Exception as e:
        return err(str(e))
    return ok({'archive': os.path.basename(out_path)})


def change_permissions(base: str, rel_path: str, mode_octal: str, recursive: bool) -> JsonResponse:
    target = _safe_path(base, rel_path)
    if not target or not os.path.exists(target):
        return err('Path not found.')
    try:
        mode = int(mode_octal, 8)
    except ValueError:
        return err('Invalid permission value.')
    try:
        if recursive and os.path.isdir(target):
            for root, dirs, files in os.walk(target):
                os.chmod(root, mode)
                for f in files:
                    os.chmod(os.path.join(root, f), mode)
        else:
            os.chmod(target, mode)
    except OSError as e:
        return err(str(e))
    return ok()


def disk_usage(base: str) -> JsonResponse:
    """Return used bytes under base path."""
    total = 0
    try:
        for root, dirs, files in os.walk(base):
            for f in files:
                fp = os.path.join(root, f)
                try:
                    total += os.path.getsize(fp)
                except OSError:
                    pass
    except Exception:
        pass
    stat_vfs = os.statvfs(base)
    free = stat_vfs.f_bavail * stat_vfs.f_frsize
    disk_total = stat_vfs.f_blocks * stat_vfs.f_frsize
    return ok({'used': total, 'free': free, 'total': disk_total})
