
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('botengine', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='botprocess',
            name='auto_restart',
            field=models.BooleanField(default=True, help_text='Xatolik yuz berganda avtomatik qayta ishga tushirish'),
        ),
        migrations.AddField(
            model_name='botprocess',
            name='env_vars',
            field=models.JSONField(blank=True, default=dict, help_text="Atrof-muhit o'zgaruvchilari (.env / Secrets)"),
        ),
    ]
