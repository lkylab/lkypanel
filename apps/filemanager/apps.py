"""
W3Panel v2 — File Manager App
"""
from django.apps import AppConfig


class FileManagerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.filemanager'
    verbose_name = 'File Manager'