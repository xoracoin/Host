from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.filemanager.models import Folder, File

User = get_user_model()

SAMPLE_BOT_CODE = """# Py Hosting - Python Telegram Bot Misol
import time
import sys

print("[Py Hosting] Bot ishga tushirilmoqda...")
print("[Py Hosting] Python versiyasi:", sys.version)

def run():
    count = 1
    while True:
        print(f"[Py Hosting Log] Bot 24/7 rejimida ishlamoqda. Yurak urishi #{count}")
        time.sleep(5)
        count += 1

if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("[Py Hosting] Bot to'xtatildi.")
"""

ECHO_BOT_CODE = """# Py Hosting - Telegram Echo Bot Shablon
# Diqqat: Haqiqiy bot ishlashi uchun @BotFather orqali TOKEN oling
# import telebot
# bot = telebot.TeleBot("SIZNING_BOT_TOKENINGIZ")

import time

print("[Py Hosting] Telegram Echo Bot tayyor.")
print("[Py Hosting] @BotFather orqali olingan tokenni joylashtiring.")

for i in range(1, 20):
    print(f"[Telegram Polling] Yangi xabarlar tekshirilmoqda... #{i}")
    time.sleep(3)
"""

class Command(BaseCommand):
    help = "Demo foydalanuvchi va namunaviy bot fayllarini yaratadi"

    def handle(self, *args, **options):
        user, created = User.objects.get_or_create(
            username='demo',
            defaults={'email': 'demo@pyhosting.uz'}
        )
        user.set_password('demo12345')
        user.save()

        quota = user.quota
        quota.max_disk_mb = 50.0
        quota.max_running_bots = 2
        quota.max_ram_mb = 256
        quota.max_cpu = 0.5
        quota.save()

        bot_file, _ = File.objects.get_or_create(
            owner=user,
            folder=None,
            name='bot.py',
            defaults={'extension': '.py'}
        )
        bot_file.write_content(SAMPLE_BOT_CODE)

        echo_file, _ = File.objects.get_or_create(
            owner=user,
            folder=None,
            name='echo_bot.py',
            defaults={'extension': '.py'}
        )
        echo_file.write_content(ECHO_BOT_CODE)

        req_file, _ = File.objects.get_or_create(
            owner=user,
            folder=None,
            name='requirements.txt',
            defaults={'extension': '.txt'}
        )
        req_file.write_content("pyTelegramBotAPI==4.26.0\nrequests==2.32.3\n")

        folder, _ = Folder.objects.get_or_create(owner=user, name='loyihalar', parent=None)
        subfile, _ = File.objects.get_or_create(
            owner=user,
            folder=folder,
            name='config.py',
            defaults={'extension': '.py'}
        )
        subfile.write_content("# Bot sozlamalari\nDEBUG = True\nTIMEOUT = 60\n")

        quota.recalculate_usage()

        self.stdout.write(self.style.SUCCESS("[OK] Demo foydalanuvchi yaratildi: username: 'demo', parol: 'demo12345'"))
        self.stdout.write(self.style.SUCCESS(f"[OK] Namuna fayllar yuklandi. Disk sarfi: {quota.used_disk_mb} MB / 50 MB"))
