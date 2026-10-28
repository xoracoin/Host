import os
import sys
import re
import json
import logging
import subprocess
from pathlib import Path
from django.conf import settings

logger = logging.getLogger(__name__)

POPULAR_PACKAGES = [
    {
        'name': 'aiogram',
        'desc': "Asinxron zamonaviy Telegram bot freymvorki (v3)",
        'category': 'Telegram',
        'install_cmd': 'aiogram'
    },
    {
        'name': 'pyTelegramBotAPI',
        'desc': "Sodda va qulay TeleBot kutubxonasi",
        'category': 'Telegram',
        'install_cmd': 'pyTelegramBotAPI'
    },
    {
        'name': 'python-telegram-bot',
        'desc': "Keng imkoniyatli klassik Telegram Bot SDK",
        'category': 'Telegram',
        'install_cmd': 'python-telegram-bot'
    },
    {
        'name': 'aiohttp',
        'desc': "Tezkor asinxron HTTP so'rovlar mijoz/serveri",
        'category': 'Network',
        'install_cmd': 'aiohttp'
    },
    {
        'name': 'requests',
        'desc': "Mashhur sinxron HTTP kutubxonasi",
        'category': 'Network',
        'install_cmd': 'requests'
    },
    {
        'name': 'APScheduler',
        'desc': "Rejalashtirilgan vazifalar va taymerlar dvigateli (Cron)",
        'category': 'Utility',
        'install_cmd': 'APScheduler'
    },
    {
        'name': 'python-dotenv',
        'desc': ".env fayllardan maxfiy kalitlarni avtomatik o'qish",
        'category': 'Utility',
        'install_cmd': 'python-dotenv'
    },
    {
        'name': 'peewee',
        'desc': "Yengil va chaqqon SQLite / PostgreSQL ORM",
        'category': 'Database',
        'install_cmd': 'peewee'
    },
    {
        'name': 'Pillow',
        'desc': "Rasmlar va media fayllarni tahrirlash",
        'category': 'Media',
        'install_cmd': 'Pillow'
    }
]

def get_pip_executable() -> str:
    venv_win = Path(settings.BASE_DIR) / '.venv' / 'Scripts' / 'pip.exe'
    if venv_win.exists():
        return str(venv_win)
    venv_unix = Path(settings.BASE_DIR) / '.venv' / 'bin' / 'pip'
    if venv_unix.exists():
        return str(venv_unix)
    return sys.executable.replace('python.exe', 'pip.exe').replace('python', 'pip')

def install_package(package_name: str) -> tuple[bool, str]:
    package_name = package_name.strip()
    if not re.match(r'^[a-zA-Z0-9_\-\.\=\<\>\~\,\ ]+$', package_name):
        return False, "Kutubxona nomida ruxsat etilmagan belgilar mavjud!"

    pip_exe = get_pip_executable()
    cmd = [pip_exe, "install", "--no-input", package_name]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
        return proc.returncode == 0, output.strip()
    except subprocess.TimeoutExpired:
        return False, "O'rnatish vaqti tugadi (120 soniya chegara)."
    except Exception as e:
        return False, f"O'rnatishda xatolik yuz berdi: {str(e)}"

def install_requirements_file(req_path: Path) -> tuple[bool, str]:
    if not req_path.exists():
        return False, "requirements.txt fayli diskda topilmadi!"

    pip_exe = get_pip_executable()
    cmd = [pip_exe, "install", "--no-input", "-r", str(req_path)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
        return proc.returncode == 0, output.strip()
    except subprocess.TimeoutExpired:
        return False, "requirements.txt o'rnatish vaqti tugadi (180 soniya)."
    except Exception as e:
        return False, f"O'rnatishda xatolik yuz berdi: {str(e)}"

def list_installed_packages() -> list:
    pip_exe = get_pip_executable()
    try:
        proc = subprocess.run([pip_exe, "list", "--format=json"], capture_output=True, text=True, timeout=10)
        if proc.returncode == 0:
            return json.loads(proc.stdout)
    except Exception as e:
        logger.warning(f"Error listing packages: {e}")
    return []
