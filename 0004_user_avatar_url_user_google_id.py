
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_userquota_auto_scroll_logs_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='avatar_url',
            field=models.URLField(blank=True, max_length=500, null=True, verbose_name='Avatar URL'),
        ),
        migrations.AddField(
            model_name='user',
            name='google_id',
            field=models.CharField(blank=True, max_length=255, null=True, unique=True, verbose_name='Google ID'),
        ),
    ]
