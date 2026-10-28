
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('adminpanel', '0004_systemsetting_turnstile_enabled_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='systemsetting',
            name='email_verification_required',
            field=models.BooleanField(default=True, help_text='Yoqilsa, yangi foydalanuvchilar pochtadagi havolani faollashtirmaguncha akkaunt ochilmaydi.', verbose_name='Email tasdiqlash majburiy'),
        ),
        migrations.AlterField(
            model_name='adminauditlog',
            name='action',
            field=models.CharField(choices=[('LOGIN', 'Admin Tizimga Kirdi'), ('USER_QUOTA_UPDATE', "Kvota O'zgartirildi"), ('USER_BAN', 'Foydalanuvchi Bloklandi'), ('USER_UNBAN', 'Foydalanuvchi Blokdan Chiqarildi'), ('USER_PASSWORD_RESET', 'Parol Yangilandi'), ('BOT_KILL', "Bot Majburiy To'xtatildi"), ('SETTINGS_UPDATE', "Tizim Sozlamalari O'zgartirildi"), ('BROADCAST_SENT', "Tizim E'loni Yuborildi"), ('SECURITY_ALERT', '🚨 Xavfsizlik Qoidabuzarligi')], max_length=50, verbose_name='Harakat turi'),
        ),
    ]
