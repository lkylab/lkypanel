"""Package management — admin views."""
import json
from pathlib import Path

from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from django.contrib import messages

from lkypanel.models import Package
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
@require_http_methods(["GET", "POST"])
def list_packages(request):
    """List and Create Resource Packages, plus Plugin management."""
    if request.method == "POST":
        # Handle Creating a new Resource Package
        name = request.POST.get("name", "").strip()
        disk = request.POST.get("disk_limit_mb", 1024)
        bw = request.POST.get("bandwidth_limit_gb", 10)
        sites = request.POST.get("websites_limit", 1)
        dbs = request.POST.get("databases_limit", 1)
        ftp = request.POST.get("ftp_limit", 1)
        email = request.POST.get("email_limit", 1)

        if Package.objects.filter(name=name).exists():
            messages.error(request, f"Package '{name}' already exists.")
        else:
            Package.objects.create(
                name=name,
                disk_limit_mb=disk,
                bandwidth_limit_gb=bw,
                websites_limit=sites,
                databases_limit=dbs,
                ftp_limit=ftp,
                email_limit=email
            )
            messages.success(request, f"Package '{name}' created successfully.")
        return redirect("admin_list_packages")

    # GET: List everything
    packages = Package.objects.all().order_by("name")
    plugins = get_all_plugins()
    
    return render(request, "admin/packages.html", {
        "packages": packages,
        "plugins": plugins,
        "mariadb_installed": is_plugin_installed("mariadb"),
        "active_page": "packages",
        "panel_user": request.panel_user,
    })


@admin_required
@require_http_methods(["POST"])
def delete_package(request, package_id):
    """Delete a resource package."""
    package = get_object_or_404(Package, pk=package_id)
    if package.users.exists():
        messages.error(request, f"Cannot delete package '{package.name}' because it is assigned to users.")
    else:
        package.delete()
        messages.success(request, f"Package '{package.name}' deleted.")
    return redirect("admin_list_packages")


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
