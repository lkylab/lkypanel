"""File manager and config editor views for user sites."""
import json
import os
import mimetypes
from pathlib import Path

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect

from lkypanel.user_views.decorators import login_required, owns_website

# Config files editable per site
EDITABLE_CONFIGS = [
    '.htaccess',
    'php.ini',
    '.user.ini',
    'robots.txt',
    'wp-config.php',
    '.env',
]

TEXT_EXTENSIONS = {
    '.php', '.html', '.htm', '.css', '.js', '.json', '.xml', '.txt',
    '.md', '.ini', '.conf', '.htaccess', '.env', '.sh', '.py', '.sql',
    '.yaml', '.yml', '.log', '.csv',
}


def _safe_path(doc_root: str, rel_path: str) -> Path | None:
    """Resolve rel_path inside doc_root, return None if path escapes."""
    base = Path(doc_root).resolve()
    target = (base / rel_path.lstrip('/')).resolve()
    if base in target.parents or target == base:
        return target
    return None


@login_required
@owns_website
@require_http_methods(['GET'])
def list_files(request, site_id):
    """List files/dirs in a directory within the site doc_root."""
    rel = request.GET.get('path', '/')
    doc_root = request.panel_website.doc_root
    target = _safe_path(doc_root, rel)
    if not target or not target.is_dir():
        return JsonResponse({'error': 'Invalid path'}, status=400)

    entries = []
    try:
        for item in sorted(target.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
            entries.append({
                'name': item.name,
                'type': 'file' if item.is_file() else 'dir',
                'size': item.stat().st_size if item.is_file() else None,
                'modified': int(item.stat().st_mtime),
                'editable': item.suffix.lower() in TEXT_EXTENSIONS or item.name in EDITABLE_CONFIGS,
            })
    except PermissionError:
        return JsonResponse({'error': 'Permission denied'}, status=403)

    parent = str(Path(rel).parent) if rel != '/' else None
    return JsonResponse({'path': rel, 'parent': parent, 'entries': entries})


@login_required
@owns_website
@require_http_methods(['GET'])
def read_file(request, site_id):
    rel = request.GET.get('path', '')
    doc_root = request.panel_website.doc_root
    target = _safe_path(doc_root, rel)
    if not target or not target.is_file():
        return JsonResponse({'error': 'File not found'}, status=404)
    if target.stat().st_size > 512 * 1024:  # 512KB limit
        return JsonResponse({'error': 'File too large to edit (>512KB)'}, status=400)
    if target.suffix.lower() not in TEXT_EXTENSIONS and target.name not in EDITABLE_CONFIGS:
        return JsonResponse({'error': 'File type not editable'}, status=400)
    try:
        content = target.read_text(errors='replace')
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'path': rel, 'content': content})


@login_required
@owns_website
@csrf_protect
@require_http_methods(['POST'])
def write_file(request, site_id):
    data = json.loads(request.body)
    rel = data.get('path', '')
    content = data.get('content', '')
    doc_root = request.panel_website.doc_root
    target = _safe_path(doc_root, rel)
    if not target or not target.is_file():
        return JsonResponse({'error': 'File not found'}, status=404)
    if target.suffix.lower() not in TEXT_EXTENSIONS and target.name not in EDITABLE_CONFIGS:
        return JsonResponse({'error': 'File type not editable'}, status=400)
    try:
        target.write_text(content)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'saved': rel})


@login_required
@owns_website
@csrf_protect
@require_http_methods(['POST'])
def delete_file(request, site_id):
    data = json.loads(request.body)
    rel = data.get('path', '')
    doc_root = request.panel_website.doc_root
    target = _safe_path(doc_root, rel)
    if not target or not target.exists():
        return JsonResponse({'error': 'Not found'}, status=404)
    # Prevent deleting doc_root itself
    if target == Path(doc_root).resolve():
        return JsonResponse({'error': 'Cannot delete site root'}, status=400)
    try:
        if target.is_dir():
            import shutil
            shutil.rmtree(target)
        else:
            target.unlink()
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'deleted': rel})


@login_required
@owns_website
@csrf_protect
@require_http_methods(['POST'])
def create_item(request, site_id):
    """Create a new file or directory."""
    data = json.loads(request.body)
    rel = data.get('path', '')
    kind = data.get('type', 'file')  # 'file' or 'dir'
    doc_root = request.panel_website.doc_root
    target = _safe_path(doc_root, rel)
    if not target:
        return JsonResponse({'error': 'Invalid path'}, status=400)
    if target.exists():
        return JsonResponse({'error': 'Already exists'}, status=400)
    try:
        if kind == 'dir':
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.touch()
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'created': rel})


@login_required
@owns_website
@require_http_methods(['GET'])
def site_logs(request, site_id):
    """Return site access or error log content."""
    from lkypanel.services.logs import get_log_content
    log_type = request.GET.get('type', 'access')  # 'access' or 'error'
    lines = int(request.GET.get('lines', 100))
    domain = request.panel_website.domain
    log_id = f'site_{log_type}'
    content = get_log_content(log_id, lines, domain=domain)
    return JsonResponse({'content': content})


@login_required
@owns_website
@require_http_methods(['GET'])
def editable_configs(request, site_id):
    """List editable config files that exist in the site root."""
    doc_root = Path(request.panel_website.doc_root)
    configs = []
    for name in EDITABLE_CONFIGS:
        p = doc_root / name
        if p.exists():
            configs.append({'name': name, 'path': f'/{name}'})
    return JsonResponse({'configs': configs})
