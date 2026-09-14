"""
W3Panel v2 — File Manager Views
User-facing file manager for website files.
"""
import json
import os
from pathlib import Path
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect

from packages.core.models import User, Website
from packages.core.auth import get_current_user
from apps.filemanager import filemanager as fm
from apps.filemanager.models import FileManagerBookmark


def _base(user: User, website: Website = None) -> str:
    """Get base path for file operations."""
    if website:
        return website.doc_root or f"/home/{user.username}/{website.domain}/public_html"
    return f"/home/{user.username}"


def _ip(request) -> str:
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


def user_filemanager(request, website_id=None):
    """Render file manager page."""
    user = get_current_user(request)
    if not user:
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    website = None
    if website_id:
        website = get_object_or_404(Website, id=website_id, owner=user)

    base_path = Path(_base(user, website))
    base_path.mkdir(parents=True, exist_ok=True)

    bookmarks = FileManagerBookmark.objects.filter(user=user)
    if website:
        bookmarks = bookmarks.filter(website=website)
    else:
        bookmarks = bookmarks.filter(website__isnull=True)

    return render(request, 'user/filemanager.html', {
        'user': user,
        'website': website,
        'base_path': str(base_path),
        'bookmarks': bookmarks,
        'active_page': 'files',
    })


@require_http_methods(['POST'])
@csrf_protect
def user_filemanager_api(request, website_id=None):
    """AJAX endpoint for file manager operations."""
    user = get_current_user(request)
    if not user:
        return JsonResponse({'status': 0, 'error': 'Unauthorized'}, status=401)

    website = None
    if website_id:
        website = get_object_or_404(Website, id=website_id, owner=user)

    base = _base(user, website)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'status': 0, 'error': 'Invalid JSON.'}, status=400)

    action = data.get('action', '')

    if action == 'list':
        return fm.list_dir(
            base,
            data.get('path', ''),
            page=int(data.get('page', 1)),
            per_page=int(data.get('per_page', 100)),
            sort=data.get('sort', 'name'),
            reverse=bool(data.get('reverse', False)),
            search=data.get('search', ''),
        )

    if action == 'create_file':
        return fm.create_file(base, data.get('path', ''))

    if action == 'create_folder':
        return fm.create_folder(base, data.get('path', ''))

    if action == 'rename':
        return fm.rename(base, data.get('dir', ''), data.get('old_name', ''), data.get('new_name', ''))

    if action == 'copy':
        return fm.copy_items(base, data.get('src_dir', ''), data.get('items', []), data.get('dst_dir', ''))

    if action == 'move':
        return fm.move_items(base, data.get('src_dir', ''), data.get('items', []), data.get('dst_dir', ''))

    if action == 'trash':
        return fm.trash_items(base, data.get('dir', ''), data.get('items', []))

    if action == 'delete':
        return fm.delete_permanent(base, data.get('dir', ''), data.get('items', []))

    if action == 'list_trash':
        return fm.list_trash(base)

    if action == 'restore_trash':
        return fm.restore_trash(base, data.get('trash_names', []), data.get('original_paths', []))

    if action == 'empty_trash':
        return fm.empty_trash(base)

    if action == 'read':
        return fm.read_file(base, data.get('path', ''))

    if action == 'write':
        return fm.write_file(base, data.get('path', ''), data.get('content', ''))

    if action == 'extract':
        return fm.extract_archive(base, data.get('archive', ''), data.get('dest', ''))

    if action == 'compress':
        return fm.compress_items(base, data.get('dir', ''), data.get('items', []),
                                 data.get('name', 'archive'), data.get('format', 'zip'))

    if action == 'chmod':
        return fm.change_permissions(base, data.get('path', ''), data.get('mode', '755'),
                                     bool(data.get('recursive', False)))

    if action == 'disk_usage':
        return fm.disk_usage(base)

    if action == 'bookmarks':
        return _handle_bookmarks(request, user, website, data)

    return JsonResponse({'status': 0, 'error': 'Unknown action.'}, status=400)


def _handle_bookmarks(request, user, website, data):
    sub_action = data.get('sub_action', '')
    if sub_action == 'list':
        bookmarks = FileManagerBookmark.objects.filter(user=user)
        if website:
            bookmarks = bookmarks.filter(website=website)
        else:
            bookmarks = bookmarks.filter(website__isnull=True)
        return JsonResponse({'status': 1, 'bookmarks': [
            {'id': b.id, 'name': b.name, 'path': b.path} for b in bookmarks
        ]})
    elif sub_action == 'add':
        name = data.get('name', '').strip()
        path = data.get('path', '').strip()
        if name and path:
            bm = FileManagerBookmark.objects.create(user=user, website=website, name=name, path=path)
            return JsonResponse({'status': 1, 'bookmark': {'id': bm.id, 'name': bm.name, 'path': bm.path}})
        return JsonResponse({'status': 0, 'error': 'Name and path required.'})
    elif sub_action == 'delete':
        bm_id = data.get('id')
        FileManagerBookmark.objects.filter(id=bm_id, user=user).delete()
        return JsonResponse({'status': 1})
    return JsonResponse({'status': 0, 'error': 'Unknown bookmark action.'})


@require_http_methods(['POST'])
@csrf_protect
def user_filemanager_upload(request, website_id=None):
    """Handle file uploads."""
    user = get_current_user(request)
    if not user:
        return JsonResponse({'status': 0, 'error': 'Unauthorized'}, status=401)

    website = None
    if website_id:
        website = get_object_or_404(Website, id=website_id, owner=user)

    base = _base(user, website)
    rel_dir = request.POST.get('path', '')
    f = request.FILES.get('file')
    if not f:
        return JsonResponse({'status': 0, 'error': 'No file.'}, status=400)

    return fm.upload_file(base, rel_dir, f)


@require_http_methods(['GET'])
def user_filemanager_download(request, website_id=None):
    """Handle file downloads."""
    user = get_current_user(request)
    if not user:
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    website = None
    if website_id:
        website = get_object_or_404(Website, id=website_id, owner=user)

    base = _base(user, website)
    rel_path = request.GET.get('path', '')
    return fm.download_file(base, rel_path)