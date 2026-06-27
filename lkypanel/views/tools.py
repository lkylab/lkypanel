from django.http import HttpResponseForbidden, HttpResponseRedirect
from revproxy.views import ProxyView

class phpMyAdminProxyView(ProxyView):
    """
    Proxy requests to local OLS instance for phpMyAdmin.
    Enforces Panel Authentication and Port-based Roles.
    """
    upstream = 'http://127.0.0.1:8088/phpmyadmin/'

    def dispatch(self, request, *args, **kwargs):
        # 1. Check Panel Authentication
        user_id = request.session.get('user_id')
        port_role = request.session.get('port_role')
        server_port = int(request.META.get('SERVER_PORT', 0))

        if not user_id:
            # Determine where to redirect based on port
            if server_port == 2087:
                return HttpResponseRedirect('/admin/login/')
            return HttpResponseRedirect('/login/')

        # 2. Port-based role enforcement
        if server_port == 2087:
            if port_role != 'admin':
                return HttpResponseForbidden("Admin session required for port 2087.")
        elif server_port == 2083:
            # Users can reach PMA here; OLS/MySQL will handle their DB permissions.
            pass
        
        return super().dispatch(request, *args, **kwargs)
