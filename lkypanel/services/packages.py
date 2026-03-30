"""Package management service — modular plugin system."""
import json
import logging
import os
import subprocess
import time
from pathlib import Path

logger = logging.getLogger('lkypanel.packages')

# Configure file handler for packages.log
_pkg_log_handler = logging.FileHandler('/var/log/lkypanel/packages.log')
_pkg_log_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
logger.addHandler(_pkg_log_handler)

PLUGINS_FLAG_DIR = "/usr/local/lkypanel/plugins"
PLUGIN_STATUS_LOG = "/usr/local/lkypanel/plugin_install.log"
PLUGINS_SOURCE_DIR = Path(__file__).resolve().parent.parent / "plugins"

BUILTIN_PLUGINS = [
    "mariadb", "pureftpd", "redis", "postfix",
    "phpmyadmin", "restic", "fail2ban",
]


def is_plugin_installed(name: str) -> bool:
    """Return True iff the flag file exists for this plugin."""
    try:
        return os.path.isfile(os.path.join(PLUGINS_FLAG_DIR, name))
    except OSError:
        return False


def get_all_plugins() -> list[dict]:
    """
    Load all plugins from PLUGINS_SOURCE_DIR/*/meta.json.
    Returns list of dicts with keys: id, name, description, version,
    firewall_ports, state ('installed'|'not_installed').
    """
    plugins = []
    for plugin_id in BUILTIN_PLUGINS:
        meta_path = PLUGINS_SOURCE_DIR / plugin_id / "meta.json"
        try:
            data = json.loads(meta_path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        plugins.append({
            "id": plugin_id,
            "name": data.get("name", plugin_id),
            "description": data.get("description", ""),
            "version": data.get("version", ""),
            "firewall_ports": data.get("firewall_ports", []),
            "state": "installed" if is_plugin_installed(plugin_id) else "not_installed",
        })
    return plugins


PLUGIN_OP_START_FILE = "/usr/local/lkypanel/plugin_op_start"

def launch_plugin_op(plugin_id: str, operation: str) -> None:
    """
    Launch plugins/{plugin_id}/{operation}.sh as a non-blocking background subprocess.
    Clears the status log before launching.
    operation: 'install' | 'remove'
    """
    script_path = PLUGINS_SOURCE_DIR / plugin_id / f"{operation}.sh"
    logger.info('Starting plugin %s: %s', operation, plugin_id)

    # Truncate log and record start time
    try:
        open(PLUGIN_STATUS_LOG, "w").close()
        with open(PLUGIN_OP_START_FILE, "w") as f:
            f.write(str(int(time.time())))
    except OSError:
        pass

    with open(PLUGIN_STATUS_LOG, "a") as log_fh:
        subprocess.Popen(
            ["bash", str(script_path)],
            stdout=log_fh,
            stderr=log_fh,
            close_fds=True,
        )


def read_plugin_status() -> dict:
    """
    Read the last line of the status log.
    Returns: {'state': 'running'|'success'|'error', 'message': str}
    """
    try:
        text = Path(PLUGIN_STATUS_LOG).read_text()
        lines = [l for l in text.splitlines() if l.strip()]
        last = lines[-1] if lines else ""
    except OSError:
        return {"state": "running", "message": ""}

    if "[200]" in last:
        logger.info('Plugin operation completed successfully')
        return {"state": "success", "message": last}
    if "[404]" in last or "error:" in text.lower() or "unbound variable" in text.lower():
        logger.error('Plugin operation failed:\n%s', text)
        return {"state": "error", "message": text}

    # Timeout check (10 minutes)
    try:
        start_time = int(Path(PLUGIN_OP_START_FILE).read_text())
        if time.time() - start_time > 600:
            logger.error('Plugin operation timed out after 10 minutes')
            return {"state": "error", "message": "Operation timed out after 10 minutes."}
    except (OSError, ValueError):
        pass

    return {"state": "running", "message": last}
