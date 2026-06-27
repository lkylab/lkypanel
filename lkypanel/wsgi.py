"""
WSGI config for Lite Hosting Panel.

Exposes the WSGI callable as a module-level variable named ``application``.
Both gunicorn processes (admin on :2087, user on :2083) use this module.
"""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lkypanel.settings')

application = get_wsgi_application()
