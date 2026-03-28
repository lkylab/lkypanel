import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('username', models.CharField(max_length=150, unique=True)),
                ('email', models.EmailField(max_length=254, unique=True)),
                ('role', models.CharField(choices=[('admin', 'admin'), ('user', 'user')], default='user', max_length=10)),
                ('is_active', models.BooleanField(default=True)),
                ('failed_logins', models.PositiveSmallIntegerField(default=0)),
                ('locked_until', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'app_label': 'lkypanel'},
        ),
        migrations.CreateModel(
            name='Website',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(max_length=253, unique=True)),
                ('doc_root', models.CharField(max_length=512)),
                ('php_version', models.CharField(default='8.1', max_length=10)),
                ('ssl_enabled', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='websites', to=settings.AUTH_USER_MODEL)),
            ],
            options={'app_label': 'lkypanel'},
        ),
        migrations.CreateModel(
            name='FTPAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('username', models.CharField(max_length=150, unique=True)),
                ('password_hash', models.CharField(max_length=256)),
                ('quota_mb', models.PositiveIntegerField(default=1024)),
                ('home_dir', models.CharField(max_length=512)),
                ('status', models.CharField(default='active', max_length=10)),
                ('website', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ftp_accounts', to='lkypanel.website')),
            ],
            options={'app_label': 'lkypanel'},
        ),
        migrations.CreateModel(
            name='GitRepo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('repo_url', models.CharField(max_length=2048)),
                ('branch', models.CharField(default='main', max_length=255)),
                ('auth_type', models.CharField(choices=[('none', 'none'), ('token', 'token'), ('ssh', 'ssh')], default='none', max_length=10)),
                ('encrypted_credentials', models.BinaryField(blank=True, null=True)),
                ('git_user', models.CharField(blank=True, max_length=255)),
                ('git_email', models.EmailField(blank=True)),
                ('website', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='git_repos', to='lkypanel.website')),
            ],
            options={'app_label': 'lkypanel'},
        ),
        migrations.CreateModel(
            name='SSLCertificate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cert_path', models.CharField(max_length=512)),
                ('issued_at', models.DateTimeField()),
                ('expires_at', models.DateTimeField()),
                ('auto_renew', models.BooleanField(default=True)),
                ('website', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='ssl_certificate', to='lkypanel.website')),
            ],
            options={'app_label': 'lkypanel'},
        ),
        migrations.CreateModel(
            name='Database',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('db_name', models.CharField(max_length=64, unique=True)),
                ('db_user', models.CharField(max_length=64, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('website', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='databases', to='lkypanel.website')),
            ],
            options={'app_label': 'lkypanel'},
        ),
        migrations.CreateModel(
            name='APIToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token_hash', models.CharField(max_length=256)),
                ('name', models.CharField(max_length=100)),
                ('last_used', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='api_tokens', to=settings.AUTH_USER_MODEL)),
            ],
            options={'app_label': 'lkypanel'},
        ),
        migrations.CreateModel(
            name='BackupConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('repo_type', models.CharField(choices=[('s3', 'S3'), ('sftp', 'SFTP'), ('local', 'Local')], max_length=10)),
                ('destination', models.CharField(max_length=512)),
                ('encrypted_credentials', models.BinaryField(blank=True, null=True)),
                ('retention_days', models.PositiveIntegerField(default=7)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'app_label': 'lkypanel'},
        ),
        migrations.CreateModel(
            name='BackupJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('running', 'running'), ('success', 'success'), ('failed', 'failed')], default='running', max_length=10)),
                ('start_time', models.DateTimeField(auto_now_add=True)),
                ('end_time', models.DateTimeField(blank=True, null=True)),
                ('log_output', models.TextField(blank=True)),
                ('snapshot_id', models.CharField(blank=True, max_length=64)),
                ('backup_size', models.BigIntegerField(default=0)),
                ('config', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='jobs', to='lkypanel.backupconfig')),
            ],
            options={'app_label': 'lkypanel'},
        ),
        migrations.CreateModel(
            name='AuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(max_length=100)),
                ('target', models.CharField(max_length=512)),
                ('ip_address', models.GenericIPAddressField()),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='audit_logs', to=settings.AUTH_USER_MODEL)),
            ],
            options={'app_label': 'lkypanel'},
        ),
    ]
