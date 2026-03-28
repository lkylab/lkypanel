"""Package management — admin views."""
import json
from pathlib import Path

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from lkypanel.admin_views.decorators import admin_required
from lkypanel.services.packages import (
    BUILTIN_PLUGINS,
    PLUGINS_SOURCE_DIR,
    get_all_plugins,
    is_plugin_installed,
    launch_plugin_op,
    read_plugin_status,
)


@admin_required
@require_http_methods(["GET"])
def list_packages(request):
    """Render the packages management page."""
    plugins = get_all_plugins()
    return render(request, "admin/packages.html", {
        "plugins": plugins,
        "mariadb_installed": is_plugin_installed("mariadb"),
        "active_page": "packages",
        "panel_user": request.panel_user,
    })


@admin_required
@csrf_protect
@require_http_methods(["POST"])
def trigger_plugin(request):
    """Launch background install/remove for a plugin."""
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    plugin_id = data.get("plugin_id", "")
    operation = data.get("operation", "")

    if plugin_id not in BUILTIN_PLUGINS:
        return JsonResponse({"error": f"Unknown plugin: {plugin_id}"}, status=400)

    if operation not in ("install", "remove"):
        return JsonResponse({"error": "Invalid operation"}, status=400)

    script_path = PLUGINS_SOURCE_DIR / plugin_id / f"{operation}.sh"
    if not script_path.exists():
        return JsonResponse({"error": "Plugin script not found"}, status=500)

    # Concurrent operation detection: if log is non-empty and last line has no terminal marker
    status = read_plugin_status()
    if status["state"] == "running" and status["message"]:
        return JsonResponse({"error": "Operation already in progress"}, status=400)

    launch_plugin_op(plugin_id, operation)
    return JsonResponse({"status": "started"})


@admin_required
@require_http_methods(["GET"])
def poll_status(request):
    """Return current plugin operation state from the status log."""
    status = read_plugin_status()
    return JsonResponse(status)
