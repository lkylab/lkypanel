"""File manager views — integrated with LkyPanel auth."""
import json
import os
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.shortcuts import render
from django.http import JsonResponse

from lkypanel.user_views.decorators import login_required, owns_website
from lkypanel.audit import log_action
from . import filemanager as fm


def _base(site) -> str:
    return f'/home/{site.domain}'


def _ip(request) -> str:
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


# ── Page ──────────────────────────────────────────────────────────────────

@login_required
@owns_website
@require_http_methods(['GET'])
def index(request, site_id):
    site = request.panel_website
    return render(request, 'filemanager/index.html', {
        'site': site,
        'panel_user': request.panel_user,
        'active_page': 'websites',
    })


# ── AJAX endpoints ────────────────────────────────────────────────────────

@login_required
@owns_website
@require_http_methods(['POST'])
@csrf_protect
def api(request, site_id):
    site = request.panel_website
    base = _base(site)
    user = request.panel_user

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
        log_action(user, 'fm_create_file', data.get('path', ''), _ip(request))
        return fm.create_file(base, data.get('path', ''))

    if action == 'create_folder':
        log_action(user, 'fm_create_folder', data.get('path', ''), _ip(request))
        return fm.create_folder(base, data.get('path', ''))

    if action == 'rename':
        log_action(user, 'fm_rename', data.get('old_name', ''), _ip(request))
        return fm.rename(base, data.get('dir', ''), data.get('old_name', ''), data.get('new_name', ''))

    if action == 'copy':
        log_action(user, 'fm_copy', str(data.get('items', '')), _ip(request))
        return fm.copy_items(base, data.get('src_dir', ''), data.get('items', []), data.get('dst_dir', ''))

    if action == 'move':
        log_action(user, 'fm_move', str(data.get('items', '')), _ip(request))
        return fm.move_items(base, data.get('src_dir', ''), data.get('items', []), data.get('dst_dir', ''))

    if action == 'trash':
        log_action(user, 'fm_trash', str(data.get('items', '')), _ip(request))
        return fm.trash_items(base, data.get('dir', ''), data.get('items', []), base)

    if action == 'delete':
        log_action(user, 'fm_delete_permanent', str(data.get('items', '')), _ip(request))
        return fm.delete_permanent(base, data.get('dir', ''), data.get('items', []))

    if action == 'list_trash':
        return fm.list_trash(base)

    if action == 'restore_trash':
        return fm.restore_trash(base, data.get('trash_names', []), data.get('original_paths', []))

    if action == 'empty_trash':
        log_action(user, 'fm_empty_trash', site.domain, _ip(request))
        return fm.empty_trash(base)

    if action == 'read':
        return fm.read_file(base, data.get('path', ''))

    if action == 'write':
        log_action(user, 'fm_write', data.get('path', ''), _ip(request))
        return fm.write_file(base, data.get('path', ''), data.get('content', ''))

    if action == 'extract':
        log_action(user, 'fm_extract', data.get('archive', ''), _ip(request))
        return fm.extract_archive(base, data.get('archive', ''), data.get('dest', ''))

    if action == 'compress':
        log_action(user, 'fm_compress', str(data.get('items', '')), _ip(request))
        return fm.compress_items(base, data.get('dir', ''), data.get('items', []),
                                 data.get('name', 'archive'), data.get('format', 'zip'))

    if action == 'chmod':
        log_action(user, 'fm_chmod', data.get('path', ''), _ip(request))
        return fm.change_permissions(base, data.get('path', ''), data.get('mode', '755'),
                                     bool(data.get('recursive', False)))

    if action == 'disk_usage':
        return fm.disk_usage(base)

    return JsonResponse({'status': 0, 'error': 'Unknown action.'}, status=400)


@login_required
@owns_website
@require_http_methods(['POST'])
@csrf_protect
def upload(request, site_id):
    site = request.panel_website
    base = _base(site)
    rel_dir = request.POST.get('path', '')
    f = request.FILES.get('file')
    if not f:
        return JsonResponse({'status': 0, 'error': 'No file.'}, status=400)
    log_action(request.panel_user, 'fm_upload', f.name, _ip(request))
    return fm.upload_file(base, rel_dir, f)


@login_required
@owns_website
@require_http_methods(['GET'])
def download(request, site_id):
    site = request.panel_website
    base = _base(site)
    rel_path = request.GET.get('path', '')
    log_action(request.panel_user, 'fm_download', rel_path, _ip(request))
    return fm.download_file(base, rel_path)
