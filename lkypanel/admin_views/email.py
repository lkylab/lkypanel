"""Email management — admin views."""
from django.shortcuts import render, redirect
from django.contrib import messages
from lkypanel.admin_views.decorators import admin_required
from lkypanel.models import Website, MailDomain, MailAccount
from lkypanel.services.email import sync_email_configs

@admin_required
def email_dashboard(request):
    """List mail domains and accounts."""
    mail_domains = MailDomain.objects.all().prefetch_related('accounts')
    websites = Website.objects.all()
    return render(request, 'admin/email.html', {
        'active_page': 'email',
        'panel_user': request.panel_user,
        'mail_domains': mail_domains,
        'websites': websites,
        'total_accounts': MailAccount.objects.count(),
    })

@admin_required
def add_mail_domain(request):
    """Add a new mail domain linked to a website."""
    if request.method == 'POST':
        site_id = request.POST.get('site_id')
        domain_name = request.POST.get('domain')
        try:
            site = Website.objects.get(id=site_id)
            MailDomain.objects.create(website=site, domain=domain_name)
            sync_email_configs()
            messages.success(request, f"Mail domain {domain_name} added.")
        except Exception as e:
            messages.error(request, f"Error: {e}")
    return redirect('admin_email')

@admin_required
def add_mail_account(request):
    """Add a new mail account (mailbox)."""
    if request.method == 'POST':
        domain_id = request.POST.get('domain_id')
        email_user = request.POST.get('email_user')
        password = request.POST.get('password')
        try:
            from lkypanel.services.email import add_mail_account as svc_add_mail
            svc_add_mail(domain_id, email_user, password)
            messages.success(request, f"Mail account {email_user}@... created.")
        except Exception as e:
            messages.error(request, f"Error: {e}")
    return redirect('admin_email')
