from django.db import models
from lkypanel.models import Website


class TrashItem(models.Model):
    website = models.ForeignKey(Website, on_delete=models.CASCADE, related_name='trash_items')
    original_path = models.CharField(max_length=1000)
    trash_name = models.CharField(max_length=255)
    trashed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-trashed_at']
