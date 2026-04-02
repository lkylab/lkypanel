"""Website management — user views."""
import json
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from lkypanel.models import Website
from lkypanel.user_views.decorators import login_required, owns_website

@login_required
@require_http_methods(['GET'])
def user_dashboard(request):
    user_id = request.session.get('user_id')
    sites = Website.objects.filter(owner_id=user_id).order_by('-created_at')
    return render(request, 'user/dashboard.html', {
        'websites': sites,
        'active_page': 'websites',
        'panel_user': request.panel_user
    })


@login_required
@owns_website
@require_http_methods(['GET'])
def site_detail(request, site_id):
    from lkypanel.models import FTPAccount, Database, GitRepo, Cronjob
    from lkypanel.services.packages import is_plugin_installed
    site = request.panel_website
    return render(request, 'user/site_detail.html', {
        'site': site,
        'ftp_count': FTPAccount.objects.filter(website=site).count(),
        'db_count': Database.objects.filter(website=site).count(),
        'git_count': GitRepo.objects.filter(website=site).count(),
        'cronjob_count': site.cronjobs.count(),
        'pureftpd_installed': is_plugin_installed('pureftpd'),
        'mariadb_installed': is_plugin_installed('mariadb'),
        'active_page': 'websites',
        'panel_user': request.panel_user,
    })


@login_required
@require_http_methods(['GET', 'POST'])
@csrf_protect
def user_profile(request):
    from django.contrib import messages
    user = request.panel_user
    error = None
    success = None
    if request.method == 'POST':
        new_email = request.POST.get('email', '').strip()
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')
        if new_email and new_email != user.email:
            from lkypanel.models import User as UserModel
            if UserModel.objects.filter(email=new_email).exclude(pk=user.pk).exists():
                error = 'Email already in use.'
            else:
                user.email = new_email
                user.save(update_fields=['email'])
                success = 'Email updated.'
        if new_password:
            if new_password != confirm_password:
                error = 'Passwords do not match.'
            elif len(new_password) < 8:
                error = 'Password must be at least 8 characters.'
            else:
                user.set_password(new_password)
                user.save(update_fields=['password'])
                success = 'Password updated. Please log in again.'
    return render(request, 'user/profile.html', {
        'panel_user': user,
        'active_page': 'profile',
        'error': error,
        'success': success,
    })
