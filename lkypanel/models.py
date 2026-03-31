"""
Data models for Lite Hosting Panel.

Path derivation rules (enforced in save()):
  Website.doc_root    = /home/{sanitized_domain}/public_html
  SSLCertificate.cert_path = /etc/letsencrypt/live/{sanitized_domain}/fullchain.pem
  FTPAccount.home_dir must start with website.doc_root
"""
import re

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.db import models

# ---------------------------------------------------------------------------
# Domain validation
# ---------------------------------------------------------------------------
_DOMAIN_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9\-\.]{1,251}[a-zA-Z0-9]$')


def _validate_domain(domain: str) -> str:
    """Validate domain and return it, or raise ValidationError."""
    if not domain:
        raise ValidationError('Domain must not be empty.')
    if '..' in domain:
        raise ValidationError('Domain must not contain "..".')
    if '//' in domain:
        raise ValidationError('Domain must not contain "//".')
    if '\x00' in domain:
        raise ValidationError('Domain must not contain null bytes.')
    if not _DOMAIN_RE.match(domain):
        raise ValidationError(
            f'Domain "{domain}" does not match the required format '
            r'^[a-zA-Z0-9][a-zA-Z0-9\-\.]{1,251}[a-zA-Z0-9]$'
        )
    return domain


# ---------------------------------------------------------------------------
# Package (Resource Limits)
# ---------------------------------------------------------------------------

class Package(models.Model):
    name = models.CharField(max_length=100, unique=True)
    disk_limit_mb = models.PositiveIntegerField(default=1024)
    bandwidth_limit_gb = models.PositiveIntegerField(default=10)
    websites_limit = models.PositiveIntegerField(default=1)
    databases_limit = models.PositiveIntegerField(default=1)
    ftp_limit = models.PositiveIntegerField(default=1)
    email_limit = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'lkypanel'

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class UserManager(BaseUserManager):
    def create_user(self, username, email, password=None, role='user', **extra_fields):
        if not username:
            raise ValueError('Username is required.')
        if not email:
            raise ValueError('Email is required.')
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, role=role, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault('role', 'admin')
        extra_fields.setdefault('is_active', True)
        return self.create_user(username, email, password, **extra_fields)


class User(AbstractBaseUser):
    ROLE_ADMIN = 'admin'
    ROLE_RESELLER = 'reseller'
    ROLE_USER = 'user'
    ROLE_CHOICES = [
        (ROLE_ADMIN, 'admin'),
        (ROLE_RESELLER, 'reseller'),
        (ROLE_USER, 'user')
    ]

    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_USER)
    
    # Reseller & Packages
    package = models.ForeignKey('Package', on_delete=models.SET_NULL, null=True, blank=True, related_name='users')
    parent_reseller = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='sub_users')
    
    # 2FA Security
    otp_secret = models.CharField(max_length=32, blank=True)
    is_2fa_enabled = models.BooleanField(default=False)
    
    is_active = models.BooleanField(default=True)
    failed_logins = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']

    objects = UserManager()

    class Meta:
        app_label = 'lkypanel'

    def __str__(self):
        return self.username


# ---------------------------------------------------------------------------
# Website
# ---------------------------------------------------------------------------

class Website(models.Model):
    FRAMEWORK_NONE = 'none'
    FRAMEWORK_WORDPRESS = 'wordpress'
    FRAMEWORK_LARAVEL = 'laravel'
    FRAMEWORK_NODEJS = 'nodejs'
    FRAMEWORK_STATIC = 'static'
    FRAMEWORK_CHOICES = [
        (FRAMEWORK_NONE, 'None'),
        (FRAMEWORK_WORDPRESS, 'WordPress'),
        (FRAMEWORK_LARAVEL, 'Laravel'),
        (FRAMEWORK_NODEJS, 'Node.js'),
        (FRAMEWORK_STATIC, 'Static Template'),
    ]

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='websites')
    domain = models.CharField(max_length=253, unique=True)
    doc_root = models.CharField(max_length=512)
    php_version = models.CharField(max_length=10, default='8.1')
    framework = models.CharField(max_length=20, choices=FRAMEWORK_CHOICES, default=FRAMEWORK_NONE)
    ssl_enabled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'lkypanel'

    def save(self, *args, **kwargs):
        # Always derive doc_root from the validated domain — never accept from input
        sanitized = _validate_domain(self.domain)
        self.doc_root = f'/home/{sanitized}/public_html'
        super().save(*args, **kwargs)

    def __str__(self):
        return self.domain


# ---------------------------------------------------------------------------
# FTPAccount
# ---------------------------------------------------------------------------

class FTPAccount(models.Model):
    website = models.ForeignKey(Website, on_delete=models.CASCADE, related_name='ftp_accounts')
    username = models.CharField(max_length=150, unique=True)
    password_hash = models.CharField(max_length=256)  # SHA512-crypt for Pure-FTPd
    quota_mb = models.PositiveIntegerField(default=1024)
    home_dir = models.CharField(max_length=512)
    status = models.CharField(max_length=10, default='active')

    class Meta:
        app_label = 'lkypanel'

    def save(self, *args, **kwargs):
        # home_dir must be within the owning website's doc_root
        doc_root = self.website.doc_root
        if not self.home_dir.startswith(doc_root):
            raise ValidationError(
                f'FTPAccount.home_dir must start with the website doc_root "{doc_root}".'
            )
        super().save(*args, **kwargs)

    def __str__(self):
        return self.username


# ---------------------------------------------------------------------------
# GitRepo
# ---------------------------------------------------------------------------

class GitRepo(models.Model):
    AUTH_NONE = 'none'
    AUTH_TOKEN = 'token'
    AUTH_SSH = 'ssh'
    AUTH_CHOICES = [
        (AUTH_NONE, 'none'),
        (AUTH_TOKEN, 'token'),
        (AUTH_SSH, 'ssh'),
    ]

    website = models.ForeignKey(Website, on_delete=models.CASCADE, related_name='git_repos')
    repo_url = models.CharField(max_length=2048)
    branch = models.CharField(max_length=255, default='main')
    auth_type = models.CharField(max_length=10, choices=AUTH_CHOICES, default=AUTH_NONE)
    encrypted_credentials = models.BinaryField(null=True, blank=True)  # Fernet-encrypted
    git_user = models.CharField(max_length=255, blank=True)
    git_email = models.EmailField(blank=True)

    class Meta:
        app_label = 'lkypanel'

    def __str__(self):
        return f'{self.website.domain} → {self.repo_url}'


# ---------------------------------------------------------------------------
# SSLCertificate
# ---------------------------------------------------------------------------

class SSLCertificate(models.Model):
    website = models.OneToOneField(Website, on_delete=models.CASCADE, related_name='ssl_certificate')
    cert_path = models.CharField(max_length=512)
    issued_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    auto_renew = models.BooleanField(default=True)

    class Meta:
        app_label = 'lkypanel'

    def save(self, *args, **kwargs):
        # Always derive cert_path from the validated domain — never accept from input
        sanitized = _validate_domain(self.website.domain)
        self.cert_path = f'/etc/letsencrypt/live/{sanitized}/fullchain.pem'
        super().save(*args, **kwargs)

    def __str__(self):
        return f'SSL for {self.website.domain}'


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

class Database(models.Model):
    website = models.ForeignKey(Website, on_delete=models.CASCADE, related_name='databases')
    db_name = models.CharField(max_length=64, unique=True)
    db_user = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'lkypanel'

    def __str__(self):
        return self.db_name


# ---------------------------------------------------------------------------
# APIToken
# ---------------------------------------------------------------------------

class APIToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='api_tokens')
    token_hash = models.CharField(max_length=256)  # SHA-256 of raw token
    name = models.CharField(max_length=100)
    last_used = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'lkypanel'

    def __str__(self):
        return f'{self.user.username} / {self.name}'



# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------

class BackupConfig(models.Model):
    TYPE_S3 = 's3'
    TYPE_SFTP = 'sftp'
    TYPE_LOCAL = 'local'
    TYPE_CHOICES = [(TYPE_S3, 'S3'), (TYPE_SFTP, 'SFTP'), (TYPE_LOCAL, 'Local')]

    name = models.CharField(max_length=100, unique=True)
    repo_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    destination = models.CharField(max_length=512)
    encrypted_credentials = models.BinaryField(null=True, blank=True)
    retention_days = models.PositiveIntegerField(default=7)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'lkypanel'

    def __str__(self):
        return f"{self.name} ({self.repo_type})"


class BackupJob(models.Model):
    STATUS_RUNNING = 'running'
    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_RUNNING, 'running'),
        (STATUS_SUCCESS, 'success'),
        (STATUS_FAILED, 'failed'),
    ]

    config = models.ForeignKey(BackupConfig, on_delete=models.CASCADE, related_name='jobs')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_RUNNING)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    log_output = models.TextField(blank=True)
    snapshot_id = models.CharField(max_length=64, blank=True)
    backup_size = models.BigIntegerField(default=0)

    class Meta:
        app_label = 'lkypanel'

    def __str__(self):
        return f"Job {self.id} - {self.status} ({self.start_time})"


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

class MailDomain(models.Model):
    website = models.OneToOneField(Website, on_delete=models.CASCADE, related_name='mail_domain')
    domain = models.CharField(max_length=253, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'lkypanel'

    def save(self, *args, **kwargs):
        self.domain = _validate_domain(self.domain)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.domain


class MailAccount(models.Model):
    domain = models.ForeignKey(MailDomain, on_delete=models.CASCADE, related_name='accounts')
    email_user = models.CharField(max_length=150)  # e.g. 'info' for info@domain.com
    password_hash = models.CharField(max_length=256)
    quota_mb = models.PositiveIntegerField(default=1024)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'lkypanel'
        unique_together = ('domain', 'email_user')

    def __str__(self):
        return f'{self.email_user}@{self.domain.domain}'


# ---------------------------------------------------------------------------
# AuditLog
# ---------------------------------------------------------------------------

class AuditLog(models.Model):
    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name='audit_logs')
    action = models.CharField(max_length=100)
    target = models.CharField(max_length=512)
    ip_address = models.GenericIPAddressField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'lkypanel'

    def __str__(self):
        return f'{self.timestamp} {self.action} {self.target}'


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

class Notification(models.Model):
    LEVEL_INFO = 'info'
    LEVEL_WARNING = 'warning'
    LEVEL_DANGER = 'danger'
    LEVEL_CHOICES = [
        (LEVEL_INFO, 'info'),
        (LEVEL_WARNING, 'warning'),
        (LEVEL_DANGER, 'danger'),
    ]

    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE, related_name='notifications')
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default=LEVEL_INFO)
    message = models.TextField()
    target = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'lkypanel'
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.level.upper()}] {self.message[:50]}'
# ---------------------------------------------------------------------------
# System Settings (Global Config)
# ---------------------------------------------------------------------------

class SystemSetting(models.Model):
    """Global configuration for the panel (SMTP, Alert Thresholds, etc.)."""
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField(blank=True)
    description = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'lkypanel'

    def __str__(self):
        return self.key

    @classmethod
    def get_val(cls, key, default=None):
        try:
            return cls.objects.get(key=key).value
        except cls.DoesNotExist:
            return default

    @classmethod
    def set_val(cls, key, value, description=""):
        obj, _ = cls.objects.update_or_create(
            key=key,
            defaults={'value': str(value), 'description': description}
        )
        return obj
