"""Email management — admin views."""
from django.shortcuts import render, redirect
from django.contrib import messages
from lkypanel.admin_views.decorators import admin_required
from lkypanel.models import MailDomain, MailAccount

@admin_required
def email_dashboard(request):
    """List mail domains and accounts."""
    mail_domains = MailDomain.objects.all().prefetch_related('accounts')
    return render(request, 'admin/email.html', {
        'active_page': 'email',
        'panel_user': request.panel_user,
        'mail_domains': mail_domains,
        'total_accounts': MailAccount.objects.count(),
    })
