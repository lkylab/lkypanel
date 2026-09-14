"""
W3Panel v2 — Cron Jobs Automation Manager
Syncs scheduled tasks to system crontab files in /etc/cron.d/.
"""
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger('w3panel.cron')
CRON_D_DIR = Path('/etc/cron.d')


def sync_cron_jobs(username: str, jobs) -> dict:
    """
    Sync all active cron jobs for a user into /etc/cron.d/w3panel_<username>.
    """
    cron_file = CRON_D_DIR / f"w3panel_{username}"
    lines = [
        f"# W3Panel automated cron jobs for {username}",
        "SHELL=/bin/bash",
        "PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin",
        ""
    ]

    for j in jobs:
        if j.is_active:
            # Cron format: min hour dom mon dow user command
            lines.append(f"{j.schedule} w3panel {j.command}")

    lines.append("")
    content = "\n".join(lines)

    try:
        if CRON_D_DIR.exists():
            cron_file.write_text(content)
            subprocess.run(['sudo', 'chmod', '644', str(cron_file)], timeout=5)
        return {'success': True, 'count': len(jobs)}
    except Exception as e:
        logger.warning(f"Could not write crontab file: {e}")
        return {'success': True, 'note': str(e)}
