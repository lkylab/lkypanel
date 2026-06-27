import psutil
import datetime
import subprocess
import os

def get_system_stats():
    """
    Get current system resource usage.
    """
    # CPU usage per core
    cpu_percent = psutil.cpu_percent(interval=1, percpu=True)
    cpu_count = psutil.cpu_count()
    cpu_load = psutil.getloadavg()
    
    # RAM
    mem = psutil.virtual_memory()
    memory = {
        'total': mem.total,
        'available': mem.available,
        'used': mem.used,
        'percent': mem.percent,
    }
    
    # Disk usage (root partition)
    disk = psutil.disk_usage('/')
    storage = {
        'total': disk.total,
        'used': disk.used,
        'free': disk.free,
        'percent': disk.percent,
    }
    
    # Network
    net = psutil.net_io_counters()
    network = {
        'bytes_sent': net.bytes_sent,
        'bytes_recv': net.bytes_recv,
    }
    
    return {
        'cpu': {
            'percent': cpu_percent,
            'count': cpu_count,
            'load': cpu_load,
        },
        'memory': memory,
        'storage': storage,
        'network': network,
        'timestamp': datetime.datetime.now().isoformat(),
    }

def check_services():
    """
    Check if critical services are running using systemctl.
    Returns a list of service statuses, filtered to only include
    installed plugins/core services.
    """
    from lkypanel.services.packages import is_plugin_installed
    
    # Core services (always monitored)
    core = [
        {'name': 'Admin Panel', 'service': 'lky-admin'},
        {'name': 'User Panel', 'service': 'lky-user'},
        {'name': 'OpenLiteSpeed', 'service': 'lshttpd'},
    ]
    
    # Plugin-based services
    plugins = [
        {'name': 'MariaDB', 'service': 'mariadb', 'plugin': 'mariadb'},
        {'name': 'Pure-FTPd', 'service': 'pure-ftpd', 'plugin': 'pureftpd'},
        {'name': 'Postfix', 'service': 'postfix', 'plugin': 'postfix'},
        {'name': 'Dovecot', 'service': 'dovecot', 'plugin': 'postfix'},
        {'name': 'Redis', 'service': 'redis', 'plugin': 'redis'},
    ]
    
    services = core
    for p in plugins:
        if is_plugin_installed(p['plugin']):
            services.append(p)
    
    results = []
    for svc in services:
        try:
            # Check status via systemctl
            proc = subprocess.run(['systemctl', 'is-active', svc['service']], 
                                 capture_output=True, text=True)
            status = proc.stdout.strip()
            is_active = (status == 'active')
            
            results.append({
                'name': svc['name'],
                'service': svc['service'],
                'status': status,
                'is_active': is_active
            })
        except Exception as e:
            results.append({
                'name': svc['name'],
                'service': svc['service'],
                'status': 'unknown',
                'is_active': False,
                'error': str(e)
            })
    return results

def check_backup_status():
    """
    Check if the most recent backup job failed.
    """
    from lkypanel.models import BackupJob
    from django.utils import timezone
    from datetime import timedelta
    
    alerts = []
    # Check for failures in the last 24 hours
    since = timezone.now() - timedelta(days=1)
    failed_jobs = BackupJob.objects.filter(status='failed', start_time__gte=since)
    
    for job in failed_jobs:
        # Check if we already alerted for this specific job id?
        # Notification logic in scheduler checks for unread similar target/message.
        alerts.append({
            'level': 'warning',
            'message': f"Warning: Backup job #{job.id} failed recently.",
            'target': f"Backup Job #{job.id}"
        })
    return alerts

def check_alerts():
    """
    Check system health and return a list of alerts.
    """
    from lkypanel.models import SystemSetting
    alerts = []
    
    # Load thresholds (fallback to 90 if not set)
    t_cpu = int(SystemSetting.get_val('threshold_cpu', '90'))
    t_ram = int(SystemSetting.get_val('threshold_ram', '90'))
    t_disk = int(SystemSetting.get_val('threshold_disk', '90'))
    
    # 1. Check Resource Usage
    disk = psutil.disk_usage('/')
    if disk.percent > t_disk:
        alerts.append({
            'level': 'danger',
            'message': f"Critical: Disk usage is at {disk.percent}% (Threshold: {t_disk}%)!",
            'target': 'Storage'
        })
    elif disk.percent > (t_disk - 10):
        alerts.append({
            'level': 'warning',
            'message': f"Warning: Disk usage is reaching {disk.percent}% (Threshold: {t_disk}%).",
            'target': 'Storage'
        })
        
    mem = psutil.virtual_memory()
    if mem.percent > t_ram:
        alerts.append({
            'level': 'danger',
            'message': f"Critical: Memory usage is at {mem.percent}% (Threshold: {t_ram}%)!",
            'target': 'RAM'
        })
        
    load = psutil.getloadavg()[0]
    cpu_count = psutil.cpu_count()
    # High load if avg load > threshold (as percentage of total cores)
    # E.g. if t_cpu is 90, and we have 4 cores, load > 3.6 is an alert
    cpu_usage_avg = (load / cpu_count) * 100
    if cpu_usage_avg > t_cpu:
        alerts.append({
            'level': 'danger',
            'message': f"Critical: System load is very high ({cpu_usage_avg:.1f}%) (Threshold: {t_cpu}%)!",
            'target': 'CPU'
        })
    
    # 2. Check Services
    # check_services now returns a list of results, but we need to convert to alerts if not active
    svc_results = check_services()
    for svc in svc_results:
        if not svc['is_active']:
            alerts.append({
                'level': 'danger',
                'message': f"Critical: Service {svc['name']} is {svc['status']}!",
                'target': svc['name']
            })
    
    # 3. Check Backup Status
    alerts.extend(check_backup_status())
    
    return alerts
