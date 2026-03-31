from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.contrib import messages

from lkypanel.models import User
from lkypanel.utils.two_factor import (
    generate_otp_secret, 
    get_totp_uri, 
    generate_qr_code_base64, 
    verify_otp_code
)

from lkypanel.admin_views.decorators import panel_login_required

@panel_login_required
@csrf_protect
@require_http_methods(['GET', 'POST'])
def two_factor_setup(request):
    """View for users to enable/disable 2FA."""
    user = request.panel_user
    
    if request.method == 'GET':
        # If not enabled, generate a temp secret for setup
        if not user.is_2fa_enabled:
            temp_secret = generate_otp_secret()
            request.session['temp_otp_secret'] = temp_secret
            uri = get_totp_uri(user.username, temp_secret)
            qr_code = generate_qr_code_base64(uri)
            return render(request, 'security/2fa_setup.html', {
                'qr_code': qr_code,
                'secret': temp_secret,
                'active_page': 'security'
            })
        
        return render(request, 'security/2fa_setup.html', {
            'is_enabled': True,
            'active_page': 'security'
        })

    # POST: Enable or Disable
    action = request.POST.get('action')
    
    if action == 'enable':
        code = request.POST.get('code', '').strip()
        temp_secret = request.session.get('temp_otp_secret')
        
        if not temp_secret:
            messages.error(request, "Session expired. Please try again.")
            return redirect('security_2fa_setup')
            
        if verify_otp_code(temp_secret, code):
            user.otp_secret = temp_secret
            user.is_2fa_enabled = True
            user.save(update_fields=['otp_secret', 'is_2fa_enabled'])
            del request.session['temp_otp_secret']
            messages.success(request, "2FA has been successfully enabled.")
        else:
            messages.error(request, "Invalid verification code. Please scan the QR code again.")
            
    elif action == 'disable':
        user.is_2fa_enabled = False
        user.otp_secret = None
        user.save(update_fields=['is_2fa_enabled', 'otp_secret'])
        messages.warning(request, "2FA has been disabled.")

    return redirect('security_2fa_setup')
