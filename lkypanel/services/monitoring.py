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
    Check if critical services are running.
    """
    services = [
        {'name': 'OpenLiteSpeed', 'process': 'lsws'},
        {'name': 'MariaDB', 'process': 'mariadbd'},
        {'name': 'Pure-FTPd', 'process': 'pure-ftpd'},
    ]
    
    alerts = []
    for svc in services:
        is_running = False
        # Check by process name using psutil
        for proc in psutil.process_iter(['name']):
            if svc['process'] in proc.info['name'].lower():
                is_running = True
                break
        
        if not is_running:
            alerts.append({
                'level': 'danger',
                'message': f"Critical: Service {svc['name']} is NOT running!",
                'target': svc['name']
            })
    return alerts

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
    alerts = []
    
    # 1. Check Resource Usage
    disk = psutil.disk_usage('/')
    if disk.percent > 90:
        alerts.append({
            'level': 'danger',
            'message': f"Critical: Disk usage is at {disk.percent}%!",
            'target': 'Storage'
        })
    elif disk.percent > 80:
        alerts.append({
            'level': 'warning',
            'message': f"Warning: Disk usage is reaching {disk.percent}%.",
            'target': 'Storage'
        })
        
    mem = psutil.virtual_memory()
    if mem.percent > 90:
        alerts.append({
            'level': 'danger',
            'message': f"Critical: Memory usage is at {mem.percent}%!",
            'target': 'RAM'
        })
        
    load = psutil.getloadavg()[0]
    cpu_count = psutil.cpu_count()
    if load > cpu_count * 2:
        alerts.append({
            'level': 'danger',
            'message': f"Critical: System load is very high ({load})!",
            'target': 'CPU'
        })
    
    # 2. Check Services
    alerts.extend(check_services())
    
    # 3. Check Backup Status
    alerts.extend(check_backup_status())
    
    return alerts
