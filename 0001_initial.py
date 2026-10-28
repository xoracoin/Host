
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200, verbose_name='Sarlavha')),
                ('message', models.TextField(verbose_name='Xabar matni')),
                ('type', models.CharField(choices=[('info', "ℹ️ Ma'lumot (Moviy)"), ('success', '✅ Muvaffaqiyat (Yashil)'), ('warning', '⚠️ Ogohlantirish (Sariq)'), ('danger', '🚨 Muhim / Xavf (Qizil)')], default='info', max_length=20, verbose_name='Xabar turi')),
                ('target_type', models.CharField(choices=[('all', '📢 Barcha foydalanuvchilar (Broadcast)'), ('single', '👤 Alohida foydalanuvchiga (Single User)')], default='all', max_length=20, verbose_name='Yuborish qamrovi')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Yaratilgan vaqt')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='authored_notifications', to=settings.AUTH_USER_MODEL, verbose_name='Muallif (Admin)')),
                ('recipient', models.ForeignKey(blank=True, help_text="Faqat 'Alohida foydalanuvchiga' tanlanganda to'ldiriladi. 'Barchaga' bo'lsa bo'sh qoldiring.", null=True, on_delete=django.db.models.deletion.CASCADE, related_name='received_notifications', to=settings.AUTH_USER_MODEL, verbose_name='Qabul qiluvchi')),
            ],
            options={
                'verbose_name': 'Bildirishnoma',
                'verbose_name_plural': 'Bildirishnomalar',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='NotificationRead',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('read_at', models.DateTimeField(auto_now_add=True, verbose_name="O'qilgan vaqt")),
                ('notification', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reads', to='notifications.notification', verbose_name='Bildirishnoma')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notification_reads', to=settings.AUTH_USER_MODEL, verbose_name='Foydalanuvchi')),
            ],
            options={
                'verbose_name': "O'qilgan bildirishnoma",
                'verbose_name_plural': "O'qilgan bildirishnomalar",
                'ordering': ['-read_at'],
                'unique_together': {('notification', 'user')},
            },
        ),
    ]
