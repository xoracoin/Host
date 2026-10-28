
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userquota',
            name='max_cpu',
            field=models.FloatField(default=0.5, help_text='Maksimal CPU yadrolari'),
        ),
        migrations.AlterField(
            model_name='userquota',
            name='max_ram_mb',
            field=models.IntegerField(default=256, help_text='Maksimal RAM hajmi (MB)'),
        ),
    ]
