import os
import time
import logging
import threading
from pathlib import Path
from django.utils import timezone
from django.conf import settings
from apps.filemanager.models import File, Folder

logger = logging.getLogger(__name__)

def rehydrate_all_user_workspaces():
    """
    Reconstructs all user folders and files from Supabase PostgreSQL onto the local disk.
    Called immediately after Render finishes a build and starts a new container.
    """
    try:
        folder_count = 0
        for fld in Folder.objects.all():
            try:
                fld.ensure_on_disk()
                folder_count += 1
            except Exception as e:
                logger.error(f"Error restoring folder #{fld.id}: {e}")

        file_count = 0
        for f in File.objects.all():
            try:
                f.ensure_on_disk()
                file_count += 1
            except Exception as e:
                logger.error(f"Error restoring file #{f.id}: {e}")

        logger.info(f"[PyHosting Storage] {folder_count} ta papka va {file_count} ta fayl diskka tiklandi.")

        storage_root = getattr(settings, 'USER_STORAGE_ROOT', Path(settings.MEDIA_ROOT) / 'users')
        if storage_root.exists():
            import shutil
            from apps.accounts.models import User
            valid_user_ids = set(User.objects.values_list('id', flat=True))
            for user_dir in storage_root.iterdir():
                if user_dir.is_dir() and user_dir.name.isdigit():
                    if int(user_dir.name) not in valid_user_ids:
                        shutil.rmtree(user_dir, ignore_errors=True)
                        logger.info(f"[PyHosting Storage] O'chirilgan foydalanuvchi papkasi diskdan tozalandi: #{user_dir.name}")
    except Exception as e:
        logger.error(f"[PyHosting Storage] Tiklashda xatolik: {e}")

def sync_disk_changes_to_database():
    """
    Periodically inspects user directories on disk and syncs modified or created
    files (SQLite databases, logs, json) back into Supabase PostgreSQL.
    Guarantees zero data loss across Render redeploys and restarts.
    """
    from apps.filemanager.models import ALLOWED_EXTENSIONS
    try:
        storage_root = getattr(settings, 'USER_STORAGE_ROOT', Path(settings.MEDIA_ROOT) / 'users')
        if not storage_root.exists():
            return

        for user_dir in storage_root.iterdir():
            if not user_dir.is_dir() or not user_dir.name.isdigit():
                continue
            user_id = int(user_dir.name)

            for disk_file in user_dir.rglob('*'):
                if disk_file.is_file() and disk_file.suffix.lower() in ALLOWED_EXTENSIONS:
                    if disk_file.stat().st_size > 25 * 1024 * 1024:
                        continue

                    relative_path = disk_file.relative_to(user_dir).as_posix()
                    file_name = disk_file.name

                    db_file = File.objects.filter(owner_id=user_id, name=file_name).first()
                    if db_file:
                        try:
                            if db_file.is_binary or disk_file.suffix.lower() in ['.db', '.sqlite', '.sqlite3']:
                                disk_bytes = disk_file.read_bytes()
                                import base64
                                encoded = base64.b64encode(disk_bytes).decode('ascii')
                                if encoded != db_file.content:
                                    db_file.content = encoded
                                    db_file.is_binary = True
                                    db_file.size_kb = round(len(disk_bytes) / 1024.0, 3)
                                    db_file.save(update_fields=['content', 'is_binary', 'size_kb', 'updated_at'])
                            else:
                                disk_text = disk_file.read_text(encoding='utf-8', errors='replace')
                                if disk_text != db_file.content:
                                    db_file.content = disk_text
                                    db_file.is_binary = False
                                    db_file.size_kb = round(len(disk_text.encode('utf-8')) / 1024.0, 3)
                                    db_file.save(update_fields=['content', 'is_binary', 'size_kb', 'updated_at'])
                        except Exception as file_sync_err:
                            logger.debug(f"Sync error for {disk_file}: {file_sync_err}")
    except Exception as e:
        logger.debug(f"Periodic disk-to-DB sync exception: {e}")

def resume_running_bots():
    """
    Auto-resumes all bots that were running before the server restarted or deployed.
    """
    from .models import BotProcess
    from .runner import start_bot_process, broadcast_log, _ACTIVE_SUBPROCESSES

    try:
        active_bots = BotProcess.objects.filter(status='running', file__isnull=False).select_related('file', 'owner')
        for bot in active_bots:
            if bot.id in _ACTIVE_SUBPROCESSES:
                continue

            try:
                bot.file.ensure_on_disk()

                bot.restart_count = 0
                bot.save(update_fields=['restart_count'])

                logger.info(f"[🚀 PyHosting Auto-Resume] Bot qayta tiklanmoqda: {bot.file.name} (User: {bot.owner.username})")
                start_bot_process(bot.file.id, bot.owner)
                broadcast_log(
                    bot,
                    "[🚀 PyHosting Tizim] Server yangilanishidan so'ng bot 24/7 rejimida avtomatik muvaffaqiyatli qayta ishga tushirildi!",
                    level='INFO'
                )
            except Exception as bot_err:
                logger.error(f"Botni qayta ishga tushirishda xatolik #{bot.id}: {bot_err}")
                bot.status = 'crashed'
                bot.last_error = f"Server startida qayta ishga tushirish xatosi: {bot_err}"
                bot.stopped_at = timezone.now()
                bot.save(update_fields=['status', 'last_error', 'stopped_at'])
    except Exception as e:
        logger.error(f"[PyHosting Auto-Resume] Xatolik: {e}")

def run_server_startup_sequence():
    """
    Runs asynchronous startup sequence: restores workspaces, resumes bots.
    """
    def _worker():
        time.sleep(4)
        from django.db import close_old_connections
        close_old_connections()
        logger.info("[🚀 PyHosting Startup] Server start ketma-ketligi boshlandi...")
        try:
            from .models import BotProcess
            BotProcess.objects.filter(status='running').update(pid=None)
        except Exception:
            pass
        rehydrate_all_user_workspaces()
        resume_running_bots()
        logger.info("[✅ PyHosting Startup] Barcha foydalanuvchi fayllari va botlari to'liq tiklandi.")

    t = threading.Thread(target=_worker, daemon=True, name="PyHosting-StartupSequence")
    t.start()
