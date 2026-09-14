"""
W3Panel v2 — License Models
Stores license keys, tiers, and feature access.
"""
from django.db import models


# ---------------------------------------------------------------------------
# License Tiers
# ---------------------------------------------------------------------------

TIER_CHOICES = [
    ('free', 'Free'),
    ('solo', 'Solo'),
    ('admin', 'Admin'),
    ('pro', 'Pro'),
    ('enterprise', 'Enterprise'),
]

# Feature matrix: which features are available in each tier
TIER_FEATURES = {
    'free': [
        'users', 'websites', 'databases', 'ftp', 'cron', 'file_manager',
    ],
    'solo': [
        'users', 'websites', 'databases', 'ftp', 'cron', 'file_manager',
        'email', 'ssl', 'backups',
    ],
    'admin': [
        'users', 'websites', 'databases', 'ftp', 'cron', 'file_manager',
        'email', 'ssl', 'backups', 'wizards', 'containers', 'firewall', 'api',
    ],
    'pro': [
        'users', 'websites', 'databases', 'ftp', 'cron', 'file_manager',
        'email', 'ssl', 'backups', 'wizards', 'containers', 'firewall', 'api',
        'monitoring', 'white_label',
    ],
    'enterprise': [
        'users', 'websites', 'databases', 'ftp', 'cron', 'file_manager',
        'email', 'ssl', 'backups', 'wizards', 'containers', 'firewall', 'api',
        'monitoring', 'white_label', 'custom_branding', 'priority_support', 'sla',
    ],
}

# Default limits per tier (-1 = unlimited)
TIER_LIMITS = {
    'free': {'websites': 1, 'databases': 1, 'email': 0, 'ftp': 1, 'disk_mb': 1024},
    'solo': {'websites': 5, 'databases': 5, 'email': 25, 'ftp': 5, 'disk_mb': 10240},
    'admin': {'websites': 25, 'databases': 25, 'email': -1, 'ftp': 25, 'disk_mb': 51200},
    'pro': {'websites': 100, 'databases': 100, 'email': -1, 'ftp': 100, 'disk_mb': 204800},
    'enterprise': {'websites': -1, 'databases': -1, 'email': -1, 'ftp': -1, 'disk_mb': -1},
}


# ---------------------------------------------------------------------------
# License
# ---------------------------------------------------------------------------

class License(models.Model):
    license_key = models.CharField(max_length=32, unique=True, db_index=True)
    tier = models.CharField(max_length=16, choices=TIER_CHOICES, default='free')
    is_active = models.BooleanField(default=False)
    
    # Validation
    server_fingerprint = models.CharField(max_length=128, blank=True, default='')
    activated_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_validated = models.DateTimeField(null=True, blank=True)
    
    # Cached from license server
    cached_features = models.JSONField(default=list, blank=True)
    cached_limits = models.JSONField(default=dict, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'w3panel_license'

    def __str__(self):
        return f'{self.license_key} ({self.tier})'

    @property
    def is_valid(self):
        """Check if license is currently valid."""
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        return True

    @property
    def features(self):
        """Get features for current tier."""
        return TIER_FEATURES.get(self.tier, [])

    @property
    def limits(self):
        """Get limits for current tier."""
        return TIER_LIMITS.get(self.tier, TIER_LIMITS['free'])

    def has_feature(self, feature):
        """Check if license includes a specific feature."""
        return feature in self.features


# ---------------------------------------------------------------------------
# License Feature (for custom overrides)
# ---------------------------------------------------------------------------

class LicenseFeature(models.Model):
    license = models.ForeignKey(License, on_delete=models.CASCADE, related_name='features')
    feature = models.CharField(max_length=64)
    enabled = models.BooleanField(default=True)

    class Meta:
        db_table = 'w3panel_license_feature'
        unique_together = ['license', 'feature']

    def __str__(self):
        return f'{self.license.license_key}/{self.feature} = {self.enabled}'


# ---------------------------------------------------------------------------
# Import timezone (needed for is_valid property)
# ---------------------------------------------------------------------------

from django.utils import timezone
