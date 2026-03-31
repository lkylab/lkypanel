"""
Login views — port-aware, cPanel-style.
admin_login → port 2087, user_login → port 2083
"""
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect

from lkypanel.auth import authenticate_user, AccountLocked, InvalidCredentials
from lkypanel.utils.ip import get_client_ip


def login_index(request):
    """Route root / based on port: 2087 -> admin/unified, 2083 -> user."""
    port = request.get_port()
    if port == 2087:
        return admin_login(request)
    return user_login(request)


@csrf_protect
@require_http_methods(['GET', 'POST'])
def admin_login(request):
    """Admin-focused login page (Port 2087). Allows all roles but defaults to admin UI."""
    if request.method == 'GET':
        return render(request, 'admin_login.html', {'panel_version': '1.0.0'})

    username = request.POST.get('username', '').strip()
    password = request.POST.get('password', '')
    ip = get_client_ip(request)
    error = None

    try:
        user, is_2fa_required = authenticate_user(username, password, ip)
        if user is None:
            error = 'Invalid username or password.'
        elif is_2fa_required:
            request.session['pre_auth_user_id'] = user.pk
            request.session['pre_auth_device_ip'] = ip
            return redirect('/login/2fa/')
        else:
            request.session.cycle_key()
            request.session['user_id'] = user.pk
            request.session['port_role'] = user.role
            if user.role == 'admin' or user.role == 'reseller':
                return redirect('/admin/dashboard/')
            return redirect('/user/dashboard/')
    except AccountLocked as e:
        error = f'Account locked. Try again in {e.remaining_minutes} minute(s).'
    except InvalidCredentials:
        error = 'Invalid username or password.'

    return render(request, 'admin_login.html', {'error': error, 'panel_version': '1.0.0'})


@csrf_protect
@require_http_methods(['GET', 'POST'])
def user_login(request):
    """User-focused login page (Port 2083)."""
    if request.method == 'GET':
        return render(request, 'user_login.html', {'panel_version': '1.0.0'})

    username = request.POST.get('username', '').strip()
    password = request.POST.get('password', '')
    ip = get_client_ip(request)
    error = None

    try:
        user, is_2fa_required = authenticate_user(username, password, ip)
        if user is None:
            error = 'Invalid username or password.'
        elif is_2fa_required:
            request.session['pre_auth_user_id'] = user.pk
            request.session['pre_auth_device_ip'] = ip
            return redirect('/login/2fa/')
        else:
            request.session.cycle_key()
            request.session['user_id'] = user.pk
            request.session['port_role'] = user.role
            if user.role == 'admin' or user.role == 'reseller':
                return redirect('/admin/dashboard/')
            return redirect('/user/dashboard/')
    except AccountLocked as e:
        error = f'Account locked. Try again in {e.remaining_minutes} minute(s).'
    except InvalidCredentials:
        error = 'Invalid username or password.'

    return render(request, 'user_login.html', {'error': error, 'panel_version': '1.0.0'})



@csrf_protect
@require_http_methods(['GET', 'POST'])
def verify_2fa(request):
    """Verify TOTP code after primary authentication."""
    user_id = request.session.get('pre_auth_user_id')
    if not user_id:
        return redirect('/')

    from lkypanel.models import User
    from lkypanel.utils.two_factor import verify_otp_code
    from lkypanel.audit import log_action

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        request.session.flush()
        return redirect('/')

    if request.method == 'GET':
        return render(request, 'login_2fa.html')

    code = request.POST.get('code', '').strip()
    if verify_otp_code(user.otp_secret, code):
        # Success!
        request.session.cycle_key()
        request.session['user_id'] = user.pk
        request.session['port_role'] = user.role
        
        # Cleanup pre-auth
        del request.session['pre_auth_user_id']
        if 'pre_auth_device_ip' in request.session:
            ip = request.session.pop('pre_auth_device_ip')
            log_action(user, 'login_success', user.username, ip)

        if user.role == 'admin' or user.role == 'reseller':
            return redirect('/admin/dashboard/')
        return redirect('/user/dashboard/')

    return render(request, 'login_2fa.html', {'error': 'Invalid verification code.'})


def logout_view(request):
    request.session.flush()
    port = int(request.META.get('SERVER_PORT', 2083))
    return redirect('/' if port == 2087 else '/')
