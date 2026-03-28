import json
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect

from lkypanel.models import BackupConfig, BackupJob
from lkypanel.admin_views.decorators import admin_required
from lkypanel.services.backup import run_backup, init_repo, list_snapshots, restore_snapshot
from lkypanel.utils.encryption import encrypt_data
from lkypanel.services.packages import is_plugin_installed

@admin_required
@require_http_methods(['GET'])
def list_backups(request):
    """Render the backup management dashboard."""
    configs = BackupConfig.objects.all().order_by('-created_at')
    jobs = BackupJob.objects.all().order_by('-start_time')[:20]

    for config in configs:
        config.snapshot_count = len(list_snapshots(config)) if config.is_active else 0

    return render(request, 'admin/backup.html', {
        'configs': configs,
        'jobs': jobs,
        'restic_installed': is_plugin_installed('restic'),
        'active_page': 'backup',
        'panel_user': request.panel_user
    })

@admin_required
@csrf_protect
@require_http_methods(['POST'])
def create_config(request):
    """Create a new backup configuration (S3/SFTP)."""
    name = request.POST.get('name')
    repo_type = request.POST.get('repo_type')
    destination = request.POST.get('destination')
    
    # Credentials as JSON
    creds = {
        'repo_password': request.POST.get('repo_password'),
    }
    
    if repo_type == BackupConfig.TYPE_S3:
        creds.update({
            'aws_access_key': request.POST.get('aws_access_key'),
            'aws_secret_key': request.POST.get('aws_secret_key'),
        })
    elif repo_type == BackupConfig.TYPE_SFTP:
        creds.update({
            'sftp_password': request.POST.get('sftp_password'),
        })

    config = BackupConfig.objects.create(
        name=name,
        repo_type=repo_type,
        destination=destination,
        retention_days=int(request.POST.get('retention_days', 7)),
        encrypted_credentials=encrypt_data(json.dumps(creds))
    )
    
    try:
        init_repo(config)
    except Exception as e:
        config.delete()
        return JsonResponse({'error': f"Failed to initialize repository: {str(e)}"}, status=500)

    return redirect('admin_list_backups')

@admin_required
@csrf_protect
@require_http_methods(['POST'])
def trigger_backup(request):
    """Manually trigger a backup job."""
    config_id = request.POST.get('config_id')
    config = BackupConfig.objects.get(id=config_id)
    
    job = run_backup(config)
    if not job:
        return JsonResponse({'error': 'A backup job is already running.'}, status=409)
        
    return JsonResponse({
        'status': job.status,
        'job_id': job.id,
        'snapshot_id': job.snapshot_id
    })

@admin_required
@csrf_protect
@require_http_methods(['POST'])
def restore_backup(request):
    """Restore from a specific snapshot."""
    config_id = request.POST.get('config_id')
    snapshot_id = request.POST.get('snapshot_id')
    target_dir = request.POST.get('target_dir', '/tmp/restored_backup')
    
    config = BackupConfig.objects.get(id=config_id)
    try:
        restore_snapshot(config, snapshot_id, target_dir)
        return JsonResponse({'success': True, 'msg': f'Restored to {target_dir}'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@admin_required
def export_websites(request):
    return JsonResponse({'status': 'stub'})

@admin_required
def export_users(request):
    return JsonResponse({'status': 'stub'})
