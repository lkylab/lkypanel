import os
import shutil
import subprocess
import logging
import json
from pathlib import Path
from django.utils import timezone
from lkypanel.models import BackupConfig, BackupJob, Website
from lkypanel.utils.encryption import decrypt_data

logger = logging.getLogger(__name__)

RESTIC_BIN = shutil.which("restic") or "/usr/bin/restic"

def get_all_docroots():
    """Returns a list of all website docrooms for backup."""
    return [site.doc_root for site in Website.objects.all() if os.path.exists(site.doc_root)]

def _prepare_env(config):
    """Prepares environment variables for restic based on config."""
    env = os.environ.copy()
    creds_raw = decrypt_data(config.encrypted_credentials)
    creds = json.loads(creds_raw) if creds_raw else {}

    if config.repo_type == BackupConfig.TYPE_S3:
        env["AWS_ACCESS_KEY_ID"] = creds.get("aws_access_key")
        env["AWS_SECRET_ACCESS_KEY"] = creds.get("aws_secret_key")
        dest = config.destination if config.destination.startswith("s3:") else f"s3:{config.destination}"
        env["RESTIC_REPOSITORY"] = dest
    elif config.repo_type == BackupConfig.TYPE_SFTP:
        dest = config.destination if config.destination.startswith("sftp:") else f"sftp:{config.destination}"
        env["RESTIC_REPOSITORY"] = dest
        # For SFTP, we might need a password or SSH key handle
        env["SSH_AUTH_SOCK"] = "" # SFTP password handled via restic expect or env? 
        # Restic SFTP usually expects SSH keys. If password, it's tricky.
        # Restic supports RESTIC_PASSWORD but for the REPO, not the SFTP part.
        # We'll assume SFTP uses password if sftp_password provided
        if "sftp_password" in creds:
             pass # Will handle via sshpass or similar if needed.
    
    env["RESTIC_PASSWORD"] = creds.get("repo_password") or "lkypanel-backup-default"
    if not creds.get("repo_password"):
        logger.warning("No repo_password set for backup config %s — using default", config.name)
    return env

def init_repo(config):
    """Initializes a restic repository."""
    env = _prepare_env(config)
    try:
        subprocess.run([RESTIC_BIN, "init"], env=env, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        if b"already initialized" in e.stderr:
            return True
        logger.error(f"Restic init failed: {e.stderr.decode()}")
        raise RuntimeError(f"Restic init failed: {e.stderr.decode()}")

def run_backup(config):
    """Runs an incremental backup job."""
    # Prevent concurrent jobs for same config
    if BackupJob.objects.filter(config=config, status=BackupJob.STATUS_RUNNING).exists():
        logger.warning(f"Backup job for {config.name} already running.")
        return None

    job = BackupJob.objects.create(config=config, status=BackupJob.STATUS_RUNNING)
    env = _prepare_env(config)
    paths = get_all_docroots()
    
    if not paths:
        job.status = BackupJob.STATUS_FAILED
        job.log_output = "No docroots found to backup."
        job.end_time = timezone.now()
        job.save()
        return job

    try:
        # restic backup --json [paths]
        cmd = [RESTIC_BIN, "backup", "--json"] + paths
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        if result.returncode == 0:
            # Parse JSON output for snapshot ID and size
            for line in result.stdout.splitlines():
                try:
                    data = json.loads(line)
                    if data.get("message_type") == "summary":
                        job.snapshot_id = data.get("snapshot_id", "")
                        job.backup_size = data.get("total_bytes_processed", 0)
                except json.JSONDecodeError:
                    continue
            
            job.status = BackupJob.STATUS_SUCCESS
        else:
            job.status = BackupJob.STATUS_FAILED
            job.log_output = result.stderr
            
    except Exception as e:
        job.status = BackupJob.STATUS_FAILED
        job.log_output = str(e)
    
    job.end_time = timezone.now()
    job.save()
    
    # Run prune/retention after success
    if job.status == BackupJob.STATUS_SUCCESS:
        prune_backups(config)
        
    return job

def prune_backups(config):
    """Enforces retention policy."""
    env = _prepare_env(config)
    days = config.retention_days
    try:
        cmd = [RESTIC_BIN, "forget", "--keep-daily", str(days), "--prune"]
        subprocess.run(cmd, env=env, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Restic prune failed: {e.stderr.decode()}")

def list_snapshots(config):
    """Lists available snapshots."""
    env = _prepare_env(config)
    try:
        cmd = [RESTIC_BIN, "snapshots", "--json"]
        result = subprocess.run(cmd, env=env, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        logger.error(f"Failed to list snapshots: {e}")
        return []

def restore_snapshot(config, snapshot_id, target_dir):
    """Restores a snapshot to a target directory."""
    env = _prepare_env(config)
    try:
        cmd = [RESTIC_BIN, "restore", snapshot_id, "--target", target_dir]
        subprocess.run(cmd, env=env, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Restore failed: {e.stderr.decode()}")
        raise RuntimeError(f"Restore failed: {e.stderr.decode()}")
