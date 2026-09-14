"""
W3Panel v2 — Core Models
Shared across admin, user, and API apps.
"""
import secrets
import hashlib
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager


# ---------------------------------------------------------------------------
# User Manager
# ---------------------------------------------------------------------------

class UserManager(BaseUserManager):
    def create_user(self, username, email, password=None, role='user', **extra_fields):
        if not username:
            raise ValueError('Username is required')
        email = self.normalize_email(email) if email else ''
        user = self.model(username=username, email=email, role=role, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password):
        return self.create_user(username, email, password, role='admin')


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class User(AbstractBaseUser):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('reseller', 'Reseller'),
        ('user', 'User'),
    ]

    username = models.CharField(max_length=64, unique=True)
    email = models.EmailField(blank=True, default='')
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default='user')
    package = models.ForeignKey('Package', on_delete=models.SET_NULL, null=True, blank=True)
    parent_reseller = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # 2FA
    otp_secret = models.CharField(max_length=32, blank=True, default='')
    is_2fa_enabled = models.BooleanField(default=False)
    recovery_codes = models.JSONField(default=list, blank=True)

    # Brute-force protection
    failed_logins = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)

    # Shell & Terminal access
    shell_enabled = models.BooleanField(default=False)

    objects = UserManager()
    USERNAME_FIELD = 'username'

    class Meta:
        db_table = 'w3panel_user'

    def __str__(self):
        return f'{self.username} ({self.role})'

    def generate_api_token(self):
        raw = secrets.token_hex(32)
        token_hash = hashlib.sha256(raw.encode()).hexdigest()
        APIToken.objects.create(user=self, token_hash=token_hash, name='default')
        return raw


# ---------------------------------------------------------------------------
# Package (resource limits)
# ---------------------------------------------------------------------------

class Package(models.Model):
    name = models.CharField(max_length=64, unique=True)
    description = models.TextField(blank=True, default='')
    websites_limit = models.IntegerField(default=-1)  # -1 = unlimited
    databases_limit = models.IntegerField(default=-1)
    ftp_limit = models.IntegerField(default=-1)
    email_limit = models.IntegerField(default=-1)
    disk_limit_mb = models.IntegerField(default=-1)
    bandwidth_limit_gb = models.IntegerField(default=-1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'w3panel_package'

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# Website
# ---------------------------------------------------------------------------

class Website(models.Model):
    FRAMEWORK_CHOICES = [
        ('none', 'None'),
        ('wordpress', 'WordPress'),
        ('laravel', 'Laravel'),
        ('django', 'Django'),
        ('nodejs', 'Node.js'),
        ('static', 'Static'),
    ]

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='websites')
    domain = models.CharField(max_length=255, unique=True)
    doc_root = models.CharField(max_length=512, blank=True, default='')
    php_version = models.CharField(max_length=16, default='8.3')
    framework = models.CharField(max_length=32, choices=FRAMEWORK_CHOICES, default='none')
    ssl_enabled = models.BooleanField(default=False)
    proxy_real_ip = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Node.js / Daemon Process fields
    port = models.IntegerField(default=3000, blank=True, null=True)
    app_entrypoint = models.CharField(max_length=255, default='app.js', blank=True)
    app_env_vars = models.TextField(blank=True, default='')

    # Container mode (v2)
    use_container = models.BooleanField(default=False)
    container_pod_id = models.CharField(max_length=128, blank=True, default='')

    class Meta:
        db_table = 'w3panel_website'

    def __str__(self):
        return self.domain


# ---------------------------------------------------------------------------
# Release (Zero-downtime deployments & rollback)
# ---------------------------------------------------------------------------

class Release(models.Model):
    STATUS_CHOICES = [
        ('deployed', 'Deployed'),
        ('rolled_back', 'Rolled Back'),
        ('failed', 'Failed'),
    ]

    website = models.ForeignKey(Website, on_delete=models.CASCADE, related_name='releases')
    release_id = models.CharField(max_length=64)  # Timestamp e.g. 20260913_021500
    commit_or_version = models.CharField(max_length=128, blank=True, default='')
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default='deployed')
    is_current = models.BooleanField(default=False)
    notes = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'w3panel_release'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.website.domain} release {self.release_id} ({self.status})'


# ---------------------------------------------------------------------------
# LoginToken (Single Sign-On & Admin Impersonation)
# ---------------------------------------------------------------------------

class LoginToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_tokens')
    token = models.CharField(max_length=64, unique=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_tokens')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        db_table = 'w3panel_login_token'
        ordering = ['-created_at']

    def __str__(self):
        return f'LoginToken({self.user.username}, used={self.is_used})'

    @classmethod
    def create_for_user(cls, user, created_by=None, validity_seconds=120):
        from django.utils import timezone
        from datetime import timedelta
        token = secrets.token_urlsafe(32)
        expires_at = timezone.now() + timedelta(seconds=validity_seconds)
        return cls.objects.create(
            user=user,
            token=token,
            created_by=created_by,
            expires_at=expires_at,
            is_used=False
        )

    def is_valid(self):
        from django.utils import timezone
        return not self.is_used and self.expires_at > timezone.now()


# ---------------------------------------------------------------------------
# SystemSetting (key-value config)
# ---------------------------------------------------------------------------

class SystemSetting(models.Model):
    key = models.CharField(max_length=128, unique=True)
    value = models.TextField(blank=True, default='')
    description = models.TextField(blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'w3panel_system_setting'

    def __str__(self):
        return f'{self.key} = {self.value}'

    @classmethod
    def get(cls, key, default=''):
        try:
            return cls.objects.get(key=key).value
        except cls.DoesNotExist:
            return default

    @classmethod
    def set(cls, key, value, description=''):
        obj, _ = cls.objects.update_or_create(
            key=key, defaults={'value': value, 'description': description}
        )
        return obj


# ---------------------------------------------------------------------------
# APIToken
# ---------------------------------------------------------------------------

class APIToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='api_tokens')
    token_hash = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=64, default='default')
    last_used = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'w3panel_api_token'

    def __str__(self):
        return f'{self.user.username}/{self.name}'


# ---------------------------------------------------------------------------
# AuditLog
# ---------------------------------------------------------------------------

class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=64)
    target = models.CharField(max_length=255, blank=True, default='')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'w3panel_audit_log'
        ordering = ['-timestamp']

    def __str__(self):
        return f'{self.user}: {self.action} @ {self.timestamp}'


# ---------------------------------------------------------------------------
# Notification
# ---------------------------------------------------------------------------

class Notification(models.Model):
    LEVEL_CHOICES = [
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('danger', 'Danger'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    level = models.CharField(max_length=16, choices=LEVEL_CHOICES, default='info')
    message = models.TextField()
    target = models.CharField(max_length=255, blank=True, default='')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'w3panel_notification'
        ordering = ['-created_at']


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

class Database(models.Model):
    DB_TYPE_CHOICES = [
        ('mariadb', 'MariaDB / MySQL'),
        ('postgresql', 'PostgreSQL'),
    ]

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='databases')
    name = models.CharField(max_length=64)
    db_type = models.CharField(max_length=16, choices=DB_TYPE_CHOICES, default='mariadb')
    db_user = models.CharField(max_length=64, blank=True, default='')
    size_mb = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'w3panel_database'
        unique_together = ('owner', 'name')

    def __str__(self):
        return f'{self.name} ({self.db_type})'


# ---------------------------------------------------------------------------
# Mailbox
# ---------------------------------------------------------------------------

class Mailbox(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mailboxes')
    email = models.EmailField(unique=True)
    domain = models.CharField(max_length=255)
    quota_mb = models.IntegerField(default=1024)
    used_mb = models.FloatField(default=0.0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'w3panel_mailbox'

    def __str__(self):
        return self.email


# ---------------------------------------------------------------------------
# DNS Record
# ---------------------------------------------------------------------------

class DNSRecord(models.Model):
    RECORD_TYPE_CHOICES = [
        ('A', 'A'),
        ('AAAA', 'AAAA'),
        ('CNAME', 'CNAME'),
        ('MX', 'MX'),
        ('TXT', 'TXT'),
        ('NS', 'NS'),
        ('SRV', 'SRV'),
    ]

    domain = models.ForeignKey(Website, on_delete=models.CASCADE, related_name='dns_records')
    record_type = models.CharField(max_length=8, choices=RECORD_TYPE_CHOICES, default='A')
    name = models.CharField(max_length=255, default='@')
    value = models.CharField(max_length=512)
    ttl = models.IntegerField(default=3600)
    priority = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'w3panel_dns_record'

    def __str__(self):
        return f'{self.name} {self.record_type} {self.value}'


# ---------------------------------------------------------------------------
# FTP Account
# ---------------------------------------------------------------------------

class FTPAccount(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ftp_accounts')
    username = models.CharField(max_length=64, unique=True)
    directory = models.CharField(max_length=512, default='/')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'w3panel_ftp_account'

    def __str__(self):
        return self.username


# ---------------------------------------------------------------------------
# Cron Job
# ---------------------------------------------------------------------------

class CronJob(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cron_jobs')
    command = models.CharField(max_length=512)
    schedule = models.CharField(max_length=64, default='0 0 * * *')
    description = models.CharField(max_length=255, blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'w3panel_cron_job'

    def __str__(self):
        return f'{self.schedule} {self.command}'


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------

class Backup(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='backups')
    name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=512, blank=True, default='')
    size_bytes = models.BigIntegerField(default=0)
    backup_type = models.CharField(max_length=32, default='full')
    status = models.CharField(max_length=32, default='completed')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'w3panel_backup'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.status})'


# ---------------------------------------------------------------------------
# Firewall Rule
# ---------------------------------------------------------------------------

class FirewallRule(models.Model):
    PROTOCOL_CHOICES = [
        ('tcp', 'TCP'),
        ('udp', 'UDP'),
        ('both', 'Both (TCP/UDP)'),
    ]
    ACTION_CHOICES = [
        ('ALLOW', 'Allow'),
        ('DENY', 'Deny'),
    ]

    port = models.CharField(max_length=32)
    protocol = models.CharField(max_length=8, choices=PROTOCOL_CHOICES, default='tcp')
    action = models.CharField(max_length=8, choices=ACTION_CHOICES, default='ALLOW')
    source_ip = models.CharField(max_length=64, blank=True, default='0.0.0.0/0')
    comment = models.CharField(max_length=255, blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'w3panel_firewall_rule'

    def __str__(self):
        return f'{self.action} {self.protocol} {self.port} from {self.source_ip}'

