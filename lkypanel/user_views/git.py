"""Git repository management — user views."""
import json
import subprocess
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect

from lkypanel.models import GitRepo
from lkypanel.user_views.decorators import login_required, owns_website
from lkypanel.services.git import clone_repo, pull_repo, push_repo


@login_required
@owns_website
@require_http_methods(['GET'])
def list_repos(request, site_id):
    site = request.panel_website
    repo = site.git_repos.first()
    return render(request, 'user/site_git.html', {
        'site': site,
        'repo': repo,
        'active_page': 'websites',
        'panel_user': request.panel_user,
    })


@login_required
@owns_website
@csrf_protect
@require_http_methods(['POST'])
def link_repo(request, site_id):
    data = json.loads(request.body)
    repo_url = data.get('repo_url', '').strip()
    branch = data.get('branch', 'main').strip()
    auth_type = data.get('auth_type', 'none')
    credentials = data.get('credentials')
    git_user = data.get('git_user', '')
    git_email = data.get('git_email', '')

    try:
        clone_repo(request.panel_website, repo_url, branch, auth_type, credentials)
    except RuntimeError as e:
        return JsonResponse({'error': str(e), 'code': 'GIT_CLONE_FAILED', 'details': {}}, status=500)
    except subprocess.TimeoutExpired:
        return JsonResponse({'error': 'Git operation timed out', 'code': 'GIT_TIMEOUT', 'details': {}}, status=504)

    repo = GitRepo.objects.filter(website=request.panel_website).first()
    if repo and (git_user or git_email):
        repo.git_user = git_user
        repo.git_email = git_email
        repo.save(update_fields=['git_user', 'git_email'])

    return JsonResponse({'linked': repo_url}, status=201)


@login_required
@owns_website
@csrf_protect
@require_http_methods(['POST'])
def git_pull(request, site_id):
    repo = GitRepo.objects.filter(website=request.panel_website).first()
    if not repo:
        return JsonResponse({'error': 'No repo linked', 'code': 'NO_REPO', 'details': {}}, status=400)
    try:
        output = pull_repo(repo)
    except RuntimeError as e:
        return JsonResponse({'error': str(e), 'code': 'GIT_PULL_FAILED', 'details': {}}, status=500)
    return JsonResponse({'output': output})


@login_required
@owns_website
@csrf_protect
@require_http_methods(['POST'])
def git_push(request, site_id):
    repo = GitRepo.objects.filter(website=request.panel_website).first()
    if not repo:
        return JsonResponse({'error': 'No repo linked', 'code': 'NO_REPO', 'details': {}}, status=400)
    try:
        output = push_repo(repo)
    except RuntimeError as e:
        return JsonResponse({'error': str(e), 'code': 'GIT_PUSH_FAILED', 'details': {}}, status=500)
    return JsonResponse({'output': output})
