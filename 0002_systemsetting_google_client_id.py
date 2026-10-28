
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('adminpanel', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='systemsetting',
            name='google_client_id',
            field=models.CharField(blank=True, default='', help_text='Google Cloud Console Client ID (masalan: 123456789-xxx.apps.googleusercontent.com)', max_length=255, verbose_name='Google OAuth Client ID'),
        ),
    ]
