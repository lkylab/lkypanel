"""
W3Panel v2 — License Service
Online validation, caching, and feature checking.
"""
import json
import hashlib
import logging
from pathlib import Path
from datetime import timedelta

import requests
from django.utils import timezone
from django.conf import settings

from .models import License, LicenseFeature, TIER_FEATURES, TIER_LIMITS

logger = logging.getLogger('w3panel.license')

LICENSE_SERVER = 'https://license.lkylab.com/api/validate'
CACHE_DIR = Path('/etc/w3panel')
STATUS_FILE = Path('/run/w3panel/license_status')
GRACE_PERIOD_DAYS = 7


def get_server_fingerprint():
    """Generate unique server fingerprint."""
    import uuid
    import platform
    
    # Combine multiple hardware identifiers
    identifiers = [
        platform.node(),           # hostname
        str(uuid.getnode()),       # MAC address
        platform.machine(),        # CPU architecture
    ]
    
    raw = '|'.join(identifiers)
    return hashlib.sha256(raw.encode()).hexdigest()


def activate_license(license_key: str) -> dict:
    """
    Activate a license key.
    Returns: {'success': bool, 'error': str, 'license': License}
    """
    fingerprint = get_server_fingerprint()
    
    try:
        response = requests.post(
            LICENSE_SERVER,
            json={
                'license_key': license_key,
                'server_fingerprint': fingerprint,
                'panel_version': getattr(settings, 'W3PANEL_VERSION', '2.0.0'),
                'action': 'activate',
            },
            timeout=10,
        )
        data = response.json()
    except requests.RequestException as e:
        return {'success': False, 'error': f'License server unreachable: {e}'}
    except json.JSONDecodeError:
        return {'success': False, 'error': 'Invalid response from license server'}

    if not data.get('valid'):
        return {'success': False, 'error': data.get('error', 'Invalid license')}

    # Create or update license
    license_obj, _ = License.objects.update_or_create(
        license_key=license_key,
        defaults={
            'tier': data.get('tier', 'free'),
            'is_active': True,
            'server_fingerprint': fingerprint,
            'activated_at': timezone.now(),
            'expires_at': _parse_datetime(data.get('expires_at')),
            'last_validated': timezone.now(),
            'cached_features': data.get('features', []),
            'cached_limits': data.get('limits', {}),
        }
    )

    # Save to local cache
    _save_local_cache(license_obj)

    # Update SystemSetting for middleware
    _update_system_settings(license_obj)

    return {'success': True, 'license': license_obj}


def validate_license() -> dict:
    """
    Validate current license against server.
    Returns: {'valid': bool, 'error': str, 'grace_days_remaining': int}
    """
    license_obj = _get_local_license()
    if not license_obj:
        return {'valid': False, 'error': 'No license activated', 'code': 'NO_LICENSE'}

    # Check grace period
    if license_obj.expires_at and license_obj.expires_at < timezone.now():
        days_expired = (timezone.now() - license_obj.expires_at).days
        grace_remaining = GRACE_PERIOD_DAYS - days_expired
        if grace_remaining > 0:
            return {
                'valid': False,
                'error': 'License expired',
                'code': 'LICENSE_EXPIRED',
                'grace_days_remaining': grace_remaining,
            }
        else:
            return {
                'valid': False,
                'error': 'License expired and grace period ended',
                'code': 'LICENSE_EXPIRED_GRACE',
            }

    # Validate with server
    fingerprint = get_server_fingerprint()
    try:
        response = requests.post(
            LICENSE_SERVER,
            json={
                'license_key': license_obj.license_key,
                'server_fingerprint': fingerprint,
                'panel_version': getattr(settings, 'W3PANEL_VERSION', '2.0.0'),
                'action': 'validate',
            },
            timeout=10,
        )
        data = response.json()
    except (requests.RequestException, json.JSONDecodeError):
        # Server unreachable — use cached license
        return {'valid': license_obj.is_valid, 'error': '', 'cached': True}

    # Update local cache
    license_obj.last_validated = timezone.now()
    if data.get('valid'):
        license_obj.tier = data.get('tier', license_obj.tier)
        license_obj.expires_at = _parse_datetime(data.get('expires_at'))
        license_obj.cached_features = data.get('features', license_obj.cached_features)
        license_obj.cached_limits = data.get('limits', license_obj.cached_limits)
    else:
        license_obj.is_active = False
    license_obj.save()

    _save_local_cache(license_obj)
    _update_system_settings(license_obj)

    return {
        'valid': data.get('valid', False),
        'error': data.get('error', ''),
        'grace_days_remaining': 0,
    }


def check_feature(feature: str) -> bool:
    """
    Check if current license includes a feature.
    Fast check — reads from SystemSetting cache.
    """
    from ..core.models import SystemSetting

    # Free tier always available for basic features
    basic_features = ['users', 'websites', 'databases', 'ftp', 'cron', 'file_manager']
    if feature in basic_features:
        return True

    # Check cached features
    features_json = SystemSetting.get('license_features', '[]')
    try:
        features = json.loads(features_json)
    except (json.JSONDecodeError, TypeError):
        features = []

    return feature in features


def get_tier_limits(tier: str) -> dict:
    """Get resource limits for a tier."""
    return TIER_LIMITS.get(tier, TIER_LIMITS['free'])


def _get_local_license():
    """Get license from database."""
    return License.objects.filter(is_active=True).first()


def _save_local_cache(license_obj):
    """Save license status to local file for middleware."""
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    status = {
        'valid': license_obj.is_valid,
        'tier': license_obj.tier,
        'features': license_obj.features,
        'limits': license_obj.limits,
        'expires_at': license_obj.expires_at.isoformat() if license_obj.expires_at else None,
        'grace_days_remaining': 0,
    }

    if license_obj.expires_at and license_obj.expires_at < timezone.now():
        days_expired = (timezone.now() - license_obj.expires_at).days
        status['grace_days_remaining'] = max(0, GRACE_PERIOD_DAYS - days_expired)

    STATUS_FILE.write_text(json.dumps(status, indent=2))


def _update_system_settings(license_obj):
    """Update SystemSetting for middleware/feature gate access."""
    from ..core.models import SystemSetting

    SystemSetting.set('license_tier', license_obj.tier, 'Current license tier')
    SystemSetting.set('license_features', json.dumps(license_obj.features), 'Licensed features')
    SystemSetting.set('license_expires', license_obj.expires_at.isoformat() if license_obj.expires_at else '', 'License expiry')
    SystemSetting.set('websites_limit', str(license_obj.limits.get('websites', 1)), 'Websites limit')
    SystemSetting.set('databases_limit', str(license_obj.limits.get('databases', 1)), 'Databases limit')


def _parse_datetime(dt_str):
    """Parse ISO datetime string."""
    if not dt_str:
        return None
    try:
        from django.utils.dateparse import parse_datetime
        return parse_datetime(dt_str)
    except Exception:
        return None
