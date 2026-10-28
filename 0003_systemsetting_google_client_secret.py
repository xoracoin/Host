
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('adminpanel', '0002_systemsetting_google_client_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='systemsetting',
            name='google_client_secret',
            field=models.CharField(blank=True, default='', help_text='Google Cloud Console Client Secret', max_length=255, verbose_name='Google OAuth Client Secret'),
        ),
    ]
