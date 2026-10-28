
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_user_avatar_url_user_google_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userquota',
            name='max_disk_mb',
            field=models.FloatField(default=25.0, help_text='Maksimal disk kvotasi (MB)'),
        ),
        migrations.AlterField(
            model_name='userquota',
            name='max_ram_mb',
            field=models.IntegerField(default=128, help_text='Maksimal RAM hajmi (MB)'),
        ),
        migrations.AlterField(
            model_name='userquota',
            name='max_running_bots',
            field=models.IntegerField(default=1, help_text='Maksimal ishlayotgan botlar soni'),
        ),
    ]
