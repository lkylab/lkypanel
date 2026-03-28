import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('lkypanel', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='MailDomain',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(max_length=253, unique=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('website', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='mail_domain', to='lkypanel.website')),
            ],
            options={'app_label': 'lkypanel'},
        ),
        migrations.CreateModel(
            name='MailAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email_user', models.CharField(max_length=150)),
                ('password_hash', models.CharField(max_length=256)),
                ('quota_mb', models.PositiveIntegerField(default=1024)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('domain', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='accounts', to='lkypanel.maildomain')),
            ],
            options={'app_label': 'lkypanel', 'unique_together': {('domain', 'email_user')}},
        ),
    ]
