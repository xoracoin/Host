
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_alter_userquota_max_cpu_alter_userquota_max_ram_mb'),
    ]

    operations = [
        migrations.AddField(
            model_name='userquota',
            name='auto_scroll_logs',
            field=models.BooleanField(default=True, help_text='Terminalda avtomatik pastga tushish'),
        ),
        migrations.AddField(
            model_name='userquota',
            name='default_auto_restart',
            field=models.BooleanField(default=True, help_text='Standart auto-restart holati'),
        ),
        migrations.AddField(
            model_name='userquota',
            name='log_buffer_limit',
            field=models.IntegerField(default=100, help_text='Xotirada saqlanadigan log satrlari soni'),
        ),
        migrations.AddField(
            model_name='userquota',
            name='max_restart_attempts',
            field=models.IntegerField(default=5, help_text='Maksimal qayta urinishlar soni'),
        ),
        migrations.AddField(
            model_name='userquota',
            name='python_version',
            field=models.CharField(default='3.12', help_text='Standart Python versiyasi', max_length=10),
        ),
    ]
