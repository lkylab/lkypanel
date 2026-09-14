"""
W3Panel v2 — File Manager Models
"""
from django.db import models
from packages.core.models import User, Website


class FileManagerSettings(models.Model):
    """Per-user file manager settings"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='fm_settings')
    show_hidden = models.BooleanField(default=False)
    default_view = models.CharField(max_length=16, choices=[('grid', 'Grid'), ('list', 'List')], default='list')
    editor_theme = models.CharField(max_length=32, default='vs-dark')
    editor_font_size = models.PositiveSmallIntegerField(default=13)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'w3panel_fm_settings'

    def __str__(self):
        return f'FM Settings for {self.user.username}'


class FileManagerBookmark(models.Model):
    """User bookmarks for quick folder access"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fm_bookmarks')
    website = models.ForeignKey(Website, on_delete=models.CASCADE, null=True, blank=True, related_name='fm_bookmarks')
    name = models.CharField(max_length=128)
    path = models.CharField(max_length=512)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'w3panel_fm_bookmark'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} -> {self.path}'