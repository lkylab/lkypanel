"""
W3Panel v2 — Systemd Daemon Process Manager
Lightweight, native process supervisor for Node.js, Python, and background daemons.
Zero idle memory overhead compared to PM2 (saves ~60MB RAM per tenant).
"""
import os
import shutil
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger('w3panel.process_manager')

SYSTEMD_DIR = Path('/etc/systemd/system')


def _has_sudo() -> bool:
    try:
        res = subprocess.run(['sudo', '-n', 'true'], capture_output=True, timeout=2)
        return res.returncode == 0
    except Exception:
        return False


def _write_privileged_file(target_path: Path, content: str) -> bool:
    """Write file directly or escalate with sudo -n tee."""
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content)
        return True
    except (PermissionError, OSError):
        if not _has_sudo():
            return False
        try:
            subprocess.run(['sudo', '-n', 'mkdir', '-p', str(target_path.parent)], capture_output=True, timeout=3)
            proc = subprocess.run(
                ['sudo', '-n', 'tee', str(target_path)],
                input=content,
                text=True,
                capture_output=True,
                timeout=3
            )
            return proc.returncode == 0
        except Exception as e:
            logger.error(f"Failed to write systemd unit {target_path}: {e}")
            return False


def _remove_privileged_file(target_path: Path) -> bool:
    """Remove file directly or escalate with sudo -n rm."""
    if not target_path.exists():
        return True
    try:
        target_path.unlink()
        return True
    except (PermissionError, OSError):
        if not _has_sudo():
            return False
        try:
            proc = subprocess.run(['sudo', '-n', 'rm', '-f', str(target_path)], capture_output=True, timeout=3)
            return proc.returncode == 0
        except Exception as e:
            logger.error(f"Failed to remove unit file {target_path}: {e}")
            return False


def get_service_name(domain: str) -> str:
    """Generate systemd service name for domain."""
    clean = domain.replace('.', '-').replace('_', '-').lower()
    return f"w3panel-app-{clean}"


def get_service_path(domain: str) -> Path:
    """Determine systemd unit file destination."""
    name = get_service_name(domain)
    if SYSTEMD_DIR.exists() and (os.access(str(SYSTEMD_DIR), os.W_OK) or _has_sudo()):
        return SYSTEMD_DIR / f"{name}.service"
    fallback = Path('/tmp/w3panel/systemd')
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback / f"{name}.service"


def setup_app_service(website) -> dict:
    """
    Generate and install systemd unit file for website daemon.
    Supports Node.js, Python, or custom entrypoints with memory/CPU limits.
    """
    domain = website.domain
    service_name = get_service_name(domain)
    unit_path = get_service_path(domain)

    # Determine execution user
    username = website.owner.username if website.owner else 'w3panel'
    try:
        import pwd
        pwd.getpwnam(username)
    except Exception:
        # Fallback to current process user if tenant user doesn't exist
        try:
            import getpass
            username = getpass.getuser()
        except Exception:
            username = 'nobody'

    doc_root = Path(website.doc_root) if website.doc_root else Path(f"/home/{username}/{domain}/public_html")
    port = getattr(website, 'port', 3000) or 3000
    entrypoint = getattr(website, 'app_entrypoint', 'app.js') or 'app.js'

    # Determine ExecStart command
    node_bin = shutil.which('node') or '/usr/bin/node'
    python_bin = shutil.which('python3') or '/usr/bin/python3'

    if entrypoint.endswith('.py'):
        exec_start = f"{python_bin} {entrypoint}"
    elif entrypoint.endswith('.sh'):
        exec_start = f"/bin/bash {entrypoint}"
    else:
        exec_start = f"{node_bin} {entrypoint}"

    # Process custom environment variables
    env_lines = [
        f"Environment=PORT={port}",
        "Environment=NODE_ENV=production",
    ]
    raw_env = getattr(website, 'app_env_vars', '') or ''
    for line in raw_env.splitlines():
        line = line.strip()
        if line and '=' in line and not line.startswith('#'):
            env_lines.append(f'Environment="{line}"')

    env_block = "\n".join(env_lines)

    unit_content = f"""# W3Panel Application Service for {domain}
# Zero idle memory overhead daemon unit
[Unit]
Description=W3Panel Application - {domain}
After=network.target

[Service]
Type=simple
User={username}
WorkingDirectory={doc_root}
{env_block}
ExecStart={exec_start}
Restart=always
RestartSec=3
MemoryMax=512M
CPUQuota=100%
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""

    written = _write_privileged_file(unit_path, unit_content)
    if not written:
        return {'success': False, 'error': f"Failed to write unit file {unit_path}"}

    # Reload systemd and enable service if running as root or with sudo
    if _has_sudo():
        try:
            subprocess.run(['sudo', '-n', 'systemctl', 'daemon-reload'], capture_output=True, timeout=5)
            subprocess.run(['sudo', '-n', 'systemctl', 'enable', service_name], capture_output=True, timeout=5)
        except Exception as e:
            logger.warning(f"Could not reload systemd or enable {service_name}: {e}")

    return {
        'success': True,
        'service_name': service_name,
        'unit_path': str(unit_path),
        'port': port,
        'exec_start': exec_start,
    }


def start_app(website) -> dict:
    """Start application daemon."""
    service_name = get_service_name(website.domain)
    setup_app_service(website)
    if _has_sudo():
        try:
            res = subprocess.run(['sudo', '-n', 'systemctl', 'start', service_name], capture_output=True, text=True, timeout=5)
            return {'success': res.returncode == 0, 'output': res.stdout or res.stderr}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    return {'success': True, 'simulated': True}


def stop_app(website) -> dict:
    """Stop application daemon."""
    service_name = get_service_name(website.domain)
    if _has_sudo():
        try:
            res = subprocess.run(['sudo', '-n', 'systemctl', 'stop', service_name], capture_output=True, text=True, timeout=5)
            return {'success': res.returncode == 0, 'output': res.stdout or res.stderr}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    return {'success': True, 'simulated': True}


def restart_app(website) -> dict:
    """Restart application daemon."""
    service_name = get_service_name(website.domain)
    setup_app_service(website)
    if _has_sudo():
        try:
            res = subprocess.run(['sudo', '-n', 'systemctl', 'restart', service_name], capture_output=True, text=True, timeout=5)
            return {'success': res.returncode == 0, 'output': res.stdout or res.stderr}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    return {'success': True, 'simulated': True}


def get_app_status(website) -> dict:
    """Get real-time daemon status (active, inactive, failed, etc.)."""
    service_name = get_service_name(website.domain)
    try:
        res = subprocess.run(['systemctl', 'is-active', service_name], capture_output=True, text=True, timeout=3)
        status_text = res.stdout.strip()
        is_running = (status_text == 'active')
        
        pid = None
        if is_running:
            show_res = subprocess.run(
                ['systemctl', 'show', service_name, '--property=MainPID'],
                capture_output=True,
                text=True,
                timeout=3
            )
            for line in show_res.stdout.splitlines():
                if line.startswith('MainPID='):
                    pid = line.split('=')[1].strip()
                    break

        return {
            'service_name': service_name,
            'status': status_text or 'unknown',
            'is_running': is_running,
            'pid': pid if pid and pid != '0' else None,
            'port': getattr(website, 'port', 3000),
            'entrypoint': getattr(website, 'app_entrypoint', 'app.js'),
        }
    except Exception as e:
        return {
            'service_name': service_name,
            'status': 'unknown',
            'is_running': False,
            'error': str(e),
            'port': getattr(website, 'port', 3000),
            'entrypoint': getattr(website, 'app_entrypoint', 'app.js'),
        }


def get_app_logs(website, lines: int = 50) -> str:
    """Retrieve recent journald log entries for application daemon."""
    service_name = get_service_name(website.domain)
    try:
        cmd = ['journalctl', '-u', service_name, '-n', str(lines), '--no-pager']
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
        return "No application log entries recorded yet."
    except Exception as e:
        return f"Could not retrieve application logs: {e}"


def remove_app_service(website) -> dict:
    """Stop, disable, and delete application service."""
    service_name = get_service_name(website.domain)
    unit_path = get_service_path(website.domain)
    if _has_sudo():
        try:
            subprocess.run(['sudo', '-n', 'systemctl', 'stop', service_name], capture_output=True, timeout=5)
            subprocess.run(['sudo', '-n', 'systemctl', 'disable', service_name], capture_output=True, timeout=5)
        except Exception:
            pass

    _remove_privileged_file(unit_path)

    if _has_sudo():
        try:
            subprocess.run(['sudo', '-n', 'systemctl', 'daemon-reload'], capture_output=True, timeout=5)
        except Exception:
            pass

    return {'success': True, 'service_name': service_name}
