"""
W3Panel v2 — Process Manager (Systemd-backed)
Ultra-low memory daemon manager for Node.js, Python, and custom processes.
"""
from .manager import (
    setup_app_service,
    start_app,
    stop_app,
    restart_app,
    get_app_status,
    get_app_logs,
    remove_app_service,
    get_service_name,
)

__all__ = [
    'setup_app_service',
    'start_app',
    'stop_app',
    'restart_app',
    'get_app_status',
    'get_app_logs',
    'remove_app_service',
    'get_service_name',
]
