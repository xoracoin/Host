
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('filemanager', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='file',
            name='content',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='file',
            name='is_binary',
            field=models.BooleanField(default=False),
        ),
    ]
