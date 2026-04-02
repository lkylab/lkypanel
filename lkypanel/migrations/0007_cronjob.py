from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('lkypanel', '0006_systemsetting'),
    ]

    operations = [
        migrations.CreateModel(
            name='Cronjob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('command', models.CharField(max_length=1024)),
                ('schedule', models.CharField(max_length=100)),
                ('description', models.CharField(blank=True, max_length=255)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('website', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cronjobs', to='lkypanel.website')),
            ],
            options={'app_label': 'lkypanel'},
        ),
    ]
