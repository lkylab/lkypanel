"""
Login views — port-aware, cPanel-style.
admin_login → port 2087, user_login → port 2083
"""
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect

from lkypanel.auth import authenticate_user, AccountLocked, InvalidCredentials


def login_index(request):
    """Route root / based on port: 2087 -> admin, 2083 -> user."""
    port = int(request.META.get('SERVER_PORT', 2083))
    if port == 2087:
        return admin_login(request)
    return user_login(request)


@csrf_protect
@require_http_methods(['GET', 'POST'])
def admin_login(request):
    if request.method == 'GET':
        return render(request, 'admin_login.html', {'panel_version': '1.0.0'})

    username = request.POST.get('username', '').strip()
    password = request.POST.get('password', '')
    ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
    error = None

    try:
        user = authenticate_user(username, password, ip)
        if user is None or user.role != 'admin':
            error = 'Invalid credentials or insufficient privileges.'
        else:
            request.session.cycle_key()
            request.session['user_id'] = user.pk
            request.session['port_role'] = 'admin'
            return redirect('/admin/dashboard/')
    except AccountLocked as e:
        error = f'Account locked. Try again in {e.remaining_minutes} minute(s).'
    except InvalidCredentials:
        error = 'Invalid username or password.'

    return render(request, 'admin_login.html', {'error': error, 'panel_version': '1.0.0'})


@csrf_protect
@require_http_methods(['GET', 'POST'])
def user_login(request):
    if request.method == 'GET':
        return render(request, 'user_login.html', {'panel_version': '1.0.0'})

    username = request.POST.get('username', '').strip()
    password = request.POST.get('password', '')
    ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
    error = None

    try:
        user = authenticate_user(username, password, ip)
        if user is None or user.role != 'user':
            error = 'Invalid credentials or insufficient privileges.'
        else:
            request.session.cycle_key()
            request.session['user_id'] = user.pk
            request.session['port_role'] = 'user'
            return redirect('/user/dashboard/')
    except AccountLocked as e:
        error = f'Account locked. Try again in {e.remaining_minutes} minute(s).'
    except InvalidCredentials:
        error = 'Invalid username or password.'

    return render(request, 'user_login.html', {'error': error, 'panel_version': '1.0.0'})


def logout_view(request):
    request.session.flush()
    port = int(request.META.get('SERVER_PORT', 2083))
    return redirect('/' if port == 2087 else '/')
