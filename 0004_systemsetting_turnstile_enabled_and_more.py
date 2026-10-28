
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('adminpanel', '0003_systemsetting_google_client_secret'),
    ]

    operations = [
        migrations.AddField(
            model_name='systemsetting',
            name='turnstile_enabled',
            field=models.BooleanField(default=False, help_text="Kirish va ro'yxatdan o'tish formalarida Cloudflare Turnstile robot himoyasini yoqish", verbose_name='Cloudflare Turnstile (CAPTCHA) Faol'),
        ),
        migrations.AddField(
            model_name='systemsetting',
            name='turnstile_secret_key',
            field=models.CharField(blank=True, default='', help_text='Cloudflare Turnstile Secret Key (masalan: 0x4AAAAAA...)', max_length=255, verbose_name='Turnstile Secret Key'),
        ),
        migrations.AddField(
            model_name='systemsetting',
            name='turnstile_site_key',
            field=models.CharField(blank=True, default='', help_text='Cloudflare Turnstile Public Site Key (masalan: 0x4AAAAAA...)', max_length=255, verbose_name='Turnstile Site Key'),
        ),
    ]
